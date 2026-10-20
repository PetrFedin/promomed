"""PARTNER-01 qualification: verified organization scope + consented lead lifecycle."""
import importlib
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app import partner_commercial
from app.auth import hash_password


class PartnerCommercialTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "SQLITE_PATH":str(Path(self.temp.name)/"partner-commercial.db"),
            "DATABASE_URL":"",
            "PROMOMED_SEED_DEMO":"false",
            "PROMOMED_REQUIRE_POSTGRES":"false",
        })
        self.env.start()
        from app import db
        importlib.reload(db)
        importlib.reload(partner_commercial)
        self.db=db
        self.c=db.connect()
        db.migrate(self.c)
        self.now=int(time.time())
        self.partner_a="partner-a@example.test"
        self.partner_b="partner-b@example.test"
        self.participant="participant@example.test"
        for email,role in (
            (self.partner_a,"partner"),
            (self.partner_b,"partner"),
            (self.participant,"participant"),
        ):
            self.c.execute(
                "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
                "VALUES(?,?,?,?, 'active',?,?)",
                (email,hash_password("StrongPartnerTest!42"),role,email,self.now,self.now),
            )
        for org,name,partner_id in (
            ("ORG-A","Organization A","partner-a"),
            ("ORG-B","Organization B","partner-b"),
        ):
            self.c.execute(
                "INSERT INTO institutional_organizations("
                "id,name,organization_type,status,external_ref,credential_source,partner_id,"
                "created_at,created_by,demo_only) VALUES(?,?,?,'active','ext','registry',?,?,?,0)",
                (org,name,"commercial_partner",partner_id,self.now,"governance"),
            )
        for idx,(org,email) in enumerate((("ORG-A",self.partner_a),("ORG-B",self.partner_b)),1):
            self.c.execute(
                "INSERT INTO institutional_memberships("
                "id,organization_id,account_email,member_role,status,effective_at,expires_at,"
                "verified_by,verification_ref,demo_only) "
                "VALUES(?,?,?,'administrator','active',?,NULL,'governance',?,0)",
                (f"M{idx}",org,email,self.now-10,f"verification:{idx}"),
            )
        self.c.commit()

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.temp.cleanup()

    def cmd(self,role,email,**data):
        out=partner_commercial.handle_command(
            self.c,partner_commercial.ROUTE,role,email,data
        )
        if out.status<400:self.c.commit()
        else:self.c.rollback()
        return out

    def enable_org_a(self):
        out=self.cmd(
            "partner",self.partner_a,
            action="placement_update",organization_id="ORG-A",
            status="enabled",expected_version=0,
        )
        self.assertEqual(out.status,201)
        return out

    def test_partner_can_update_only_verified_member_organization(self):
        first=self.enable_org_a()
        self.assertEqual(first.payload["placement"]["organization_id"],"ORG-A")
        self.assertEqual(first.payload["placement"]["version"],1)
        denied=self.cmd(
            "partner",self.partner_b,
            action="placement_update",organization_id="ORG-A",
            status="paused",expected_version=1,
        )
        self.assertEqual((denied.status,denied.payload["error"]),(404,"organization_not_found"))
        row=self.c.execute(
            "SELECT status,version FROM partner_commercial_placements_v1 "
            "WHERE organization_id='ORG-A'"
        ).fetchone()
        self.assertEqual(dict(row),{"status":"enabled","version":1})

    def test_optimistic_version_prevents_lost_update(self):
        self.enable_org_a()
        ok=self.cmd(
            "partner",self.partner_a,
            action="placement_update",organization_id="ORG-A",
            status="paused",expected_version=1,
        )
        self.assertEqual(ok.payload["placement"]["version"],2)
        stale=self.cmd(
            "partner",self.partner_a,
            action="placement_update",organization_id="ORG-A",
            status="enabled",expected_version=1,
        )
        self.assertEqual((stale.status,stale.payload["error"]),(409,"version_conflict"))

    def test_lead_requires_enabled_target_and_explicit_consent(self):
        key="a"*32
        unavailable=self.cmd(
            "participant",self.participant,
            action="lead_submit",organization_id="ORG-A",
            request_id=key,kind="materials",consent=True,
        )
        self.assertEqual((unavailable.status,unavailable.payload["error"]),(404,"organization_not_found"))
        self.enable_org_a()
        no_consent=self.cmd(
            "participant",self.participant,
            action="lead_submit",organization_id="ORG-A",
            request_id=key,kind="materials",consent=False,
        )
        self.assertEqual((no_consent.status,no_consent.payload["error"]),(422,"consent_required"))
        created=self.cmd(
            "participant",self.participant,
            action="lead_submit",organization_id="ORG-A",
            request_id=key,kind="materials",consent=True,
        )
        self.assertEqual(created.status,201)
        self.assertEqual(created.payload["lead"]["organization_id"],"ORG-A")

    def test_lead_is_visible_only_to_target_org_and_withdrawal_removes_visibility(self):
        self.enable_org_a()
        created=self.cmd(
            "participant",self.participant,
            action="lead_submit",organization_id="ORG-A",
            request_id="b"*32,kind="follow_up",consent=True,
        )
        lead_id=created.payload["lead"]["id"]

        a,status=partner_commercial.read(
            self.c,partner_commercial.ROUTE,"partner",self.partner_a
        )
        self.assertEqual(status,200)
        self.assertEqual(a["organizations"][0]["leads"][0]["email"],self.participant)

        b,status=partner_commercial.read(
            self.c,partner_commercial.ROUTE,"partner",self.partner_b
        )
        self.assertEqual(status,200)
        self.assertNotIn(self.participant,str(b))

        withdrawn=self.cmd(
            "participant",self.participant,
            action="lead_withdraw",lead_id=lead_id,
        )
        self.assertEqual(withdrawn.status,200)
        a,_=partner_commercial.read(
            self.c,partner_commercial.ROUTE,"partner",self.partner_a
        )
        self.assertNotIn(self.participant,str(a))
        mine,_=partner_commercial.read(
            self.c,partner_commercial.ROUTE,"participant",self.participant
        )
        self.assertEqual(mine["myLeads"][0]["status"],"withdrawn")

    def test_lead_request_is_idempotent_and_conflict_safe(self):
        self.enable_org_a()
        data=dict(
            action="lead_submit",organization_id="ORG-A",
            request_id="c"*32,kind="materials",consent=True,
        )
        first=self.cmd("participant",self.participant,**data)
        replay=self.cmd("participant",self.participant,**data)
        self.assertEqual(first.payload["lead"],replay.payload["lead"])
        self.assertTrue(replay.payload["replayed"])
        conflict=self.cmd(
            "participant",self.participant,
            **{**data,"kind":"other"}
        )
        self.assertEqual((conflict.status,conflict.payload["error"]),(409,"idempotency_conflict"))
        n=self.c.execute(
            "SELECT COUNT(*) n FROM participant_partner_leads_v1 WHERE email=?",
            (self.participant,),
        ).fetchone()["n"]
        self.assertEqual(int(n),1)

    def test_partner_snapshot_never_exposes_other_org_placement(self):
        self.enable_org_a()
        self.cmd(
            "partner",self.partner_b,
            action="placement_update",organization_id="ORG-B",
            status="enabled",expected_version=0,
        )
        a,_=partner_commercial.read(
            self.c,partner_commercial.ROUTE,"partner",self.partner_a
        )
        text=str(a)
        self.assertIn("ORG-A",text)
        self.assertNotIn("ORG-B",text)

    def test_structured_action_and_state_return_client_error(self):
        for invalid in ([],{},["placement_update"]):
            out=partner_commercial.handle_command(
                self.c,partner_commercial.ROUTE,"partner",self.partner_a,
                {"action":invalid},
            )
            self.assertEqual(out.status,400)
        for invalid in ([],{},["enabled"]):
            out=partner_commercial.handle_command(
                self.c,partner_commercial.ROUTE,"partner",self.partner_a,
                {"action":"placement_update","organization_id":"ORG-A",
                 "status":invalid,"expected_version":1},
            )
            self.assertEqual(out.status,422)

    def test_query_selectors_and_foreign_roles_are_rejected(self):
        payload,status=partner_commercial.read(
            self.c,partner_commercial.ROUTE+"?organization_id=ORG-B",
            "partner",self.partner_a,
        )
        self.assertEqual((payload,status),({"error":"unsupported_query"},422))
        out=self.cmd(
            "organizer","organizer@example.test",
            action="placement_update",organization_id="ORG-A",
            status="enabled",expected_version=0,
        )
        self.assertEqual(out.status,403)

    def test_operational_status_does_not_claim_contract_or_revenue(self):
        self.enable_org_a()
        payload,_=partner_commercial.read(
            self.c,partner_commercial.ROUTE,"partner",self.partner_a
        )
        self.assertTrue(payload["truthBoundary"]["operationalPlacementNotContract"])
        self.assertFalse(payload["truthBoundary"]["revenueClaimed"])
        self.assertNotIn("contracted",str(payload).lower())

    def test_unbound_partner_cannot_read_contacts_or_modify_placement(self):
        self.enable_org_a()
        lead=self.cmd(
            "participant",self.participant,
            action="lead_submit",organization_id="ORG-A",
            request_id="f"*32,kind="follow_up",consent=True,
        )
        self.assertEqual(lead.status,201)
        lead_id=lead.payload["lead"]["id"]
        before,_=partner_commercial.read(
            self.c,partner_commercial.ROUTE,"partner",self.partner_a
        )
        self.assertIn(self.participant,str(before))
        for unbound_value in (None, "   "):
            with self.subTest(value=unbound_value):
                self.c.execute(
                    "UPDATE institutional_organizations SET partner_id=? WHERE id='ORG-A'",
                    (unbound_value,),
                )
                self.c.commit()
                hidden,status=partner_commercial.read(
                    self.c,partner_commercial.ROUTE,"partner",self.partner_a
                )
                self.assertEqual(status,200)
                self.assertEqual(hidden["organizations"],[])
                denied=self.cmd(
                    "partner",self.partner_a,action="placement_update",
                    organization_id="ORG-A",status="paused",expected_version=1,
                )
                self.assertEqual(
                    (denied.status,denied.payload["error"]),
                    (404,"organization_not_found"),
                )
                no_new_lead=self.cmd(
                    "participant",self.participant,action="lead_submit",
                    organization_id="ORG-A",request_id="d"*32,
                    kind="materials",consent=True,
                )
                self.assertEqual(
                    (no_new_lead.status,no_new_lead.payload["error"]),
                    (404,"organization_not_found"),
                )
        owner,_=partner_commercial.read(
            self.c,partner_commercial.ROUTE,"participant",self.participant
        )
        self.assertEqual(owner["myLeads"][0]["id"],lead_id)
        withdrawn=self.cmd(
            "participant",self.participant,action="lead_withdraw",lead_id=lead_id
        )
        self.assertEqual(withdrawn.status,200)

    def test_stale_placement_and_withdraw_replay_are_not_new_transitions(self):
        first=self.enable_org_a()
        self.assertEqual(first.payload["placement"]["version"],1)
        duplicate=self.cmd(
            "partner",self.partner_a,action="placement_update",
            organization_id="ORG-A",status="enabled",expected_version=0,
        )
        self.assertEqual(
            (duplicate.status,duplicate.payload["error"]),
            (409,"version_conflict"),
        )
        created=self.cmd(
            "participant",self.participant,action="lead_submit",
            organization_id="ORG-A",request_id="8"*32,
            kind="materials",consent=True,
        )
        self.assertEqual(created.status,201)
        lead_id=created.payload["lead"]["id"]
        withdrawal=self.cmd(
            "participant",self.participant,action="lead_withdraw",lead_id=lead_id
        )
        self.assertEqual(withdrawal.status,200)
        self.assertFalse(withdrawal.payload["replayed"])
        replay=self.cmd(
            "participant",self.participant,action="lead_withdraw",lead_id=lead_id
        )
        self.assertEqual(replay.status,200)
        self.assertTrue(replay.payload["replayed"])
        self.assertEqual(
            self.c.execute(
                "SELECT COUNT(*) n FROM participant_partner_leads_v1 "
                "WHERE email=? AND request_key=?",(self.participant,"8"*32),
            ).fetchone()["n"],1,
        )


if __name__=="__main__":
    unittest.main()
