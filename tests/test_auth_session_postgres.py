"""Real PostgreSQL 17 account-role and status revocation proof (CI only)."""
import secrets
import time
import unittest
from types import SimpleNamespace
from app import auth as account_auth
from app import db


class PostgresSessionAuthorityTests(unittest.TestCase):
    def test_pg_role_status_and_deletion_revoke_immediately(self):
        if db.backend_name() != "postgres":
            self.skipTest("real PostgreSQL 17 workflow only")
        c = db.connect()
        email = "security-ci-" + secrets.token_hex(7) + "@example.test"
        try:
            db.migrate(c)
            now = int(time.time())
            c.execute(
                "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
                "VALUES(?,?,'partner','PG Test','active',?,?)",
                (email, "synthetic-password-hash", now, now),
            )
            c.commit()
            def issue(role):
                t, _ = account_auth.issue_session(c, email, role, "PG Test")
                return t

            def access(t):
                return account_auth.auth(SimpleNamespace(
                    headers={"Authorization": "Bearer " + t}
                ))

            def revoked(t):
                row = c.execute(
                    "SELECT revoked_at FROM auth_sessions WHERE token_hash=?",
                    (account_auth.token_hash(t),),
                ).fetchone()
                return row["revoked_at"] if row else None

            token1 = issue("partner")
            self.assertEqual(access(token1), ("partner", "PG Test", email))
            c.execute(
                "UPDATE accounts SET status='suspended' WHERE email=?", (email,)
            )
            c.rollback()
            self.assertIsNone(revoked(token1))
            self.assertEqual(access(token1), ("partner", "PG Test", email))
            c.execute(
                "UPDATE accounts SET role='organizer' WHERE email=?", (email,)
            )
            c.commit()
            self.assertIsNotNone(revoked(token1))
            self.assertIsNone(access(token1))
            token2 = issue("organizer")
            self.assertEqual(access(token2), ("organizer", "PG Test", email))
            c.execute(
                "UPDATE accounts SET status='suspended' WHERE email=?", (email,)
            )
            c.commit()
            self.assertIsNotNone(revoked(token2))
            self.assertIsNone(access(token2))
            c.execute(
                "UPDATE accounts SET status='active' WHERE email=?", (email,)
            )
            c.commit()
            self.assertIsNone(access(token2))
            token3 = issue("organizer")
            self.assertEqual(access(token3), ("organizer", "PG Test", email))
            c.execute("DELETE FROM accounts WHERE email=?", (email,))
            c.commit()
            self.assertIsNotNone(revoked(token3))
            self.assertIsNone(access(token3))
            self.assertIn(
                "029_auth_session_revocation",
                db.migration_status(c)["applied"],
            )
        finally:
            c.rollback()
            c.execute("DELETE FROM auth_sessions WHERE email=?", (email,))
            c.execute("DELETE FROM accounts WHERE email=?", (email,))
            c.commit()
            c.close()


if __name__ == "__main__":
    unittest.main()
