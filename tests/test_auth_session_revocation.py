"""Cross-role session security: revocation, current account and strict Bearer proof."""
import importlib
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import auth as account_auth

EMAIL = "session-security@example.test"


class AuthSessionRevocationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = patch.dict(os.environ, {
            "SQLITE_PATH": str(Path(self.temp.name) / "session-guard.db"),
            "DATABASE_URL": "",
            "PROMOMED_SEED_DEMO": "false",
            "PROMOMED_REQUIRE_POSTGRES": "false",
        })
        self.config.start()
        from app import db
        importlib.reload(db)
        self.db = db
        self.c = db.connect()
        db.migrate(self.c)
        now = int(time.time())
        self.c.execute(
            "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
            "VALUES(?,?,'partner','Test Partner','active',?,?)",
            (EMAIL, "synthetic-hash", now, now),
        )
        self.c.commit()

    def tearDown(self):
        self.c.close()
        self.config.stop()
        self.temp.cleanup()

    def bearer(self, token):
        return account_auth.auth(SimpleNamespace(
            headers={"Authorization": "Bearer " + token}
        ))

    def session(self):
        token, expiry = account_auth.issue_session(
            self.c, EMAIL, "partner", "Test Partner"
        )
        self.assertGreater(expiry, int(time.time()))
        self.assertEqual(self.bearer(token), ("partner", "Test Partner", EMAIL))
        return token

    def row(self, token):
        return self.c.execute(
            "SELECT revoked_at FROM auth_sessions WHERE token_hash=?",
            (account_auth.token_hash(token),),
        ).fetchone()

    def test_active_session_strict_token_and_expiry(self):
        token = self.session()
        for header in (
            token, "Basic " + token, "bearer " + token,
            "Bearer  " + token, "Bearer " + token + " " + token,
            "Bearer " + token + "\n", "Bearer " + "A" * 129,
            "Bearer " + "B" * 257,
        ):
            self.assertIsNone(account_auth.auth(
                SimpleNamespace(headers={"Authorization": header})
            ))
        self.assertIsNone(account_auth.auth(SimpleNamespace(headers={})))
        self.c.execute(
            "UPDATE auth_sessions SET expires_at=? WHERE token_hash=?",
            (int(time.time()) - 1, account_auth.token_hash(token)),
        )
        self.c.commit()
        self.assertIsNone(self.bearer(token))

    def test_account_suspension_revokes_token_immediately(self):
        token = self.session()
        self.c.execute(
            "UPDATE accounts SET status='suspended' WHERE email=?", (EMAIL,)
        )
        self.c.commit()
        self.assertIsNotNone(self.row(token)["revoked_at"])
        self.assertIsNone(self.bearer(token))
        self.c.execute(
            "UPDATE accounts SET status='active' WHERE email=?", (EMAIL,)
        )
        self.c.commit()
        self.assertIsNone(self.bearer(token))

    def test_role_change_revokes_session_and_blocks_replay(self):
        token = self.session()
        self.c.execute(
            "UPDATE accounts SET role='organizer' WHERE email=?", (EMAIL,)
        )
        self.c.commit()
        self.assertIsNotNone(self.row(token)["revoked_at"])
        self.assertIsNone(self.bearer(token))
        # Even if the database had a mismatched (incorrectly cached) session role,
        # the live account role is authoritative, not the session copy.
        other, _ = account_auth.issue_session(
            self.c, EMAIL, "partner", "Legacy Partner"
        )
        self.assertIsNone(self.bearer(other))
        self.assertEqual(self.row(other)["revoked_at"], None)

    def test_deleted_account_cannot_use_session(self):
        token = self.session()
        self.c.execute("DELETE FROM accounts WHERE email=?", (EMAIL,))
        self.c.commit()
        self.assertIsNone(self.bearer(token))
        self.assertIsNotNone(self.row(token)["revoked_at"])

    def test_update_rollback_restores_live_session(self):
        token = self.session()
        self.c.execute(
            "UPDATE accounts SET status='suspended' WHERE email=?", (EMAIL,)
        )
        self.c.rollback()
        self.assertIsNone(self.row(token)["revoked_at"])
        self.assertEqual(self.bearer(token), ("partner", "Test Partner", EMAIL))

    def test_migration_checksum_and_reapplication(self):
        status = self.db.migration_status(self.c)
        self.assertIn("029_auth_session_revocation", status["applied"])
        self.assertTrue(status["schema_ready"], status)
        repeated = self.db.migrate(self.c)
        self.assertTrue(repeated["schema_ready"], repeated)
        self.assertFalse(repeated["checksum_drift"])

    def test_legacy_role_mismatch_does_not_leak_via_auth(self):
        token = self.session()
        self.c.execute(
            "UPDATE auth_sessions SET role='organizer' WHERE token_hash=?",
            (account_auth.token_hash(token),),
        )
        self.c.commit()
        self.assertIsNone(self.bearer(token))


if __name__ == "__main__":
    unittest.main()
