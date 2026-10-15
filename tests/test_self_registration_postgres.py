"""PostgreSQL 17 qualification for participant self-registration."""
import os
import unittest
import uuid
from unittest.mock import patch

from app import db, self_registration


@unittest.skipUnless(
    os.environ.get("PROMOMED_REGISTRATION_PG_TEST") == "1",
    "dedicated PostgreSQL registration qualification only",
)
class ParticipantRegistrationPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if db.backend_name() != "postgres":
            raise RuntimeError("postgres_required")
        cls.c = db.connect()
        db.migrate(cls.c)

    @classmethod
    def tearDownClass(cls):
        cls.c.close()

    def setUp(self):
        self.suffix = uuid.uuid4().hex[:10]
        self.email = "pg-" + self.suffix + "@example.test"
        self.payload = {
            "email": self.email,
            "name": "PG Participant",
            "password": "StrongPgRegistration!42",
        }

    def tearDown(self):
        c = db.connect()
        try:
            c.execute(
                "DELETE FROM participant_registration_requests WHERE email=?",
                (self.email,),
            )
            c.execute("DELETE FROM auth_sessions WHERE email=?", (self.email,))
            c.execute("DELETE FROM accounts WHERE email=?", (self.email,))
            c.execute("DELETE FROM registrations WHERE email=?", (self.email,))
            c.commit()
        finally:
            c.close()

    def test_pending_then_verified_account_without_event_registration(self):
        sent = {}
        def deliver(email, code, request_id):
            sent.update(email=email, code=code, request_id=request_id)

        with patch("app.self_registration.delivery_configured", return_value=True):
            with patch("app.self_registration.send_verification", side_effect=deliver):
                requested, status = self_registration.request_registration(
                    dict(self.payload)
                )
        self.assertEqual(status, 202)
        self.assertEqual(requested["requestId"], sent["request_id"])

        c = db.connect()
        try:
            pending = c.execute(
                "SELECT status,verification_hash FROM participant_registration_requests "
                "WHERE email=?", (self.email,)
            ).fetchone()
            self.assertEqual(pending["status"], "pending")
            self.assertEqual(len(pending["verification_hash"]), 64)
            self.assertIsNone(
                c.execute("SELECT 1 FROM accounts WHERE email=?", (self.email,)).fetchone()
            )
        finally:
            c.close()

        verified, status = self_registration.verify_registration({
            "request_id": requested["requestId"],
            "code": sent["code"],
        })
        self.assertEqual(status, 201)
        self.assertTrue(verified["verified"])
        self.assertFalse(verified["eventRegistration"])
        self.assertTrue(verified["token"])

        c = db.connect()
        try:
            account = c.execute(
                "SELECT role,status FROM accounts WHERE email=?", (self.email,)
            ).fetchone()
            self.assertEqual(dict(account), {"role": "participant", "status": "active"})
            self.assertIsNone(
                c.execute("SELECT 1 FROM registrations WHERE email=?", (self.email,)).fetchone()
            )
            sessions = c.execute(
                "SELECT COUNT(*) n FROM auth_sessions WHERE email=? AND revoked_at IS NULL",
                (self.email,),
            ).fetchone()["n"]
            self.assertEqual(int(sessions), 1)
            terminal = c.execute(
                "SELECT status,password_hash,verification_hash FROM "
                "participant_registration_requests WHERE email=?", (self.email,)
            ).fetchone()
            self.assertEqual(terminal["status"], "verified")
            self.assertEqual(terminal["password_hash"], "")
            self.assertEqual(terminal["verification_hash"], "")
        finally:
            c.close()


if __name__ == "__main__":
    unittest.main()
