"""APPT-01 qualification for organization-scoped partner appointments."""
import importlib
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app import partner_appointments, partner_commercial
from app.auth import hash_password


class PartnerAppointmentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "SQLITE_PATH":str(Path(self.temp.name)/"partner-appointments.db"),
            "DATABASE_URL":"",
            "PROMOMED_SEED_DEMO":"false",
            "PROMOMED_REQUIRE_POSTGRES":"false",
        })
        self.env.start()
        from app import db
        importlib.reload(db)
        importlib.reload(partner_commercial)
        importlib.reload(partner_appointments)
        self.db=db
        self.c=db.connect()
        db.migrate(self.c)
        self.now=int(time.time())
        self.partner_a="partner-a@example.test"
        self.partner_b="partner-b@example.test"
        self.participant_a="participant-a@example.test"
        self.participant_b="participant-b@example.test"
        for email,role in (
            (self.partner_a,"partner"),
            (self.partner_b,"partner"),
            (self.participant_a,"participant"),
            (self.participant_b,"participant"),
        ):
            self.c.execute(
                "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
                "VALUES(?,?,?,?, 'active',?,?)",
                (email,hash_password("StrongAppointment!42"),role,email,self.now,self.now),
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
                (f"AM{idx}",org,email,self.now-10,f"verification:{idx}"),
            )
        self.c.commit()
        self.enable("ORG-A",self.partner_a)
        self.enable("ORG-B",self.partner_b)

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.temp.cleanup()

    def enable(self,org,email):
        out=partner_commercial.handle_command(
            self.c,partner_commercial.ROUTE,"partner",email,{
                "action":"placement_update",
                "organization_id":org,
                "status":"enabled",
                "expected_version":0,
            }
        )
        self.assertEqual(out.status,201)
        self.c.commit()

    def cmd(self,role,email,**data):
        out=partner_appointments.handle_command(
            self.c,partner_appointments.ROUTE,role,email,data
        )
        if out.status<400:self.c.commit()
        else:self.c.rollback()
        return out

    def create_slot(self,partner=None,org="ORG-A",capacity=1):
        partner=partner or self.partner_a
        out=self.cmd(
            "partner",partner,
            action="slot_create",
            organization_id=org,
            starts_at=self.now+3600,
            ends_at=self.now+5400,
            capacity=capacity,
        )
        self.assertEqual(out.status,201)
        return out.payload["slot"]["id"]

    def booking_status(self,slot,email):
        row=self.c.execute(
            "SELECT status FROM participant_partner_appointments_v1 "
            "WHERE slot_id=? AND email=?",
            (slot,email),
        ).fetchone()
        return row["status"] if row else None

    def test_partner_can_create_only_own_org_slot(self):
        slot=self.create_slot()
        denied=self.cmd(
            "partner",self.partner_b,
            action="slot_create",
            organization_id="ORG-A",
            starts_at=self.now+7200,
            ends_at=self.now+8100,
            capacity=1,
        )
        self.assertEqual((denied.status,denied.payload["error"]),(404,"organization_not_found"))
        row=self.c.execute(
            "SELECT organization_id FROM partner_appointment_slots_v1 WHERE id=?",
            (slot,),
        ).fetchone()
        self.assertEqual(row["organization_id"],"ORG-A")

    def test_capacity_waitlist_cancel_and_promotion(self):
        slot=self.create_slot(capacity=1)
        first=self.cmd(
            "participant",self.participant_a,
            action="book",slot_id=slot,contact_consent=True,
        )
        second=self.cmd(
            "participant",self.participant_b,
            action="book",slot_id=slot,contact_consent=True,
        )
        self.assertEqual(first.payload["appointment"]["status"],"booked")
        self.assertEqual(second.payload["appointment"]["status"],"waitlist")
        cancelled=self.cmd(
            "participant",self.participant_a,
            action="cancel",slot_id=slot,
        )
        self.assertTrue(cancelled.payload["queuePromotionOccurred"])
        self.assertEqual(self.booking_status(slot,self.participant_a),"cancelled")
        self.assertEqual(self.booking_status(slot,self.participant_b),"booked")

    def test_pause_blocks_new_booking_and_cancel_does_not_promote(self):
        slot=self.create_slot(capacity=1)
        self.cmd(
            "participant",self.participant_a,
            action="book",slot_id=slot,contact_consent=True,
        )
        self.cmd(
            "participant",self.participant_b,
            action="book",slot_id=slot,contact_consent=True,
        )
        paused=partner_commercial.handle_command(
            self.c,partner_commercial.ROUTE,"partner",self.partner_a,{
                "action":"placement_update","organization_id":"ORG-A",
                "status":"paused","expected_version":1,
            }
        )
        self.assertEqual(paused.status,200)
        self.c.commit()
        cancelled=self.cmd(
            "participant",self.participant_a,
            action="cancel",slot_id=slot,
        )
        self.assertFalse(cancelled.payload["queuePromotionOccurred"])
        self.assertEqual(self.booking_status(slot,self.participant_b),"waitlist")
        blocked=self.cmd(
            "participant",self.participant_a,
            action="book",slot_id=slot,contact_consent=True,
        )
        self.assertEqual((blocked.status,blocked.payload["error"]),(404,"slot_not_found"))

    def test_contact_consent_required_and_replay_is_idempotent(self):
        slot=self.create_slot()
        denied=self.cmd(
            "participant",self.participant_a,
            action="book",slot_id=slot,contact_consent=False,
        )
        self.assertEqual((denied.status,denied.payload["error"]),(422,"contact_consent_required"))
        first=self.cmd(
            "participant",self.participant_a,
            action="book",slot_id=slot,contact_consent=True,
        )
        replay=self.cmd(
            "participant",self.participant_a,
            action="book",slot_id=slot,contact_consent=True,
        )
        self.assertEqual(first.status,201)
        self.assertEqual(replay.status,200)
        self.assertTrue(replay.payload["replayed"])
        self.assertEqual(first.payload["appointment"],replay.payload["appointment"])

    def test_partner_snapshot_is_tenant_scoped_and_cancel_hides_contact(self):
        slot_a=self.create_slot()
        self.create_slot(partner=self.partner_b,org="ORG-B")
        self.cmd(
            "participant",self.participant_a,
            action="book",slot_id=slot_a,contact_consent=True,
        )
        a,status=partner_appointments.read(
            self.c,partner_appointments.ROUTE,"partner",self.partner_a
        )
        self.assertEqual(status,200)
        self.assertIn("ORG-A",str(a))
        self.assertNotIn("ORG-B",str(a))
        self.assertIn(self.participant_a,str(a))
        self.cmd(
            "participant",self.participant_a,
            action="cancel",slot_id=slot_a,
        )
        a,_=partner_appointments.read(
            self.c,partner_appointments.ROUTE,"partner",self.partner_a
        )
        self.assertNotIn(self.participant_a,str(a))

    def test_participant_snapshot_contains_only_owner_rows(self):
        slot=self.create_slot(capacity=2)
        self.cmd(
            "participant",self.participant_a,
            action="book",slot_id=slot,contact_consent=True,
        )
        self.cmd(
            "participant",self.participant_b,
            action="book",slot_id=slot,contact_consent=True,
        )
        mine,status=partner_appointments.read(
            self.c,partner_appointments.ROUTE,"participant",self.participant_a
        )
        self.assertEqual(status,200)
        self.assertEqual(len(mine["myAppointments"]),1)
        self.assertNotIn(self.participant_b,str(mine))

    def test_slot_version_and_capacity_floor(self):
        slot=self.create_slot(capacity=1)
        self.cmd(
            "participant",self.participant_a,
            action="book",slot_id=slot,contact_consent=True,
        )
        below=self.cmd(
            "partner",self.partner_a,
            action="slot_update",slot_id=slot,expected_version=1,
            starts_at=self.now+3600,ends_at=self.now+5400,
            capacity=0,status="open",
        )
        self.assertEqual(below.status,422)
        stale=self.cmd(
            "partner",self.partner_a,
            action="slot_update",slot_id=slot,expected_version=2,
            starts_at=self.now+3600,ends_at=self.now+5400,
            capacity=1,status="open",
        )
        self.assertEqual((stale.status,stale.payload["error"]),(409,"version_conflict"))
        ok=self.cmd(
            "partner",self.partner_a,
            action="slot_update",slot_id=slot,expected_version=1,
            starts_at=self.now+3600,ends_at=self.now+5400,
            capacity=2,status="open",
        )
        self.assertEqual(ok.payload["slot"]["version"],2)

    def test_expired_slot_blocks_booking_and_waitlist_promotion(self):
        slot=self.create_slot(capacity=1)
        self.cmd("participant",self.participant_a,action="book",
                 slot_id=slot,contact_consent=True)
        self.cmd("participant",self.participant_b,action="book",
                 slot_id=slot,contact_consent=True)
        # Advance the persisted slot clock without altering the real clock.
        self.c.execute(
            "UPDATE partner_appointment_slots_v1 SET starts_at=?,ends_at=? WHERE id=?",
            (self.now-7200,self.now-3600,slot),
        )
        self.c.commit()
        denied=self.cmd("participant",self.participant_b,action="book",
                        slot_id=slot,contact_consent=True)
        self.assertEqual((denied.status,denied.payload["error"]),
                         (404,"slot_not_found"))
        cancelled=self.cmd("participant",self.participant_a,action="cancel",
                           slot_id=slot)
        self.assertEqual(cancelled.status,200)
        self.assertFalse(cancelled.payload["queuePromotionOccurred"])
        self.assertEqual(self.booking_status(slot,self.participant_b),"waitlist")

    def test_inactive_organization_blocks_booking_and_queue_promotion(self):
        slot=self.create_slot(capacity=1)
        self.cmd("participant",self.participant_a,action="book",
                 slot_id=slot,contact_consent=True)
        self.cmd("participant",self.participant_b,action="book",
                 slot_id=slot,contact_consent=True)
        self.c.execute(
            "UPDATE institutional_organizations SET status='suspended' WHERE id=?",
            ("ORG-A",),
        )
        self.c.commit()
        denied=self.cmd("participant",self.participant_b,action="book",
                        slot_id=slot,contact_consent=True)
        self.assertEqual((denied.status,denied.payload["error"]),
                         (404,"slot_not_found"))
        cancelled=self.cmd("participant",self.participant_a,action="cancel",
                           slot_id=slot)
        self.assertEqual(cancelled.status,200)
        self.assertFalse(cancelled.payload["queuePromotionOccurred"])
        self.assertEqual(self.booking_status(slot,self.participant_b),"waitlist")

    def test_slot_update_cannot_reopen_expired_interval(self):
        slot=self.create_slot()
        denied=self.cmd(
            "partner",self.partner_a,action="slot_update",slot_id=slot,
            expected_version=1,starts_at=self.now-7200,
            ends_at=self.now-3600,capacity=1,status="open",
        )
        self.assertEqual((denied.status,denied.payload["error"]),
                         (422,"invalid_request"))

    def test_structured_slot_state_is_validation_error(self):
        slot=self.create_slot()
        for invalid in ([],{},["open"]):
            out=self.cmd("partner",self.partner_a,action="slot_update",
                         slot_id=slot,expected_version=1,
                         starts_at=self.now+3600,ends_at=self.now+5400,
                         capacity=1,status=invalid)
            self.assertEqual((out.status,out.payload["error"]),(422,"invalid_request"))

    def test_waitlist_promotion_skips_suspended_participant(self):
        slot=self.create_slot(capacity=1)
        self.cmd("participant",self.participant_a,action="book",
                 slot_id=slot,contact_consent=True)
        self.cmd("participant",self.participant_b,action="book",
                 slot_id=slot,contact_consent=True)
        self.c.execute("UPDATE accounts SET status='suspended' WHERE email=?",
                       (self.participant_b,))
        self.c.commit()
        cancelled=self.cmd("participant",self.participant_a,action="cancel",
                           slot_id=slot)
        self.assertEqual(cancelled.status,200)
        self.assertFalse(cancelled.payload["queuePromotionOccurred"])
        self.assertEqual(self.booking_status(slot,self.participant_b),"waitlist")

    def test_cannot_reopen_slot_while_partner_placement_paused(self):
        slot=self.create_slot()
        self.cmd("partner",self.partner_a,action="slot_update",
                 slot_id=slot,expected_version=1,
                 starts_at=self.now+3600,ends_at=self.now+5400,
                 capacity=1,status="closed")
        paused=partner_commercial.handle_command(
            self.c,partner_commercial.ROUTE,"partner",self.partner_a,
            {"action":"placement_update","organization_id":"ORG-A",
             "status":"paused","expected_version":1},
        )
        self.assertEqual(paused.status,200)
        self.c.commit()
        denied=self.cmd("partner",self.partner_a,action="slot_update",
                        slot_id=slot,expected_version=2,
                        starts_at=self.now+3600,ends_at=self.now+5400,
                        capacity=1,status="open")
        self.assertEqual((denied.status,denied.payload["error"]),
                         (409,"placement_unavailable"))

    def test_query_selectors_and_foreign_roles_are_rejected(self):
        payload,status=partner_appointments.read(
            self.c,partner_appointments.ROUTE+"?organization_id=ORG-B",
            "partner",self.partner_a,
        )
        self.assertEqual((payload,status),({"error":"unsupported_query"},422))
        out=self.cmd(
            "organizer","organizer@example.test",
            action="slot_create",organization_id="ORG-A",
            starts_at=self.now+3600,ends_at=self.now+5400,capacity=1,
        )
        self.assertEqual(out.status,403)


if __name__=="__main__":
    unittest.main()
