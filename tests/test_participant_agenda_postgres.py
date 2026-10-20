"""Real PostgreSQL 17 tenant and calendar projection qualification."""
import os
import time
import unittest
import uuid

from app import db, participant_agenda as agenda
from app.auth import hash_password


@unittest.skipUnless(
    os.environ.get("PROMOMED_AGENDA_PG_TEST")=="1",
    "isolated PostgreSQL 17 participant agenda qualification only",
)
class AgendaPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if db.backend_name()!="postgres":
            raise RuntimeError("postgres_required")
        c=db.connect()
        try:
            db.migrate(c)
        finally:
            c.close()

    def setUp(self):
        tag=uuid.uuid4().hex[:12]
        self.owner="agenda-"+tag+"@example.test"
        self.other="agenda-other-"+tag+"@example.test"
        self.org="AG-ORG-"+tag
        self.slot=uuid.uuid4().hex
        self.event="AG-EVENT-"+tag
        self.now=int(time.time())
        c=db.connect()
        try:
            for email in (self.owner,self.other):
                c.execute(
                    "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
                    "VALUES(?,?,'participant',?,'active',?,?)",
                    (email,hash_password("StrongAgendaPg!42"),email,self.now,self.now),
                )
            c.execute(
                "INSERT INTO institutional_organizations("
                "id,name,organization_type,status,external_ref,credential_source,partner_id,"
                "created_at,created_by,demo_only) VALUES(?,?,?,'active','test','fixture',?,?,?,0)",
                (self.org,"Synthetic Organization","strategic_partner","synthetic-binding",
                 self.now,"ci-governance"),
            )
            c.execute(
                "INSERT INTO partner_commercial_placements_v1("
                "organization_id,status,version,updated_at,updated_by,demo_only"
                ") VALUES(?,'enabled',1,?,'ci-governance',0)",
                (self.org,self.now),
            )
            c.execute(
                "INSERT INTO partner_appointment_slots_v1("
                "id,organization_id,starts_at,ends_at,capacity,status,version,"
                "created_at,updated_at,created_by,demo_only"
                ") VALUES(?,?,?, ?,1,'open',1,?,?,'ci-partner',0)",
                (self.slot,self.org,self.now+3600,self.now+5400,self.now,self.now),
            )
            c.execute(
                "INSERT INTO participant_partner_appointments_v1("
                "slot_id,email,status,contact_consent_at,requested_at,updated_at"
                ") VALUES(?,?,'booked',?,?,?)",
                (self.slot,self.owner,self.now,self.now,self.now),
            )
            c.execute(
                "INSERT INTO event_editions_v1("
                "id,title,starts_at,registration_status,capacity,demo_only,created_at,updated_at"
                ") VALUES(?, 'Synthetic Event',?,'open',10,0,?,?)",
                (self.event,self.now+86400,self.now,self.now),
            )
            for email,status in ((self.owner,"confirmed"),(self.other,"waitlist")):
                c.execute(
                    "INSERT INTO participant_event_registrations_v1("
                    "event_id,email,status,requested_at,updated_at,source"
                    ") VALUES(?,?,?,?,?,'participant')",
                    (self.event,email,status,self.now,self.now),
                )
            c.commit()
        finally:
            c.close()

    def tearDown(self):
        c=db.connect()
        try:
            c.execute("DELETE FROM participant_partner_appointments_v1 WHERE slot_id=?",(self.slot,))
            c.execute("DELETE FROM partner_appointment_slots_v1 WHERE id=?",(self.slot,))
            c.execute("DELETE FROM partner_commercial_placements_v1 WHERE organization_id=?",(self.org,))
            c.execute("DELETE FROM institutional_organizations WHERE id=?",(self.org,))
            c.execute("DELETE FROM participant_event_registrations_v1 WHERE event_id=?",(self.event,))
            c.execute("DELETE FROM event_editions_v1 WHERE id=?",(self.event,))
            for email in (self.owner,self.other):
                c.execute("DELETE FROM auth_sessions WHERE email=?",(email,))
                c.execute("DELETE FROM accounts WHERE email=?",(email,))
            c.commit()
        finally:
            c.close()

    def test_tenant_private_calendar_and_unconfirmed_exclusion(self):
        c=db.connect()
        try:
            owner,status=agenda.read(c,agenda.ROUTE,"participant",self.owner)
            self.assertEqual(status,200)
            self.assertEqual(len(owner["items"]),2)
            self.assertEqual(sum(x["calendarEligible"] for x in owner["items"]),2)
            self.assertEqual(owner["calendarIcs"].count("BEGIN:VEVENT"),2)
            self.assertEqual(owner["calendarIcs"].count("DTEND:"),1)
            self.assertNotIn(self.owner,owner["calendarIcs"])
            self.assertNotIn(self.other,str(owner))
            other,status=agenda.read(c,agenda.ROUTE,"participant",self.other)
            self.assertEqual(status,200)
            self.assertEqual(len(other["items"]),1)
            self.assertEqual(other["items"][0]["state"],"waitlist")
            self.assertEqual(other["calendarIcs"].count("BEGIN:VEVENT"),0)
            self.assertEqual(
                agenda.read(c,agenda.ROUTE+"?email="+self.other,"participant",self.owner)[1],
                422,
            )
        finally:
            c.close()

    def test_unbinding_hides_calendar_booking_but_keeps_owner_history(self):
        c=db.connect()
        try:
            c.execute(
                "UPDATE institutional_organizations SET partner_id=NULL WHERE id=?",
                (self.org,),
            )
            c.commit()
            owner=agenda.snapshot(c,self.owner,self.now)
            appointment=[x for x in owner["items"] if x["kind"]=="partner_appointment"][0]
            self.assertEqual(appointment["state"],"unavailable")
            self.assertFalse(appointment["calendarEligible"])
            self.assertEqual(owner["calendarIcs"].count("BEGIN:VEVENT"),1)
            self.assertEqual(len(owner["conflicts"]),0)
        finally:
            c.close()

    def test_revoked_identity_rejected(self):
        c=db.connect()
        try:
            c.execute("UPDATE accounts SET status='suspended' WHERE email=?",(self.owner,))
            c.commit()
            self.assertEqual(
                agenda.read(c,agenda.ROUTE,"participant",self.owner)[1],403
            )
        finally:
            c.close()


if __name__=="__main__":
    unittest.main()
