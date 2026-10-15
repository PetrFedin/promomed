"""PostgreSQL 17 concurrency proof for event registration capacity."""
import os
import threading
import time
import unittest
import uuid

from app import db, event_registration
from app.auth import hash_password


@unittest.skipUnless(
    os.environ.get("PROMOMED_EVENT_REGISTRATION_PG_TEST") == "1",
    "dedicated PostgreSQL event registration qualification only",
)
class EventRegistrationPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if db.backend_name() != "postgres":
            raise RuntimeError("postgres_required")
        c = db.connect()
        try:
            db.migrate(c)
        finally:
            c.close()

    def setUp(self):
        suffix = uuid.uuid4().hex[:10]
        self.event_id = "EV-" + suffix
        self.users = (
            "a-" + suffix + "@example.test",
            "b-" + suffix + "@example.test",
        )
        now = int(time.time())
        c = db.connect()
        try:
            for email in self.users:
                c.execute(
                    "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
                    "VALUES(?,?,'participant',?,'active',?,?)",
                    (email, hash_password("StrongEventPg!42"), email, now, now),
                )
            c.execute(
                "INSERT INTO event_editions_v1("
                "id,title,starts_at,registration_status,capacity,demo_only,created_at,updated_at"
                ") VALUES(?,?,?,'open',1,0,?,?)",
                (self.event_id, "Concurrent Event", now + 86400, now, now),
            )
            c.commit()
        finally:
            c.close()

    def tearDown(self):
        c = db.connect()
        try:
            c.execute(
                "DELETE FROM participant_event_registrations_v1 WHERE event_id=?",
                (self.event_id,),
            )
            c.execute("DELETE FROM event_editions_v1 WHERE id=?", (self.event_id,))
            for email in self.users:
                c.execute("DELETE FROM auth_sessions WHERE email=?", (email,))
                c.execute("DELETE FROM accounts WHERE email=?", (email,))
            c.commit()
        finally:
            c.close()

    def test_two_concurrent_requests_cannot_both_take_last_place(self):
        barrier = threading.Barrier(2)
        outcomes = {}
        errors = []

        def register(email):
            c = db.connect()
            try:
                barrier.wait(timeout=5)
                out = event_registration.handle_command(
                    c, event_registration.ROUTE, "participant", email,
                    {"event_id": self.event_id, "action": "register"},
                )
                c.commit()
                outcomes[email] = out.payload["registration"]["status"]
            except Exception as exc:
                try:
                    c.rollback()
                except Exception:
                    pass
                errors.append(repr(exc))
            finally:
                c.close()

        threads = [threading.Thread(target=register, args=(email,)) for email in self.users]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        self.assertFalse(errors, errors)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(sorted(outcomes.values()), ["confirmed", "waitlist"])

        c = db.connect()
        try:
            confirmed = c.execute(
                "SELECT COUNT(*) n FROM participant_event_registrations_v1 "
                "WHERE event_id=? AND status='confirmed'", (self.event_id,)
            ).fetchone()["n"]
            waitlist = c.execute(
                "SELECT COUNT(*) n FROM participant_event_registrations_v1 "
                "WHERE event_id=? AND status='waitlist'", (self.event_id,)
            ).fetchone()["n"]
            self.assertEqual((int(confirmed), int(waitlist)), (1, 1))
        finally:
            c.close()


if __name__ == "__main__":
    unittest.main()
