import os
import unittest

from app import db
import server


class Header:
    def __init__(self, token):
        self.headers = {"Authorization": "Bearer " + token}


class PersistenceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server.init()

    def test_postgres_script_splitter_preserves_dollar_quoted_function(self):
        dq=chr(36)*2
        script="CREATE FUNCTION f() RETURNS trigger AS "+dq+" BEGIN RAISE EXCEPTION 'x'; END; "+dq+" LANGUAGE plpgsql; CREATE TABLE t(id INTEGER);"
        parts=db._split_postgres_script(script)
        self.assertEqual(len(parts),2)
        self.assertIn("RAISE EXCEPTION 'x'; END;",parts[0])
        self.assertTrue(parts[1].startswith("CREATE TABLE t"))

    def test_postgres_script_splitter_preserves_tagged_dollar_quote(self):
        script="CREATE FUNCTION f2() RETURNS text AS $func$ SELECT 'a;b'; $func$ LANGUAGE sql; CREATE TABLE t2(id INTEGER);"
        parts=db._split_postgres_script(script)
        self.assertEqual(len(parts),2)
        self.assertIn("SELECT 'a;b';",parts[0])
        self.assertTrue(parts[1].startswith("CREATE TABLE t2"))

    def test_schema_migrations_are_clean(self):
        status = db.migration_status()
        self.assertTrue(status["schema_ready"], status)
        self.assertEqual(status["missing"], [])
        self.assertEqual(status["checksum_drift"], [])
        self.assertIn("001_baseline", status["applied"])
        self.assertIn("002_staff_seed_identity", status["applied"])
        self.assertIn("003_account_authority", status["applied"])

    def test_seed_is_deterministic(self):
        c = server.conn()
        try:
            before = {
                "program": c.execute("SELECT COUNT(*) n FROM program_items").fetchone()["n"],
                "speakers": c.execute("SELECT COUNT(*) n FROM speakers").fetchone()["n"],
                "content": c.execute("SELECT COUNT(*) n FROM content_catalog").fetchone()["n"],
                "learning": c.execute("SELECT COUNT(*) n FROM learning_tracks").fetchone()["n"],
                "staff": c.execute("SELECT COUNT(*) n FROM staff_assignments").fetchone()["n"],
                "accounts": c.execute("SELECT COUNT(*) n FROM accounts").fetchone()["n"],
                "accounts": c.execute("SELECT COUNT(*) n FROM accounts").fetchone()["n"],
            }
        finally:
            c.close()
        server.init()
        c = server.conn()
        try:
            after = {
                "program": c.execute("SELECT COUNT(*) n FROM program_items").fetchone()["n"],
                "speakers": c.execute("SELECT COUNT(*) n FROM speakers").fetchone()["n"],
                "content": c.execute("SELECT COUNT(*) n FROM content_catalog").fetchone()["n"],
                "learning": c.execute("SELECT COUNT(*) n FROM learning_tracks").fetchone()["n"],
                "staff": c.execute("SELECT COUNT(*) n FROM staff_assignments").fetchone()["n"],
                "accounts": c.execute("SELECT COUNT(*) n FROM accounts").fetchone()["n"],
            }
        finally:
            c.close()
        self.assertEqual(before, after)
        self.assertGreaterEqual(after["program"], 42)
        self.assertGreaterEqual(after["accounts"], 9)

    def test_demo_account_authentication_is_database_backed(self):
        c = server.conn()
        try:
            account = server.authenticate(c, "participant@demo.ru", "demo2027")
            denied = server.authenticate(c, "participant@demo.ru", "wrong-password")
        finally:
            c.close()
        self.assertEqual(account["role"], "participant")
        self.assertEqual(account["name"], "Участник")
        self.assertIsNone(denied)

    def test_session_is_database_backed(self):
        c = server.conn()
        try:
            token, expires = server.issue_session(c, "participant@demo.ru", "participant", "Участник")
        finally:
            c.close()
        self.assertGreater(expires, 0)
        self.assertEqual(server.auth(Header(token)), ("participant", "Участник", "participant@demo.ru"))
        c = server.conn()
        try:
            row = c.execute(
                "SELECT email,role FROM auth_sessions WHERE token_hash=?",
                (server.token_hash(token),),
            ).fetchone()
        finally:
            c.close()
        self.assertEqual(row["email"], "participant@demo.ru")
        self.assertEqual(row["role"], "participant")

    def test_state_queries_work_on_selected_backend(self):
        c = server.conn()
        try:
            state = server.state(c, "participant@demo.ru")
        finally:
            c.close()
        self.assertGreaterEqual(len(state["program"]), 42)
        self.assertIn("notifications", state)
        self.assertIn("direct_messages", state)
        self.assertIn("profile", state)

    def test_readiness_backend_contract(self):
        status = db.readiness()
        self.assertTrue(status["schema_ready"])
        if db.backend_name() == "postgres":
            self.assertTrue(status["durable"])
            if db.demo_seed_enabled():
                self.assertFalse(status["production_ready"])
                self.assertGreater(status["demo_accounts"], 0)
            else:
                self.assertTrue(status["production_ready"])
        else:
            self.assertFalse(status["durable"])
            self.assertFalse(status["production_ready"])


if __name__ == "__main__":
    unittest.main()
