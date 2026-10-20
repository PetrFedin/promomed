"""SQLite acceptance for one authenticated participant's unified agenda."""
import importlib
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app import participant_agenda as agenda
from app.auth import hash_password


class ParticipantAgendaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "SQLITE_PATH":str(Path(self.temp.name)/"agenda.db"),
            "DATABASE_URL":"",
            "PROMOMED_SEED_DEMO":"false",
            "PROMOMED_REQUIRE_POSTGRES":"false",
        })
        self.env.start()
        from app import db
        importlib.reload(db)
        self.db=db
        self.c=db.connect()
        db.migrate(self.c)
        self.now=int(time.time())
        self.a="agenda-a@example.test"
        self.b="agenda-b@example.test"
        self.partner="agenda-partner@example.test"
        for email,role in ((self.a,"participant"),(self.b,"participant"),(self.partner,"partner")):
            self.c.execute(
                "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
                "VALUES(?,?,?,?, 'active',?,?)",
                (email,hash_password("StrongAgendaTest!42"),role,email,self.now,self.now),
            )
        self.c.execute(
            "INSERT INTO institutional_organizations("
            "id,name,organization_type,status,external_ref,credential_source,partner_id,"
            "created_at,created_by,demo_only) VALUES(?,?,?,'active','synthetic','test',?,?,?,0)",
            ("AG-ORG","Synthetic Partner","strategic_partner","synthetic-partner",
             self.now,"governance-test"),
        )
        self.c.execute(
            "INSERT INTO partner_commercial_placements_v1("
            "organization_id,status,version,updated_at,updated_by,demo_only"
            ") VALUES(?,'enabled',1,?,?,0)",
            ("AG-ORG",self.now,self.partner),
        )
        self.events=[("EV-A","Evidence event",self.now+86400,"open","confirmed",self.a),
                     ("EV-B","Waiting event",self.now+172800,"open","waitlist",self.a),
                     ("EV-C","Cancelled event",self.now+259200,"cancelled","confirmed",self.a),
                     ("EV-OTHER","Foreign event",self.now+345600,"open","confirmed",self.b)]
        for eid,title,starts,org_status,participant_status,email in self.events:
            self.c.execute(
                "INSERT INTO event_editions_v1("
                "id,title,starts_at,registration_status,capacity,demo_only,created_at,updated_at"
                ") VALUES(?,?,?,?,10,0,?,?)",
                (eid,title,starts,org_status,self.now,self.now),
            )
            self.c.execute(
                "INSERT INTO participant_event_registrations_v1("
                "event_id,email,status,requested_at,updated_at,source"
                ") VALUES(?,?,?,?,?,'participant')",
                (eid,email,participant_status,self.now,self.now),
            )
        self.slots=[("a"*32,self.now+3600,self.now+5400,"booked",self.a),
                    ("b"*32,self.now+4800,self.now+6300,"booked",self.a),
                    ("c"*32,self.now+7200,self.now+9000,"waitlist",self.a),
                    ("d"*32,self.now+10800,self.now+12600,"booked",self.b)]
        for slot_id,starts,ends,status,email in self.slots:
            self.c.execute(
                "INSERT INTO partner_appointment_slots_v1("
                "id,organization_id,starts_at,ends_at,capacity,status,version,"
                "created_at,updated_at,created_by,demo_only"
                ") VALUES(?,'AG-ORG',?, ?,2,'open',1,?,?,?,0)",
                (slot_id,starts,ends,self.now,self.now,self.partner),
            )
            self.c.execute(
                "INSERT INTO participant_partner_appointments_v1("
                "slot_id,email,status,contact_consent_at,requested_at,updated_at"
                ") VALUES(?,?,?,?,?,?)",
                (slot_id,email,status,self.now,self.now,self.now),
            )
        self.c.commit()

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.temp.cleanup()

    def test_combined_calendar_is_owned_and_excludes_unconfirmed_rows(self):
        result,status=agenda.read(self.c,agenda.ROUTE,"participant",self.a)
        self.assertEqual(status,200)
        self.assertEqual(len(result["items"]),6)
        self.assertEqual(
            sorted(row["id"] for row in result["items"] if row["calendarEligible"]),
            ["appointment:"+"a"*32,"appointment:"+"b"*32,"event:EV-A"],
        )
        self.assertEqual(len(result["conflicts"]),1)
        self.assertEqual(
            {result["conflicts"][0]["first"],result["conflicts"][0]["second"]},
            {"appointment:"+"a"*32,"appointment:"+"b"*32},
        )
        exported=result["calendarIcs"]
        self.assertEqual(exported.count("BEGIN:VEVENT"),3)
        self.assertEqual(exported.count("DTEND:"),2)
        self.assertIn("DTSTART:",exported)
        self.assertNotIn("EV-B",exported)
        self.assertNotIn("Waiting event",exported)
        self.assertNotIn("Cancelled event",exported)
        self.assertNotIn(self.a,exported)
        self.assertNotIn(self.b,exported)
        self.assertNotIn("Foreign event",str(result))
        self.assertTrue(result["truthBoundary"]["eventEndNeverInvented"])
        self.assertTrue(result["truthBoundary"]["programmeClockOnlyExcluded"])

    def test_no_cross_account_selector_or_partner_role(self):
        for path in (
            agenda.ROUTE+"?email="+self.b,
            agenda.ROUTE+"?account="+self.b,
            agenda.ROUTE+"#calendar",
        ):
            with self.subTest(path=path):
                data,status=agenda.read(self.c,path,"participant",self.a)
                self.assertEqual((status,data["error"]),(422,"unsupported_query"))
        self.assertEqual(
            agenda.read(self.c,agenda.ROUTE,"partner",self.partner)[1],403
        )
        self.assertEqual(agenda.serve(None,agenda.ROUTE)[1],401)
        foreign,status=agenda.read(self.c,agenda.ROUTE,"participant",self.b)
        self.assertEqual(status,200)
        self.assertNotIn("Evidence event",str(foreign))
        self.assertNotIn("Waiting event",str(foreign))

    def test_binding_revocation_does_not_export_stale_partner_meetings(self):
        self.c.execute(
            "UPDATE institutional_organizations SET partner_id=NULL WHERE id='AG-ORG'"
        )
        self.c.commit()
        snapshot=agenda.snapshot(self.c,self.a,self.now)
        appointments=[x for x in snapshot["items"] if x["kind"]=="partner_appointment"]
        self.assertTrue(appointments)
        self.assertTrue(all(x["state"]=="unavailable" for x in appointments[:2]))
        self.assertTrue(all(not x["calendarEligible"] for x in appointments))
        self.assertEqual(snapshot["conflicts"],[])
        self.assertEqual(snapshot["calendarIcs"].count("BEGIN:VEVENT"),1)
        self.assertIn("Evidence event",snapshot["calendarIcs"])

    def test_cancelled_and_waitlisted_records_are_visible_not_confirmed(self):
        result=agenda.snapshot(self.c,self.a,self.now)
        by_id={x["id"]:x for x in result["items"]}
        self.assertEqual(by_id["event:EV-B"]["state"],"waitlist")
        self.assertEqual(by_id["event:EV-C"]["state"],"unavailable")
        self.assertEqual(by_id["appointment:"+"c"*32]["state"],"waitlist")
        self.assertFalse(by_id["event:EV-B"]["calendarEligible"])
        self.assertFalse(by_id["event:EV-C"]["calendarEligible"])

    def test_ical_escape_fold_and_no_fabricated_duration(self):
        item={
            "id":"event:private",
            "kind":"event_edition",
            "title":"Тема,\r\nBEGIN:VALARM;extra" + "🌿"*35,
            "startsAt":self.now+3600,
            "endsAt":None,
            "calendarEligible":True,
        }
        ics=agenda._ics([item],self.now)
        self.assertEqual(ics.count("BEGIN:VEVENT"),1)
        self.assertNotIn("\r\nBEGIN:VALARM",ics)
        self.assertIn("\\nBEGIN:VALARM\\;extra",ics.replace("\r\n ",""))
        self.assertNotIn("DTEND:",ics)
        self.assertTrue(ics.endswith("\r\n"))
        self.assertTrue(all(
            len(line.encode("utf-8"))<=75 for line in ics.split("\r\n")
        ))
        self.assertEqual(agenda._ics([item],self.now),ics)

    def test_inactive_owner_is_denied(self):
        self.c.execute("UPDATE accounts SET status='suspended' WHERE email=?",(self.a,))
        self.c.commit()
        self.assertEqual(agenda.read(self.c,agenda.ROUTE,"participant",self.a)[1],403)


if __name__=="__main__":
    unittest.main()
