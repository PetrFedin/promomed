import importlib
import os
import secrets
import time
import unittest

from app import db

ORIGINAL_DATABASE_URL = os.environ.get("DATABASE_URL")
ORIGINAL_SQLITE_PATH = os.environ.get("SQLITE_PATH")
from app.auth import hash_password, issue_session, token_hash
from app.commanding import finalize_command
from app.my_workspace import (
    DELETE_ROUTE, LOGOUT_ROUTE, NOTE_ROUTE, PAGE_PREFIX, READ_ROUTE,
    handle_command, read,
)


class MyStateV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Other explicit test modules may temporarily reload app.db against
        # disposable paths. Restore the workflow-selected backend before this
        # suite so test order cannot select a deleted database.
        if ORIGINAL_DATABASE_URL is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = ORIGINAL_DATABASE_URL
        if ORIGINAL_SQLITE_PATH is None:
            os.environ.pop("SQLITE_PATH", None)
        else:
            os.environ["SQLITE_PATH"] = ORIGINAL_SQLITE_PATH
        importlib.reload(db)
        db.migrate()

    def setUp(self):
        self.c = db.connect()
        self.a = "workspace-a-" + secrets.token_hex(5) + "@example.test"
        self.b = "workspace-b-" + secrets.token_hex(5) + "@example.test"
        now = int(time.time())
        for email, name in ((self.a, "Workspace A"), (self.b, "Workspace B")):
            self.c.execute(
                "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
                "VALUES(?,?, 'participant', ?, 'active', ?, ?)",
                (email, hash_password("T3st-pass!"), name, now, now),
            )
        self.c.execute(
            "INSERT INTO registrations(email,status,ts) VALUES(?, 'confirmed', ?)",
            (self.a, now),
        )
        self.c.execute(
            "INSERT INTO activity_bookings(email,item_id,status,ts) "
            "VALUES(?, 'P01', 'booked', ?)",
            (self.a, now),
        )
        self.c.commit()

    def tearDown(self):
        self.c.rollback()
        for email in (self.a, self.b):
            self.c.execute("DELETE FROM auth_sessions WHERE email=?", (email,))
            self.c.execute("DELETE FROM activity_bookings WHERE email=?", (email,))
            self.c.execute("DELETE FROM registrations WHERE email=?", (email,))
            self.c.execute("DELETE FROM accounts WHERE email=?", (email,))
        self.c.commit()
        self.c.close()

    def command(self, route, email, data):
        out = handle_command(self.c, route, "participant", email, data)
        self.assertIsNotNone(out)
        finalize_command(self.c, out)
        return out

    def test_read_returns_only_current_account_records(self):
        self.command(
            NOTE_ROUTE, self.a,
            {"text": "alpha-private", "request_id": secrets.token_hex(16)},
        )
        self.command(
            NOTE_ROUTE, self.b,
            {"text": "beta-private", "request_id": secrets.token_hex(16)},
        )
        payload, status = read(self.c, READ_ROUTE, "participant", self.a)
        self.assertEqual(status, 200)
        self.assertEqual(payload["account"]["email"], self.a)
        self.assertEqual(payload["registration"]["status"], "confirmed")
        self.assertEqual(payload["bookings"][0]["item_id"], "P01")
        rendered = str(payload)
        self.assertIn("alpha-private", rendered)
        self.assertNotIn("beta-private", rendered)
        self.assertNotIn(self.b, rendered)
        self.assertTrue(payload["truthBoundary"]["ownAccountOnly"])
        self.assertFalse(payload["truthBoundary"]["medicalInference"])

    def test_foreign_role_and_suspended_account_are_denied(self):
        self.assertEqual(read(self.c, READ_ROUTE, "partner", self.a)[1], 403)
        self.c.execute(
            "UPDATE accounts SET status='suspended' WHERE email=?", (self.a,)
        )
        self.c.commit()
        self.assertEqual(read(self.c, READ_ROUTE, "participant", self.a)[1], 403)

    def test_idempotent_note_retry_and_conflict(self):
        key = secrets.token_hex(16)
        one = self.command(NOTE_ROUTE, self.a, {"text": "same", "request_id": key})
        two = self.command(NOTE_ROUTE, self.a, {"text": "same", "request_id": key})
        conflict = handle_command(
            self.c, NOTE_ROUTE, "participant", self.a,
            {"text": "different", "request_id": key},
        )
        self.assertEqual((one.status, two.status, conflict.status), (201, 200, 409))
        self.assertEqual(one.payload["note"], two.payload["note"])
        self.assertEqual(
            self.c.execute(
                "SELECT COUNT(*) n FROM personal_notes_v1 WHERE email=?",
                (self.a,),
            ).fetchone()["n"],
            1,
        )
        self.c.rollback()

    def test_delete_is_owner_scoped_and_retry_cannot_resurrect(self):
        key = secrets.token_hex(16)
        note = self.command(
            NOTE_ROUTE, self.a, {"text": "erase", "request_id": key}
        ).payload["note"]
        foreign = handle_command(
            self.c, DELETE_ROUTE, "participant", self.b, {"id": note["id"]}
        )
        self.assertEqual(foreign.status, 404)
        self.c.rollback()
        deleted = self.command(
            DELETE_ROUTE, self.a, {"id": note["id"]}
        )
        self.assertEqual(deleted.status, 200)
        replay = handle_command(
            self.c, NOTE_ROUTE, "participant", self.a,
            {"text": "erase", "request_id": key},
        )
        self.assertEqual(replay.status, 409)
        self.c.rollback()
        row = self.c.execute(
            "SELECT body,deleted_at FROM personal_notes_v1 WHERE id=?",
            (note["id"],),
        ).fetchone()
        self.assertEqual(row["body"], "")
        self.assertIsNotNone(row["deleted_at"])

    def test_foreign_or_missing_page_cursor_has_same_shape(self):
        foreign_note = self.command(
            NOTE_ROUTE, self.b,
            {"text": "beta", "request_id": secrets.token_hex(16)},
        ).payload["note"]
        a = read(
            self.c, PAGE_PREFIX + foreign_note["id"], "participant", self.a
        )
        b = read(
            self.c, PAGE_PREFIX + secrets.token_hex(16), "participant", self.a
        )
        self.assertEqual(a, b)
        self.assertEqual(a, ({"error": "not_found"}, 404))

    def test_logout_all_revokes_only_current_account(self):
        token_a1, _ = issue_session(self.c, self.a, "participant", "Workspace A")
        token_a2, _ = issue_session(self.c, self.a, "participant", "Workspace A")
        token_b, _ = issue_session(self.c, self.b, "participant", "Workspace B")
        out = self.command(LOGOUT_ROUTE, self.a, {})
        self.assertEqual(out.payload["scope"], "all_account_sessions")
        for token in (token_a1, token_a2):
            row = self.c.execute(
                "SELECT revoked_at FROM auth_sessions WHERE token_hash=?",
                (token_hash(token),),
            ).fetchone()
            self.assertIsNotNone(row["revoked_at"])
        row = self.c.execute(
            "SELECT revoked_at FROM auth_sessions WHERE token_hash=?",
            (token_hash(token_b),),
        ).fetchone()
        self.assertIsNone(row["revoked_at"])

    def test_account_delete_erases_personal_note_storage(self):
        self.command(
            NOTE_ROUTE, self.a,
            {"text": "erase-with-account", "request_id": secrets.token_hex(16)},
        )
        self.c.execute("DELETE FROM accounts WHERE email=?", (self.a,))
        self.c.commit()
        count = self.c.execute(
            "SELECT COUNT(*) n FROM personal_notes_v1 WHERE email=?", (self.a,)
        ).fetchone()["n"]
        self.assertEqual(count, 0)

    def test_unknown_route_not_claimed(self):
        self.assertIsNone(
            handle_command(self.c, "/api/other", "participant", self.a, {})
        )
        self.assertIsNone(read(self.c, "/api/other", "participant", self.a))


if __name__ == "__main__":
    unittest.main()
