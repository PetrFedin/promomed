"""PostgreSQL 17 qualification for participant self-registration."""
import os
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
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

    def _pending_with_code(self):
        sent = {}

        def deliver(email, code, request_id):
            sent.update(email=email, code=code, request_id=request_id)

        with patch("app.self_registration.delivery_configured", return_value=True):
            with patch("app.self_registration.send_verification", side_effect=deliver):
                submitted, status = self_registration.request_registration(dict(self.payload))
        self.assertEqual(status, 202)
        return submitted["requestId"], sent["code"]

    def test_parallel_wrong_codes_increment_attempts_twice(self):
        request_id, code = self._pending_with_code()
        wrong = "000000" if code != "000000" else "111111"
        entered, second_started, release = Event(), Event(), Event()
        guard, calls = Lock(), [0]
        original_hash = self_registration._code_hash

        def held_hash(rid, value):
            with guard:
                calls[0] += 1
                is_first = calls[0] == 1
            if is_first:
                entered.set()
                if not release.wait(8):
                    raise AssertionError("first verifier was not released")
            return original_hash(rid, value)

        def verify():
            return self_registration.verify_registration({"request_id": request_id, "code": wrong})

        def second_verify():
            second_started.set()
            return verify()

        with patch("app.self_registration._code_hash", side_effect=held_hash):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(verify)
                try:
                    self.assertTrue(entered.wait(6))
                    second = pool.submit(second_verify)
                    self.assertTrue(second_started.wait(6))
                    time.sleep(0.25)
                    with guard:
                        self.assertEqual(calls[0], 1, "lock was bypassed")
                finally:
                    release.set()
                self.assertEqual(first.result(timeout=12)[1], 422)
                self.assertEqual(second.result(timeout=12)[1], 422)

        c = db.connect()
        try:
            record = c.execute(
                "SELECT attempts,status FROM participant_registration_requests WHERE id=?",
                (request_id,),
            ).fetchone()
            self.assertEqual(record["attempts"], 2)
            self.assertEqual(record["status"], "pending")
        finally:
            c.close()

    def test_parallel_signup_has_one_pending_mail(self):
        delivered, second_started, release = Event(), Event(), Event()
        guard, calls = Lock(), [0]

        def held_delivery(email, code, request_id):
            with guard:
                calls[0] += 1
            delivered.set()
            if not release.wait(8):
                raise AssertionError("first delivery was not released")

        def second_request():
            second_started.set()
            return self_registration.request_registration(dict(self.payload))

        with patch("app.self_registration.delivery_configured", return_value=True):
            with patch("app.self_registration.send_verification", side_effect=held_delivery):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    first = pool.submit(self_registration.request_registration, dict(self.payload))
                    try:
                        self.assertTrue(delivered.wait(6))
                        second = pool.submit(second_request)
                        self.assertTrue(second_started.wait(6))
                        time.sleep(0.25)
                        with guard:
                            self.assertEqual(calls[0], 1)
                    finally:
                        release.set()
                    result1 = first.result(timeout=12)
                    result2 = second.result(timeout=12)

        self.assertEqual((result1[1], result2[1]), (202, 202))
        self.assertNotEqual(result1[0]["requestId"], result2[0]["requestId"])
        with guard:
            self.assertEqual(calls[0], 1)
        c = db.connect()
        try:
            count = c.execute(
                "SELECT COUNT(*) n FROM participant_registration_requests "
                "WHERE email=? AND status='pending'",
                (self.email,),
            ).fetchone()["n"]
            self.assertEqual(int(count), 1)
        finally:
            c.close()

    def test_parallel_correct_code_issues_one_session(self):
        request_id, code = self._pending_with_code()
        entered, second_started, release = Event(), Event(), Event()
        original_hash = self_registration._code_hash

        def held_hash(rid, value):
            entered.set()
            if not release.wait(8):
                raise AssertionError("verification was not released")
            return original_hash(rid, value)

        def second_verify():
            second_started.set()
            return self_registration.verify_registration({"request_id": request_id, "code": code})

        with patch("app.self_registration._code_hash", side_effect=held_hash):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self_registration.verify_registration, {"request_id": request_id, "code": code})
                try:
                    self.assertTrue(entered.wait(6))
                    second = pool.submit(second_verify)
                    self.assertTrue(second_started.wait(6))
                finally:
                    release.set()
                results = [first.result(timeout=12), second.result(timeout=12)]

        self.assertEqual(sorted(status for _, status in results), [201, 422])
        c = db.connect()
        try:
            account = c.execute("SELECT COUNT(*) n FROM accounts WHERE email=?", (self.email,)).fetchone()["n"]
            sessions = c.execute("SELECT COUNT(*) n FROM auth_sessions WHERE email=?", (self.email,)).fetchone()["n"]
            self.assertEqual(int(account), 1)
            self.assertEqual(int(sessions), 1)
        finally:
            c.close()


if __name__ == "__main__":
    unittest.main()
