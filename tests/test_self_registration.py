"""REG-01 qualification for fail-closed participant self-registration."""
import importlib
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

    def test_expired_code_never_creates_account(self):
        payload, captured = self.request_with_code()
        c = self.db.connect()
        try:
            c.execute(
                "UPDATE participant_registration_requests SET expires_at=? WHERE id=?",
                (int(time.time()) - 1, payload["requestId"]),
            )
            c.commit()
        finally:
            c.close()
        result, status = self_registration.verify_registration({
            "request_id": payload["requestId"], "code": captured["code"]
        })
        self.assertEqual((result, status), ({"error": "invalid_verification"}, 422))
        self.assertEqual(self.count("accounts", "email=?", (self.email,)), 0)

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


if __name__ == "__main__":
    unittest.main()
