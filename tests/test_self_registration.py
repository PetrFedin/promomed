"""REG-01 qualification for fail-closed participant self-registration."""
import importlib
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import self_registration


class ParticipantSelfRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "SQLITE_PATH": str(Path(self.temp.name) / "registration.db"),
            "DATABASE_URL": "",
            "PROMOMED_SEED_DEMO": "false",
            "PROMOMED_REQUIRE_POSTGRES": "false",
            "PROMOMED_REGISTRATION_CODE_SECRET": "ci-registration-secret-value",
            "PROMOMED_REGISTRATION_SMTP_HOST": "smtp.example.test",
            "PROMOMED_REGISTRATION_FROM_EMAIL": "noreply@example.test",
        })
        self.env.start()
        from app import db
        importlib.reload(db)
        importlib.reload(self_registration)
        self.db = db
        self.c = db.connect()
        db.migrate(self.c)
        self.c.close()
        self.email = "new-participant@example.test"
        self.payload = {
            "email": self.email,
            "name": "Новый участник",
            "password": "StrongRegistration!42",
        }

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def count(self, table, where="", args=()):
        c = self.db.connect()
        try:
            sql = "SELECT COUNT(*) n FROM " + table
            if where:
                sql += " WHERE " + where
            return int(c.execute(sql, args).fetchone()["n"])
        finally:
            c.close()

    def request_with_code(self):
        captured = {}
        def send(email, code, request_id):
            captured.update(email=email, code=code, request_id=request_id)
        with patch("app.self_registration.delivery_configured", return_value=True):
            with patch("app.self_registration.send_verification", side_effect=send):
                payload, status = self_registration.request_registration(dict(self.payload))
        self.assertEqual(status, 202)
        self.assertEqual(payload["accepted"], True)
        self.assertEqual(payload["requestId"], captured["request_id"])
        self.assertEqual(captured["email"], self.email)
        self.assertRegex(captured["code"], r"^[0-9]{6}$")
        return payload, captured

    def test_request_creates_pending_only_then_verify_creates_account_and_session(self):
        payload, captured = self.request_with_code()
        self.assertEqual(self.count("accounts", "email=?", (self.email,)), 0)
        self.assertEqual(
            self.count(
                "participant_registration_requests",
                "email=? AND status='pending'", (self.email,)
            ), 1
        )
        c = self.db.connect()
        try:
            pending = c.execute(
                "SELECT password_hash,verification_hash FROM participant_registration_requests "
                "WHERE email=?", (self.email,)
            ).fetchone()
            self.assertTrue(pending["password_hash"].startswith("scrypt$"))
            self.assertEqual(len(pending["verification_hash"]), 64)
            self.assertNotEqual(pending["verification_hash"], captured["code"])
        finally:
            c.close()
        result, status = self_registration.verify_registration({
            "request_id": payload["requestId"], "code": captured["code"]
        })
        self.assertEqual(status, 201)
        self.assertTrue(result["verified"])
        self.assertEqual(result["role"], "participant")
        self.assertFalse(result["eventRegistration"])
        self.assertTrue(result["token"])
        self.assertEqual(self.count("accounts", "email=?", (self.email,)), 1)
        self.assertEqual(self.count("registrations", "email=?", (self.email,)), 0)
        c = self.db.connect()
        try:
            terminal = c.execute(
                "SELECT status,password_hash,verification_hash FROM "
                "participant_registration_requests WHERE email=?", (self.email,)
            ).fetchone()
            self.assertEqual(terminal["status"], "verified")
            self.assertEqual(terminal["password_hash"], "")
            self.assertEqual(terminal["verification_hash"], "")
        finally:
            c.close()

    def test_existing_account_has_same_public_response_shape_and_no_delivery(self):
        c = self.db.connect()
        now = int(time.time())
        try:
            from app.auth import hash_password
            c.execute(
                "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
                "VALUES(?,?, 'participant','Existing','active',?,?)",
                (self.email, hash_password("DifferentStrong!42"), now, now),
            )
            c.commit()
        finally:
            c.close()
        with patch("app.self_registration.delivery_configured", return_value=True):
            with patch(
                "app.self_registration.send_verification",
                side_effect=AssertionError("must not deliver"),
            ):
                result, status = self_registration.request_registration(dict(self.payload))
        self.assertEqual(status, 202)
        self.assertEqual(
            set(result),
            {"accepted", "next", "expiresInSeconds", "requestId"},
        )
        self.assertEqual(len(result["requestId"]), 32)
        self.assertEqual(self.count("participant_registration_requests"), 0)

    def test_delivery_failure_rolls_back_pending_request(self):
        with patch("app.self_registration.delivery_configured", return_value=True):
            with patch(
                "app.self_registration.send_verification",
                side_effect=RuntimeError("provider_down"),
            ):
                result, status = self_registration.request_registration(dict(self.payload))
        self.assertEqual((result, status), ({"error": "registration_delivery_failed"}, 503))
        self.assertEqual(self.count("participant_registration_requests"), 0)
        self.assertEqual(self.count("accounts"), 0)

    def test_non_demo_without_delivery_or_secret_fails_before_db_write(self):
        with patch.dict(os.environ, {
            "PROMOMED_REGISTRATION_CODE_SECRET": "",
            "PROMOMED_REGISTRATION_SMTP_HOST": "",
            "PROMOMED_REGISTRATION_FROM_EMAIL": "",
        }):
            result, status = self_registration.request_registration(dict(self.payload))
        self.assertEqual(
            (result, status),
            ({"error": "registration_delivery_unavailable"}, 503),
        )
        self.assertEqual(self.count("participant_registration_requests"), 0)

    def test_five_bad_codes_block_request_and_correct_code_no_longer_works(self):
        payload, captured = self.request_with_code()
        for i in range(5):
            result, status = self_registration.verify_registration({
                "request_id": payload["requestId"],
                "code": f"{i:06d}" if f"{i:06d}" != captured["code"] else "999999",
            })
            self.assertEqual((result, status), ({"error": "invalid_verification"}, 422))
        result, status = self_registration.verify_registration({
            "request_id": payload["requestId"], "code": captured["code"]
        })
        self.assertEqual((result, status), ({"error": "invalid_verification"}, 422))
        self.assertEqual(self.count("accounts", "email=?", (self.email,)), 0)
        c = self.db.connect()
        try:
            terminal = c.execute(
                "SELECT status,password_hash,verification_hash FROM "
                "participant_registration_requests WHERE email=?", (self.email,)
            ).fetchone()
            self.assertEqual(terminal["status"], "blocked")
            self.assertEqual(terminal["password_hash"], "")
            self.assertEqual(terminal["verification_hash"], "")
        finally:
            c.close()

    def test_expired_code_never_creates_account(self):
        payload, captured = self.request_with_code()
        c = self.db.connect()
        try:
            now = int(time.time())
            c.execute(
                "UPDATE participant_registration_requests "
                "SET created_at=?,expires_at=? WHERE id=?",
                (now - 601, now - 1, payload["requestId"]),
            )
            c.commit()
        finally:
            c.close()
        result, status = self_registration.verify_registration({
            "request_id": payload["requestId"], "code": captured["code"]
        })
        self.assertEqual((result, status), ({"error": "invalid_verification"}, 422))
        self.assertEqual(self.count("accounts", "email=?", (self.email,)), 0)
        c = self.db.connect()
        try:
            terminal = c.execute(
                "SELECT status,password_hash,verification_hash FROM "
                "participant_registration_requests WHERE email=?", (self.email,)
            ).fetchone()
            self.assertEqual(terminal["status"], "expired")
            self.assertEqual(terminal["password_hash"], "")
            self.assertEqual(terminal["verification_hash"], "")
        finally:
            c.close()

    def test_invalid_payload_never_opens_delivery(self):
        bad = dict(self.payload)
        bad["password"] = "short"
        with patch(
            "app.self_registration.send_verification",
            side_effect=AssertionError("delivery called"),
        ):
            result, status = self_registration.request_registration(bad)
        self.assertEqual(
            (result, status),
            ({"error": "invalid_registration_request"}, 422),
        )

    def test_public_http_dispatch_happens_before_auth(self):
        import server
        h = SimpleNamespace(
            path=self_registration.REQUEST_ROUTE,
            out=lambda value, status=200: (value, status),
        )
        expected = {"accepted": True}
        with patch("server.body", return_value=dict(self.payload)):
            with patch("server.auth", side_effect=AssertionError("auth queried")):
                with patch(
                    "server.handle_self_registration_public",
                    return_value=(expected, 202),
                ):
                    self.assertEqual(server.H.do_POST(h), (expected, 202))

    def test_parallel_wrong_codes_do_not_lose_attempts(self):
        submitted, sent = self.request_with_code()
        bad = "000000" if sent["code"] != "000000" else "111111"
        entered, second_started, release = Event(), Event(), Event()
        guard, count = Lock(), [0]
        original_hash = self_registration._code_hash

        def held_hash(request_id, code):
            with guard:
                count[0] += 1
                is_first = count[0] == 1
            if is_first:
                entered.set()
                if not release.wait(8):
                    raise AssertionError("first verification was not released")
            return original_hash(request_id, code)

        payload = {"request_id": submitted["requestId"], "code": bad}

        def second_verify():
            second_started.set()
            return self_registration.verify_registration(dict(payload))

        with patch("app.self_registration._code_hash", side_effect=held_hash):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self_registration.verify_registration, dict(payload))
                try:
                    self.assertTrue(entered.wait(6), "first verifier did not start")
                    second = pool.submit(second_verify)
                    self.assertTrue(second_started.wait(6))
                    time.sleep(0.25)
                    with guard:
                        self.assertEqual(count[0], 1, "second verifier bypassed the lock")
                finally:
                    release.set()
                self.assertEqual(first.result(timeout=12)[1], 422)
                self.assertEqual(second.result(timeout=12)[1], 422)

        c = self.db.connect()
        try:
            record = c.execute(
                "SELECT attempts,status FROM participant_registration_requests WHERE id=?",
                (submitted["requestId"],),
            ).fetchone()
            self.assertEqual(record["attempts"], 2)
            self.assertEqual(record["status"], "pending")
        finally:
            c.close()

    def test_parallel_signup_delivers_only_one_pending_code(self):
        delivered, second_started, release = Event(), Event(), Event()
        guard, count = Lock(), [0]

        def held_delivery(email, code, request_id):
            with guard:
                count[0] += 1
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
                            self.assertEqual(count[0], 1)
                    finally:
                        release.set()
                    result1 = first.result(timeout=12)
                    result2 = second.result(timeout=12)

        self.assertEqual((result1[1], result2[1]), (202, 202))
        with guard:
            self.assertEqual(count[0], 1)
        self.assertNotEqual(result1[0]["requestId"], result2[0]["requestId"])
        self.assertEqual(
            self.count("participant_registration_requests",
                       "email=? AND status='pending'", (self.email,)),
            1,
        )

    def test_parallel_correct_code_creates_only_one_account(self):
        submitted, sent = self.request_with_code()
        entered, second_started, release = Event(), Event(), Event()
        original_hash = self_registration._code_hash

        def held_hash(request_id, code):
            entered.set()
            if not release.wait(8):
                raise AssertionError("verification was not released")
            return original_hash(request_id, code)

        payload = {"request_id": submitted["requestId"], "code": sent["code"]}

        def second_verify():
            second_started.set()
            return self_registration.verify_registration(dict(payload))

        with patch("app.self_registration._code_hash", side_effect=held_hash):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self_registration.verify_registration, dict(payload))
                try:
                    self.assertTrue(entered.wait(6))
                    second = pool.submit(second_verify)
                    self.assertTrue(second_started.wait(6))
                finally:
                    release.set()
                results = [first.result(timeout=12), second.result(timeout=12)]

        self.assertEqual(sorted(status for _, status in results), [201, 422])
        self.assertEqual(self.count("accounts", "email=?", (self.email,)), 1)
        self.assertEqual(self.count("auth_sessions", "email=?", (self.email,)), 1)


if __name__ == "__main__":
    unittest.main()
