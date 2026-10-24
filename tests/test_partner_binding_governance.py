"""SQLite/P0 integration: two-actor binding decisions and owner continuity."""
import importlib
import io
import json
import os
import tempfile
import time
import unittest
import uuid
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import evidence_interchange, partner_binding_governance as binding
from app import partner_appointments, partner_commercial, participant_agenda
from app.auth import hash_password
from server import H


class BindingGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "SQLITE_PATH":str(Path(self.t.name)/"binding.db"),
            "DATABASE_URL":"",
            "PROMOMED_REQUIRE_POSTGRES":"false",
            "PROMOMED_SEED_DEMO":"false",
        })
        self.env.start()
        from app import db
        importlib.reload(db)
        self.db=db
        self.c=db.connect()
        db.migrate(self.c)
        tag=uuid.uuid4().hex[:10]
        self.org="BIND-ORG-"+tag
        self.partner_id="BIND-LEGACY-"+tag
        self.partner2_id="BIND-OTHER-"+tag
        self.proposer="bind-requester-"+tag+"@example.test"
        self.reviewer="bind-reviewer-"+tag+"@example.test"
        self.other="bind-third-"+tag+"@example.test"
        self.partner="bind-partner-"+tag+"@example.test"
        self.owner="bind-owner-"+tag+"@example.test"
        self.now=int(time.time())
        for email,role in (
            (self.proposer,"governance"),(self.reviewer,"governance"),
            (self.other,"governance"),(self.partner,"partner"),
            (self.owner,"participant"),
        ):
            self.c.execute(
                "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
                "VALUES(?,?,?,?,'active',?,?)",
                (email,hash_password("SyntheticCiOnly!42"),role,email,self.now,self.now),
            )
        for partner_id in (self.partner_id,self.partner2_id):
            self.c.execute(
                "INSERT INTO partners(id,name,category,description,status) "
                "VALUES(?,'Synthetic partner','ci','Synthetic','active')",
                (partner_id,),
            )
        evidence_interchange.register_organization(
            self.c,organization_id=self.org,name="Synthetic Binding Institution",
            organization_type="strategic_partner",actor=self.proposer,
            partner_id=self.partner_id,demo_only=False,
        )
        self.c.execute(
            "INSERT INTO institutional_memberships("
            "id,organization_id,account_email,member_role,status,effective_at,"
            "expires_at,verified_by,verification_ref,demo_only) "
            "VALUES(?,?,?,'administrator','active',?,NULL,?,?,0)",
            ("MEM-"+tag,self.org,self.partner,self.now-10,self.proposer,"synthetic-proof"),
        )
        self.c.execute(
            "INSERT INTO partner_commercial_placements_v1("
            "organization_id,status,version,updated_at,updated_by,demo_only) "
            "VALUES(?,'enabled',1,?,?,0)",
            (self.org,self.now,self.partner),
        )
        self.slot=uuid.uuid4().hex
        self.c.execute(
            "INSERT INTO partner_appointment_slots_v1("
            "id,organization_id,starts_at,ends_at,capacity,status,version,"
            "created_at,updated_at,created_by,demo_only) "
            "VALUES(?,?,?, ?,2,'open',1,?,?,?,0)",
            (self.slot,self.org,self.now+7200,self.now+9000,
             self.now,self.now,self.partner),
        )
        self.c.execute(
            "INSERT INTO participant_partner_appointments_v1("
            "slot_id,email,status,contact_consent_at,requested_at,updated_at) "
            "VALUES(?,?,'booked',?,?,?)",
            (self.slot,self.owner,self.now,self.now,self.now),
        )
        self.c.commit()

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.t.cleanup()

    def send(self,data,actor=None,role="governance"):
        out=binding.handle_command(
            self.c,binding.ROUTE,role,actor or self.proposer,data,
        )
        if out.status>=400:self.c.rollback()
        else:self.c.commit()
        return out

    def proposal(self,**overrides):
        args={
            "action":"propose",
            "request_id":uuid.uuid4().hex,
            "organization_id":self.org,
            "expected_version":0,
            "expected_partner_id":self.partner_id,
            "new_partner_id":None,
            "reason":"Contract expired; revoke commercial partner authority",
            "evidence_ref":"urn:test:contract-expired:123",
        }
        args.update(overrides)
        return args

    def decision(self,request_id,decision="approve",decision_id=None,reason=None):
        return {
            "action":"review","request_id":request_id,
            "decision_id":decision_id or uuid.uuid4().hex,
            "decision":decision,
            "review_reason":reason or "Reviewed the evidence and scope independently",
        }

    def status(self):
        return evidence_interchange.organization(self.c,self.org)["partner_id"]

    def test_two_actor_approval_revokes_commercial_not_owner_history(self):
        proposed=self.send(self.proposal())
        self.assertEqual(proposed.status,201)
        request_id=proposed.payload["request"]["id"]
        self.assertEqual(self.status(),self.partner_id)
        self.assertTrue(proposed.payload["requiresIndependentReviewer"])
        forbidden=self.send(self.decision(request_id))
        self.assertEqual((forbidden.status,forbidden.payload["error"]),
                         (403,"independent_review_required"))
        applied=self.send(self.decision(request_id),actor=self.reviewer)
        self.assertEqual(applied.status,200,applied.payload)
        self.assertEqual(applied.payload["request"]["status"],"applied")
        self.assertFalse(applied.payload["externalDataDeletionClaimed"])
        self.assertFalse(applied.payload["collaborationScopeAutomaticallyChanged"])
        self.assertIsNone(self.status())
        placement=self.c.execute(
            "SELECT status,version FROM partner_commercial_placements_v1 "
            "WHERE organization_id=?",(self.org,),
        ).fetchone()
        self.assertEqual((placement["status"],placement["version"]),("paused",2))
        slot=self.c.execute(
            "SELECT status,version FROM partner_appointment_slots_v1 WHERE id=?",
            (self.slot,),
        ).fetchone()
        self.assertEqual((slot["status"],slot["version"]),("closed",2))
        commerical,status=partner_commercial.read(
            self.c,partner_commercial.ROUTE,"partner",self.partner,
        )
        self.assertEqual(status,200)
        self.assertEqual(commerical["organizations"],[])
        appointments,status=partner_appointments.read(
            self.c,partner_appointments.ROUTE,"partner",self.partner,
        )
        self.assertEqual(status,200)
        self.assertEqual(appointments["organizations"],[])
        agenda,status=participant_agenda.read(
            self.c,participant_agenda.ROUTE,"participant",self.owner,
        )
        self.assertEqual(status,200)
        self.assertEqual(agenda["items"][0]["state"],"unavailable")
        self.assertEqual(agenda["calendarIcs"].count("BEGIN:VEVENT"),0)
        self.assertEqual(
            self.c.execute("SELECT COUNT(*) n FROM participant_partner_appointments_v1 "
                           "WHERE slot_id=?",(self.slot,)).fetchone()["n"],1,
        )
        cancelled=partner_appointments.handle_command(
            self.c,partner_appointments.ROUTE,"participant",self.owner,
            {"action":"cancel","slot_id":self.slot},
        )
        self.assertEqual(cancelled.status,200,cancelled.payload)
        self.assertFalse(cancelled.payload["queuePromotionOccurred"])
        self.c.commit()
        blocked=self.send(self.proposal(
            expected_partner_id=None,new_partner_id=self.partner2_id,
            expected_version=1,
        ))
        self.assertEqual(
            (blocked.status,blocked.payload["error"]),
            (409,"prior_commercial_history_requires_new_organization"),
        )

    def test_reject_and_replay_are_idempotent_and_append_only(self):
        args=self.proposal()
        one=self.send(args)
        self.assertEqual(one.status,201)
        retry=self.send(args)
        self.assertEqual(retry.status,200)
        self.assertTrue(retry.payload["replayed"])
        conflict=self.send({**args,"reason":"Changed evidence for same key"})
        self.assertEqual((conflict.status,conflict.payload["error"]),
                         (409,"idempotency_conflict"))
        denied=self.send(self.decision(args["request_id"],decision="reject"),
                         actor=self.proposer)
        self.assertEqual(denied.status,403)
        review=self.decision(args["request_id"],decision="reject")
        rejected=self.send(review,actor=self.reviewer)
        self.assertEqual(rejected.status,200)
        self.assertEqual(rejected.payload["request"]["status"],"rejected")
        self.assertEqual(self.status(),self.partner_id)
        replay=self.send(review,actor=self.reviewer)
        self.assertEqual(replay.status,200)
        self.assertTrue(replay.payload["replayed"])
        conflict=self.send(self.decision(args["request_id"],decision="approve"),
                           actor=self.other)
        self.assertEqual((conflict.status,conflict.payload["error"]),
                         (409,"decision_already_recorded"))
        history=list(self.c.execute(
            "SELECT event_no,action,receipt_sha256,previous_receipt_sha256 "
            "FROM institutional_partner_binding_events_v1 "
            "WHERE organization_id=? ORDER BY event_no",(self.org,),
        ))
        self.assertEqual([x["event_no"] for x in history],[1,2])
        self.assertEqual([x["action"] for x in history],["proposed","rejected"])
        self.assertIsNone(history[0]["previous_receipt_sha256"])
        self.assertEqual(history[1]["previous_receipt_sha256"],
                         history[0]["receipt_sha256"])
        with self.assertRaises(Exception):
            self.c.execute(
                "UPDATE institutional_partner_binding_events_v1 SET actor='falsified' "
                "WHERE organization_id=?",(self.org,),
            )
        self.c.rollback()

    def test_first_binding_requires_clean_tenant_and_two_actors(self):
        fresh=self.org+"-NEW"
        evidence_interchange.register_organization(
            self.c,organization_id=fresh,name="New unbound institution",
            organization_type="strategic_partner",actor=self.proposer,
            demo_only=False,
        )
        self.c.commit()
        args=self.proposal(
            organization_id=fresh,expected_partner_id=None,
            new_partner_id=self.partner2_id,
        )
        one=self.send(args)
        self.assertEqual(one.status,201,one.payload)
        applied=self.send(self.decision(args["request_id"]),actor=self.reviewer)
        self.assertEqual(applied.status,200,applied.payload)
        row=evidence_interchange.organization(self.c,fresh)
        self.assertEqual(row["partner_id"],self.partner2_id)
        self.assertEqual(binding._version(self.c,fresh),1)
        self.assertFalse(self.c.execute(
            "SELECT 1 FROM institutional_memberships WHERE organization_id=?",
            (fresh,),
        ).fetchone())
        not_permitted=self.send(self.proposal(
            organization_id=fresh,expected_partner_id=self.partner2_id,
            new_partner_id=self.partner_id,expected_version=1,
        ))
        self.assertEqual((not_permitted.status,not_permitted.payload["error"]),
                         (409,"reassignment_not_supported"))
        no_op=self.send(self.proposal(
            organization_id=fresh,expected_partner_id=self.partner2_id,
            new_partner_id=self.partner2_id,expected_version=1,
        ))
        self.assertEqual(no_op.status,409)

    def test_fresh_binding_cannot_activate_old_memberships(self):
        fresh=self.org+"-MEMBERS"
        evidence_interchange.register_organization(
            self.c,organization_id=fresh,name="Dormant verified members",
            organization_type="strategic_partner",actor=self.proposer,
            demo_only=False,
        )
        self.c.execute(
            "INSERT INTO institutional_memberships("
            "id,organization_id,account_email,member_role,status,effective_at,"
            "expires_at,verified_by,verification_ref,demo_only) "
            "VALUES(?,?,?,'operator','active',?,NULL,?,?,0)",
            (uuid.uuid4().hex,fresh,self.partner,self.now-10,
             self.proposer,"old-collaboration-only"),
        )
        self.c.commit()
        attempt=self.send(self.proposal(
            organization_id=fresh,expected_partner_id=None,
            new_partner_id=self.partner2_id,
        ))
        self.assertEqual(
            (attempt.status,attempt.payload["error"]),
            (409,"prior_commercial_history_requires_new_organization"),
        )
        self.assertIsNone(
            evidence_interchange.organization(self.c,fresh)["partner_id"],
        )
        self.c.execute(
            "UPDATE institutional_memberships SET status='revoked' "
            "WHERE organization_id=?",(fresh,),
        )
        self.c.commit()
        accepted=self.send(self.proposal(
            organization_id=fresh,expected_partner_id=None,
            new_partner_id=self.partner2_id,
        ))
        self.assertEqual(accepted.status,201,accepted.payload)

    def test_pending_overlap_stale_version_and_expiry(self):
        first=self.proposal()
        self.assertEqual(self.send(first).status,201)
        second=self.send(self.proposal())
        self.assertEqual((second.status,second.payload["error"]),
                         (409,"request_already_pending"))
        view,status=binding.read(
            self.c,binding.ROUTE+"?organization_id="+self.org,
            "governance",self.proposer,
        )
        self.assertEqual(status,200)
        self.assertEqual(view["bindingVersion"],0)
        self.assertEqual(view["requests"][0]["status"],"pending")
        self.assertFalse(view["truthBoundary"]["historicalContactTransfer"])
        expiry=view["requests"][0]["expires_at"]
        with patch("app.partner_binding_governance.time.time",return_value=expiry+1):
            expired=self.send(self.decision(first["request_id"]),actor=self.reviewer)
            self.assertEqual((expired.status,expired.payload["error"]),
                             (409,"request_expired"))
            self.assertEqual(
                binding.read(self.c,binding.ROUTE+"?organization_id="+self.org,
                             "governance",self.reviewer)[0]["requests"][0]["effective_status"],
                "expired",
            )
            new=self.send(self.proposal())
            self.assertEqual(new.status,201)
        self.assertEqual(self.status(),self.partner_id)
        mismatched=self.send(self.proposal(expected_version=9))
        self.assertEqual(mismatched.status,409)

    def test_roles_and_malformed_scope_fail_closed(self):
        for role,email in (("partner",self.partner),("participant",self.owner),
                           ("governance",self.partner)):
            out=self.send(self.proposal(),actor=email,role=role)
            self.assertEqual(out.status,403)
        self.c.execute("UPDATE accounts SET status='suspended' WHERE email=?",
                       (self.proposer,))
        self.c.commit()
        self.assertEqual(self.send(self.proposal()).status,403)
        self.assertEqual(
            binding.read(self.c,binding.ROUTE+"?organization_id="+self.org,
                         "governance",self.proposer)[1],403,
        )
        self.c.execute("UPDATE accounts SET status='active' WHERE email=?",
                       (self.proposer,))
        self.c.commit()
        for path in (
            binding.ROUTE,
            binding.ROUTE+"?organization_id="+self.org+"&email="+self.owner,
            binding.ROUTE+"?organization_id="+self.org+"&organization_id=x",
        ):
            self.assertEqual(
                binding.read(self.c,path,"governance",self.proposer)[1],422,
            )
        bad=self.send({"action":"propose","organization_id":self.org})
        self.assertEqual(bad.status,422)
        self.assertEqual(binding.serve(None,binding.ROUTE)[1],401)

    def test_authenticated_http_composition_and_owner_only_read(self):
        args=self.proposal()
        body=json.dumps(args).encode("utf-8")
        headers=Message()
        headers["Content-Length"]=str(len(body))
        fake=SimpleNamespace(
            path=binding.ROUTE,headers=headers,rfile=io.BytesIO(body),
            out=lambda value,status=200:(value,status),
        )
        with patch("server.auth",return_value=(
            "governance","synthetic",self.proposer,
        )):
            with patch("server.conn",side_effect=self.db.connect):
                result,status=H.do_POST(fake)
        self.assertEqual(status,201,result)
        self.c.rollback()
        self.assertEqual(self.status(),self.partner_id)
        get=SimpleNamespace(
            path=binding.ROUTE+"?organization_id="+self.org,
            out=lambda value,status=200:(value,status),
        )
        with patch("server.auth",return_value=(
            "governance","synthetic",self.reviewer,
        )):
            view,status=H.do_GET(get)
        self.assertEqual(status,200,view)
        self.assertEqual(len(view["requests"]),1)
        self.assertNotIn(self.owner,json.dumps(view))
        with patch("server.auth",return_value=None):
            self.assertEqual(H.do_GET(get),({"error":"unauthorized"},401))


if __name__=="__main__":
    unittest.main()
