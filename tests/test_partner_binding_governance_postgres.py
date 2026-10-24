"""PostgreSQL 17 independent-connection acceptance for commercial binding decisions."""
import os
import threading
import time
import unittest
import uuid

from app import db, evidence_interchange, partner_binding_governance as binding, partner_appointments
from app import partner_org_scope, participant_agenda, syndication_network
from app.auth import hash_password


@unittest.skipUnless(
    os.environ.get("PROMOMED_BINDING_GOV_PG_TEST")=="1",
    "isolated PostgreSQL 17 binding-governance qualification only",
)
class BindingGovernancePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if db.backend_name()!="postgres":
            raise RuntimeError("postgres_required")
        c=db.connect()
        try:db.migrate(c)
        finally:c.close()

    def setUp(self):
        tag=uuid.uuid4().hex[:12]
        self.org="PG-BIND-"+tag
        self.fresh=self.org+"-NEW"
        self.partner_id="PG-P-"+tag
        self.second_id="PG-P2-"+tag
        self.proposer="pg-governance-p-"+tag+"@example.test"
        self.reviewers=(
            "pg-governance-a-"+tag+"@example.test",
            "pg-governance-b-"+tag+"@example.test",
        )
        self.partner="pg-member-"+tag+"@example.test"
        self.owner="pg-owner-"+tag+"@example.test"
        self.slot=uuid.uuid4().hex
        self.now=int(time.time())
        c=db.connect()
        try:
            for email,role in (
                (self.proposer,"governance"),
                (self.reviewers[0],"governance"),
                (self.reviewers[1],"governance"),
                (self.partner,"partner"),
                (self.owner,"participant"),
            ):
                c.execute(
                    "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
                    "VALUES(?,?,?,?,'active',?,?)",
                    (email,hash_password("TemporaryPgGovOnly!42"),
                     role,email,self.now,self.now),
                )
            for partner_id in (self.partner_id,self.second_id):
                c.execute(
                    "INSERT INTO partners(id,name,category,description,status) "
                    "VALUES(?,'Synthetic','ci','Only for tests','active')",
                    (partner_id,),
                )
            evidence_interchange.register_organization(
                c,organization_id=self.org,name="PG Active Institution",
                organization_type="strategic_partner",actor=self.proposer,
                partner_id=self.partner_id,demo_only=False,
            )
            evidence_interchange.register_organization(
                c,organization_id=self.fresh,name="PG Unbound Institution",
                organization_type="strategic_partner",actor=self.proposer,
                demo_only=False,
            )
            c.execute(
                "INSERT INTO institutional_memberships("
                "id,organization_id,account_email,member_role,status,effective_at,"
                "expires_at,verified_by,verification_ref,demo_only)"
                " VALUES(?,?,?,'administrator','active',?,NULL,?,?,0)",
                (uuid.uuid4().hex,self.org,self.partner,self.now-10,
                 self.proposer,"pg-verification"),
            )
            c.execute(
                "INSERT INTO partner_commercial_placements_v1("
                "organization_id,status,version,updated_at,updated_by,demo_only) "
                "VALUES(?,'enabled',1,?,?,0)",
                (self.org,self.now,self.partner),
            )
            c.execute(
                "INSERT INTO partner_appointment_slots_v1("
                "id,organization_id,starts_at,ends_at,capacity,status,version,"
                "created_at,updated_at,created_by,demo_only) "
                "VALUES(?,?,?, ?,2,'open',1,?,?,?,0)",
                (self.slot,self.org,self.now+3600,self.now+5400,
                 self.now,self.now,self.partner),
            )
            c.execute(
                "INSERT INTO participant_partner_appointments_v1("
                "slot_id,email,status,contact_consent_at,requested_at,updated_at) "
                "VALUES(?,?,'booked',?,?,?)",
                (self.slot,self.owner,self.now,self.now,self.now),
            )
            c.commit()
        finally:c.close()

    def tearDown(self):
        c=db.connect()
        try:
            for org in (self.org,self.fresh):
                c.execute(
                    "DELETE FROM institutional_partner_binding_events_v1 "
                    "WHERE organization_id=?",(org,),
                )
                c.execute(
                    "DELETE FROM institutional_partner_binding_requests_v1 "
                    "WHERE organization_id=?",(org,),
                )
                c.execute(
                    "DELETE FROM institutional_partner_binding_revisions_v1 "
                    "WHERE organization_id=?",(org,),
                )
            c.execute("DELETE FROM participant_partner_appointments_v1 WHERE slot_id=?",
                      (self.slot,))
            c.execute("DELETE FROM partner_appointment_slots_v1 WHERE organization_id=?",
                      (self.org,))
            c.execute("DELETE FROM partner_commercial_placements_v1 WHERE organization_id=?",
                      (self.org,))
            c.execute(
                "DELETE FROM institutional_memberships "
                "WHERE organization_id IN (?,?)",(self.org,self.fresh),
            )
            for org in (self.org,self.fresh):
                c.execute("DELETE FROM institutional_organizations WHERE id=?",(org,))
            for email in (self.proposer,*self.reviewers,self.partner,self.owner):
                c.execute("DELETE FROM auth_sessions WHERE email=?",(email,))
                c.execute("DELETE FROM accounts WHERE email=?",(email,))
            for partner_id in (self.partner_id,self.second_id):
                c.execute("DELETE FROM partners WHERE id=?",(partner_id,))
            c.commit()
        finally:c.close()

    def propose(self,org=None,old=None,new=None,version=0):
        if org is None:
            org=self.org
            old=self.partner_id
        return {
            "action":"propose","request_id":uuid.uuid4().hex,
            "organization_id":org,"expected_version":version,
            "expected_partner_id":old,"new_partner_id":new,
            "reason":"PG controlled two person partner withdrawal or admission",
            "evidence_ref":"urn:synthetic:governance:pg:source",
        }

    @staticmethod
    def review(req_id,decision_id=None):
        return {
            "action":"review","request_id":req_id,
            "decision_id":decision_id or uuid.uuid4().hex,
            "decision":"approve",
            "review_reason":"Independently checked institution status and the evidence",
        }

    def send(self,c,email,data):
        out=binding.handle_command(c,binding.ROUTE,"governance",email,data)
        if out.status>=400:c.rollback()
        else:c.commit()
        return out

    def test_two_reviewers_only_one_can_approve_version_zero(self):
        c=db.connect()
        try:
            args=self.propose()
            first=self.send(c,self.proposer,args)
            self.assertEqual(first.status,201,first.payload)
        finally:c.close()
        barrier=threading.Barrier(2)
        outcomes=[]
        errors=[]
        def accept(actor):
            c=db.connect()
            try:
                barrier.wait(timeout=8)
                result=self.send(c,actor,self.review(args["request_id"]))
                outcomes.append((result.status,result.payload))
            except Exception as exc:
                try:c.rollback()
                except Exception:pass
                errors.append(repr(exc))
            finally:c.close()
        workers=[threading.Thread(target=accept,args=(actor,))
                 for actor in self.reviewers]
        for thread in workers:thread.start()
        for thread in workers:thread.join(timeout=25)
        self.assertFalse(any(t.is_alive() for t in workers))
        self.assertFalse(errors,errors)
        self.assertEqual(sorted(row[0] for row in outcomes),[200,409])
        self.assertEqual(
            next(row[1]["error"] for row in outcomes if row[0]==409),
            "decision_already_recorded",
        )
        c=db.connect()
        try:
            self.assertEqual(binding._version(c,self.org),1)
            self.assertIsNone(
                evidence_interchange.organization(c,self.org)["partner_id"],
            )
            self.assertEqual(
                c.execute(
                    "SELECT COUNT(*) n FROM institutional_partner_binding_events_v1 "
                    "WHERE organization_id=?",(self.org,),
                ).fetchone()["n"],2,
            )
            rows=list(c.execute(
                "SELECT event_no,action,receipt_sha256,previous_receipt_sha256 "
                "FROM institutional_partner_binding_events_v1 "
                "WHERE organization_id=? ORDER BY event_no",(self.org,),
            ))
            self.assertEqual([row["action"] for row in rows],
                             ["proposed","applied"])
            self.assertEqual(rows[1]["previous_receipt_sha256"],
                             rows[0]["receipt_sha256"])
            placement=c.execute(
                "SELECT status,version FROM partner_commercial_placements_v1 "
                "WHERE organization_id=?",(self.org,),
            ).fetchone()
            self.assertEqual((placement["status"],placement["version"]),("paused",2))
            self.assertIsNone(partner_org_scope.commercial_member(
                c,self.org,self.partner,
            ))
            appointment_owner,status=partner_appointments.read(
                c,partner_appointments.ROUTE,"participant",self.owner,
            )
            self.assertEqual(status,200)
            self.assertEqual(appointment_owner["myAppointments"][0]["status"],"booked")
            self.assertEqual(
                appointment_owner["myAppointments"][0]["effective_status"],
                "unavailable",
            )
            owner,status=participant_agenda.read(
                c,participant_agenda.ROUTE,"participant",self.owner,
            )
            self.assertEqual(status,200)
            self.assertEqual(owner["items"][0]["state"],"unavailable")
            self.assertEqual(owner["calendarIcs"].count("BEGIN:VEVENT"),0)
        finally:c.close()

    def test_proposal_concurrency_only_one_pending(self):
        barrier=threading.Barrier(2)
        outcomes=[]
        errors=[]
        def open_request():
            c=db.connect()
            try:
                payload=self.propose(org=self.fresh,old=None,
                                     new=self.second_id)
                barrier.wait(timeout=8)
                result=self.send(c,self.proposer,payload)
                outcomes.append(result.status)
            except Exception as exc:
                try:c.rollback()
                except Exception:pass
                errors.append(repr(exc))
            finally:c.close()
        workers=[threading.Thread(target=open_request) for _ in range(2)]
        for thread in workers:thread.start()
        for thread in workers:thread.join(timeout=25)
        self.assertFalse(any(t.is_alive() for t in workers))
        self.assertFalse(errors,errors)
        self.assertEqual(sorted(outcomes),[201,409])
        c=db.connect()
        try:
            self.assertEqual(
                c.execute("SELECT COUNT(*) n FROM institutional_partner_binding_requests_v1 "
                          "WHERE organization_id=?",(self.fresh,)).fetchone()["n"],1,
            )
            self.assertIsNone(
                evidence_interchange.organization(c,self.fresh)["partner_id"],
            )
        finally:c.close()

    def test_membership_authority_serializes_before_first_binding(self):
        c=db.connect()
        try:
            args=self.propose(org=self.fresh,old=None,new=self.second_id)
            self.assertEqual(self.send(c,self.proposer,args).status,201)
        finally:c.close()
        # An uncommitted membership claim holds the parent institution lock.
        # The independent reviewer must not approve from an old snapshot.
        member_c=db.connect()
        try:
            member=syndication_network.bind_member(
                member_c,self.fresh,self.partner,"operator",self.proposer,
                verification_ref="independent-verified-fixture",demo_only=False,
            )
            self.assertEqual(member["status"],"active")
            outcomes=[]
            errors=[]
            def review():
                worker=db.connect()
                try:
                    res=self.send(
                        worker,self.reviewers[0],self.review(args["request_id"]),
                    )
                    outcomes.append((res.status,res.payload))
                except Exception as exc:
                    try:worker.rollback()
                    except Exception:pass
                    errors.append(repr(exc))
                finally:worker.close()
            t=threading.Thread(target=review)
            t.start()
            # Committing the membership first must force a fresh history check
            # after the reviewer obtains the institution row lock.
            member_c.commit()
            t.join(timeout=25)
            self.assertFalse(t.is_alive())
            self.assertFalse(errors,errors)
            self.assertEqual(outcomes[0],(
                409,{"error":"prior_commercial_history_requires_new_organization"},
            ))
        finally:member_c.close()
        c=db.connect()
        try:
            self.assertIsNone(
                evidence_interchange.organization(c,self.fresh)["partner_id"],
            )
            self.assertEqual(binding._version(c,self.fresh),0)
        finally:c.close()

    def test_new_partner_cannot_inherit_previous_or_newer_commercial_history(self):
        c=db.connect()
        try:
            args=self.propose()
            self.assertEqual(self.send(c,self.proposer,args).status,201)
            self.assertEqual(
                self.send(c,self.reviewers[0],self.review(args["request_id"])).status,
                200,
            )
            self.assertIsNone(evidence_interchange.organization(c,self.org)["partner_id"])
            bad=self.propose(
                org=self.org,old=None,new=self.second_id,version=1,
            )
            out=self.send(c,self.proposer,bad)
            self.assertEqual((out.status,out.payload["error"]),
                             (409,"prior_commercial_history_requires_new_organization"))
            self.assertIsNone(evidence_interchange.organization(c,self.org)["partner_id"])
            good=self.propose(org=self.fresh,old=None,new=self.second_id)
            self.assertEqual(self.send(c,self.proposer,good).status,201)
            self.assertEqual(
                self.send(c,self.reviewers[0],self.review(good["request_id"])).status,
                200,
            )
            self.assertEqual(evidence_interchange.organization(c,self.fresh)["partner_id"],
                             self.second_id)
            self.assertIsNone(partner_org_scope.commercial_member(
                c,self.fresh,self.partner,
            ))
        finally:c.close()


if __name__=="__main__":
    unittest.main()
