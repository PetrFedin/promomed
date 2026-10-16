"""REG-02 qualification for capacity-aware event registration."""
import importlib
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app import event_registration, programme_commands
from app.auth import hash_password


class EventRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "SQLITE_PATH": str(Path(self.temp.name) / "events.db"),
            "DATABASE_URL": "",
            "PROMOMED_SEED_DEMO": "false",
            "PROMOMED_REQUIRE_POSTGRES": "false",
        })
        self.env.start()
        from app import db
        importlib.reload(db)
        importlib.reload(event_registration)
        importlib.reload(programme_commands)
        self.db = db
        self.c = db.connect()
        db.migrate(self.c)
        now = int(time.time())
        self.users = ("a@example.test", "b@example.test", "c@example.test")
        for email in self.users:
            self.c.execute(
                "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
                "VALUES(?,?,'participant',?,'active',?,?)",
                (email, hash_password("StrongEventTest!42"), email, now, now),
            )
        self.c.execute(
            "INSERT INTO event_editions_v1("
            "id,title,starts_at,registration_status,capacity,demo_only,created_at,updated_at"
            ") VALUES('EV1','Flagship',?,'open',1,0,?,?)",
            (now + 86400, now, now),
        )
        self.c.commit()

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.temp.cleanup()

    def command(self, email, action, event_id="EV1"):
        out = event_registration.handle_command(
            self.c, event_registration.ROUTE, "participant", email,
            {"event_id": event_id, "action": action},
        )
        self.c.commit()
        return out

    def status(self, email):
        row = self.c.execute(
            "SELECT status FROM participant_event_registrations_v1 "
            "WHERE event_id='EV1' AND email=?", (email,),
        ).fetchone()
        return row["status"] if row else None

    def test_capacity_waitlist_cancel_and_promotion(self):
        first = self.command(self.users[0], "register")
        second = self.command(self.users[1], "register")
        self.assertEqual(first.status, 201)
        self.assertEqual(second.status, 201)
        self.assertEqual(first.payload["registration"]["status"], "confirmed")
        self.assertEqual(second.payload["registration"]["status"], "waitlist")
        self.assertEqual(self.status(self.users[0]), "confirmed")
        self.assertEqual(self.status(self.users[1]), "waitlist")

        cancelled = self.command(self.users[0], "cancel")
        self.assertTrue(cancelled.payload["queuePromotionOccurred"])
        self.assertEqual(self.status(self.users[0]), "cancelled")
        self.assertEqual(self.status(self.users[1]), "confirmed")

    def test_transition_history_records_waitlist_promotion_and_cancellation(self):
        self.command(self.users[0], "register")
        self.command(self.users[1], "register")
        self.command(self.users[1], "register")  # idempotent, no event
        self.command(self.users[0], "cancel")   # promotes waiting owner
        for email, expected in (
            (self.users[0], [(None, "confirmed"), ("confirmed", "cancelled")]),
            (self.users[1], [(None, "waitlist"), ("waitlist", "confirmed")]),
        ):
            rows=list(self.c.execute(
                "SELECT previous_status,next_status FROM event_registration_transitions_v1 "
                "WHERE event_id='EV1' AND email=? ORDER BY transition_no", (email,),
            ))
            self.assertEqual([(r["previous_status"],r["next_status"]) for r in rows],expected)
        with self.assertRaises(Exception):
            self.c.execute(
                "UPDATE event_registration_transitions_v1 SET next_status='cancelled' "
                "WHERE event_id='EV1' AND email=?", (self.users[1],),
            )
        self.c.rollback()

    def test_transition_history_erased_with_parent_account(self):
        self.command(self.users[0], "register")
        self.c.execute("DELETE FROM accounts WHERE email=?", (self.users[0],))
        self.c.commit()
        n=self.c.execute("SELECT COUNT(*) n FROM event_registration_transitions_v1 "
                         "WHERE email=?", (self.users[0],)).fetchone()["n"]
        self.assertEqual(n,0)

    def test_repeated_register_is_idempotent_without_queue_duplication(self):
        first = self.command(self.users[0], "register")
        requested = first.payload["registration"]["requestedAt"]
        replay = self.command(self.users[0], "register")
        self.assertEqual(replay.status, 200)
        self.assertTrue(replay.payload["replayed"])
        self.assertEqual(replay.payload["registration"]["requestedAt"], requested)
        n = self.c.execute(
            "SELECT COUNT(*) n FROM participant_event_registrations_v1 "
            "WHERE event_id='EV1' AND email=?", (self.users[0],),
        ).fetchone()["n"]
        self.assertEqual(int(n), 1)

    def test_closed_and_waitlist_only_event_semantics(self):
        self.c.execute(
            "UPDATE event_editions_v1 SET registration_status='closed' WHERE id='EV1'"
        )
        self.c.commit()
        closed = self.command(self.users[0], "register")
        self.assertEqual((closed.status, closed.payload["error"]), (409, "registration_closed"))

        self.c.execute(
            "UPDATE event_editions_v1 SET registration_status='waitlist_only' WHERE id='EV1'"
        )
        self.c.commit()
        wait = self.command(self.users[1], "register")
        self.assertEqual(wait.payload["registration"]["status"], "waitlist")

    def test_read_returns_only_current_participant_registration(self):
        self.command(self.users[0], "register")
        self.command(self.users[1], "register")
        payload, status = event_registration.read(
            self.c, event_registration.ROUTE, "participant", self.users[0]
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["events"]), 1)
        self.assertEqual(payload["events"][0]["myStatus"], "confirmed")
        self.assertNotIn(self.users[1], str(payload))
        self.assertNotIn("attendance", str(payload["events"]).lower())
        self.assertTrue(payload["truthBoundary"]["registrationIsNotAttendance"])
        self.assertFalse(payload["truthBoundary"]["marketingConsent"])

    def test_foreign_roles_and_query_selectors_are_rejected(self):
        payload, status = event_registration.read(
            self.c, event_registration.ROUTE + "?email=b@example.test",
            "participant", self.users[0],
        )
        self.assertEqual((payload, status), ({"error": "unsupported_query"}, 422))
        out = event_registration.handle_command(
            self.c, event_registration.ROUTE, "partner", "partner@example.test",
            {"event_id": "EV1", "action": "register"},
        )
        self.assertEqual(out.status, 403)

    def test_legacy_register_is_not_available_outside_demo(self):
        out = programme_commands.handle_command(
            self.c, "/api/register", "participant", self.users[0], {}
        )
        self.assertEqual(out.status, 404)
        self.assertEqual(out.payload["error"], "not_found")
        self.assertIsNone(
            self.c.execute(
                "SELECT 1 FROM registrations WHERE email=?", (self.users[0],)
            ).fetchone()
        )

    def test_sqlite_parent_guards_reject_orphan_registration(self):
        with self.assertRaises(Exception):
            self.c.execute(
                "INSERT INTO participant_event_registrations_v1("
                "event_id,email,status,requested_at,updated_at,source"
                ") VALUES('MISSING',?,'confirmed',1,1,'participant')",
                (self.users[0],),
            )
        self.c.rollback()
        with self.assertRaises(Exception):
            self.c.execute(
                "INSERT INTO participant_event_registrations_v1("
                "event_id,email,status,requested_at,updated_at,source"
                ") VALUES('EV1','missing@example.test','confirmed',1,1,'participant')"
            )
        self.c.rollback()

    def test_account_creation_is_still_separate_from_event_registration(self):
        self.assertIsNone(self.status(self.users[2]))
        payload, status = event_registration.read(
            self.c, event_registration.ROUTE, "participant", self.users[2]
        )
        self.assertEqual(status, 200)
        self.assertIsNone(payload["events"][0]["myStatus"])


if __name__ == "__main__":
    unittest.main()
