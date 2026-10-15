"""ONB-01 one-time participant invite authority and atomic acceptance."""
import importlib
import os
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from app import auth, participant_onboarding as onboarding


PASSWORD = "ParticipantPassphrase42!"


class ParticipantInviteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "SQLITE_PATH": str(Path(self.temp.name) / "invite.db"),
            "DATABASE_URL": "",
            "PROMOMED_SEED_DEMO": "false",
            "PROMOMED_REQUIRE_POSTGRES": "false",
        })
        self.env.start()
        from app import db
        importlib.reload(db)
        importlib.reload(onboarding)
        self.db = db
        self.c = db.connect()
        db.migrate(self.c)
        now = int(time.time())
        for email in ("organizer-a@example.test", "organizer-b@example.test"):
            self.c.execute(
                "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
                "VALUES(?,?,'organizer','Organizer','active',?,?)",
                (email, auth.hash_password("OrganizerPassphrase42!"), now, now),
            )
        self.c.commit()

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.temp.cleanup()

    def create(self, target="participant@example.test", actor="organizer-a@example.test"):
        out = onboarding.handle_command(
            self.c, onboarding.CREATE_ROUTE, "organizer", actor,
            {"email": target, "name": "Participant Test"},
        )
        if out.status < 400:
            self.c.commit()
        else:
            self.c.rollback()
        return out

    def test_create_stores_hash_not_raw_token_and_audit_has_no_secret(self):
        out = self.create()
        self.assertEqual(out.status, 201)
        token = out.payload["token"]
        self.assertRegex(token, onboarding.TOKEN_RE)
        row = self.c.execute(
            "SELECT token_hash,status,created_by FROM participant_invites WHERE id=?",
            (out.payload["invite_id"],),
        ).fetchone()
        self.assertEqual(row["token_hash"], auth.token_hash(token))
        self.assertNotEqual(row["token_hash"], token)
        self.assertEqual(row["status"], "pending")
        events = [dict(x) for x in self.c.execute(
            "SELECT kind,payload FROM events WHERE actor=? ORDER BY id",
            ("organizer-a@example.test",),
        )]
        self.assertTrue(any(x["kind"] == "participant_invite_created" for x in events))
        self.assertNotIn(token, str(events))

    def test_only_organizer_can_create_and_non_demo_rejects_demo_identity(self):
        denied = onboarding.handle_command(
            self.c, onboarding.CREATE_ROUTE, "partner", "partner@example.test",
            {"email": "p@example.test", "name": "P"},
        )
        self.assertEqual(denied.status, 403)
        demo = onboarding.handle_command(
            self.c, onboarding.CREATE_ROUTE, "organizer", "organizer-a@example.test",
            {"email": "participant@demo.ru", "name": "P"},
        )
        self.assertEqual(demo.status, 422)
        self.assertEqual(demo.payload["error"], "demo_identity_forbidden")

    def test_accept_creates_participant_and_registration_without_session(self):
        invite = self.create()
        result, status = onboarding.handle_public(
            onboarding.ACCEPT_ROUTE,
            {"token": invite.payload["token"], "password": PASSWORD},
        )
        self.assertEqual(status, 201)
        self.assertTrue(result["accepted"])
        self.assertFalse(result["sessionCreated"])
        account = auth.authenticate(self.c, "participant@example.test", PASSWORD)
        self.assertIsNotNone(account)
        self.assertEqual(account["role"], "participant")
        registration = self.c.execute(
            "SELECT status FROM registrations WHERE email=?",
            ("participant@example.test",),
        ).fetchone()
        self.assertEqual(registration["status"], "confirmed")
        self.assertEqual(
            self.c.execute(
                "SELECT COUNT(*) n FROM auth_sessions WHERE email=?",
                ("participant@example.test",),
            ).fetchone()["n"],
            0,
        )
        row = self.c.execute(
            "SELECT status,consumed_at FROM participant_invites WHERE id=?",
            (invite.payload["invite_id"],),
        ).fetchone()
        self.assertEqual(row["status"], "accepted")
        self.assertIsNotNone(row["consumed_at"])

    def test_token_is_one_time_and_wrong_token_has_same_not_found_shape(self):
        invite = self.create()
        first = onboarding.handle_public(
            onboarding.ACCEPT_ROUTE,
            {"token": invite.payload["token"], "password": PASSWORD},
        )
        replay = onboarding.handle_public(
            onboarding.ACCEPT_ROUTE,
            {"token": invite.payload["token"], "password": PASSWORD},
        )
        wrong = onboarding.handle_public(
            onboarding.ACCEPT_ROUTE,
            {"token": "A" * 43, "password": PASSWORD},
        )
        self.assertEqual(first[1], 201)
        self.assertEqual(replay, ({"error": "invalid_or_expired_invite"}, 404))
        self.assertEqual(wrong, replay)

    def test_concurrent_acceptance_creates_exactly_one_account(self):
        invite = self.create("parallel@example.test")
        token = invite.payload["token"]

        def accept(_):
            return onboarding.handle_public(
                onboarding.ACCEPT_ROUTE,
                {"token": token, "password": PASSWORD},
            )[1]

        with ThreadPoolExecutor(max_workers=8) as pool:
            statuses = list(pool.map(accept, range(8)))
        self.assertEqual(statuses.count(201), 1)
        self.assertTrue(all(x in (201, 404) for x in statuses))
        self.assertEqual(
            self.c.execute(
                "SELECT COUNT(*) n FROM accounts WHERE email='parallel@example.test'"
            ).fetchone()["n"],
            1,
        )
        self.assertEqual(
            self.c.execute(
                "SELECT COUNT(*) n FROM registrations WHERE email='parallel@example.test'"
            ).fetchone()["n"],
            1,
        )

    def test_revocation_is_creator_scoped_and_blocks_acceptance(self):
        invite = self.create("revoked@example.test")
        foreign = onboarding.handle_command(
            self.c, onboarding.REVOKE_ROUTE, "organizer",
            "organizer-b@example.test", {"invite_id": invite.payload["invite_id"]},
        )
        self.assertEqual(foreign.status, 404)
        self.c.rollback()
        own = onboarding.handle_command(
            self.c, onboarding.REVOKE_ROUTE, "organizer",
            "organizer-a@example.test", {"invite_id": invite.payload["invite_id"]},
        )
        self.assertEqual(own.status, 200)
        self.c.commit()
        self.assertEqual(
            onboarding.handle_public(
                onboarding.ACCEPT_ROUTE,
                {"token": invite.payload["token"], "password": PASSWORD},
            ),
            ({"error": "invalid_or_expired_invite"}, 404),
        )

    def test_expired_invite_and_password_policy_fail_closed(self):
        invite = self.create("expired@example.test")
        now = int(time.time())
        self.c.execute(
            "UPDATE participant_invites SET created_at=?,expires_at=? WHERE id=?",
            (now - 3600, now - 1, invite.payload["invite_id"]),
        )
        self.c.commit()
        expired = onboarding.handle_public(
            onboarding.ACCEPT_ROUTE,
            {"token": invite.payload["token"], "password": PASSWORD},
        )
        self.assertEqual(expired, ({"error": "invalid_or_expired_invite"}, 404))

        other = self.create("password@example.test")
        weak = onboarding.handle_public(
            onboarding.ACCEPT_ROUTE,
            {"token": other.payload["token"], "password": "short"},
        )
        self.assertEqual(weak, ({"error": "password_policy"}, 422))
        self.assertIsNone(
            self.c.execute(
                "SELECT 1 FROM accounts WHERE email='password@example.test'"
            ).fetchone()
        )

    def test_account_created_after_invite_revokes_invite_on_accept(self):
        invite = self.create("race@example.test")
        now = int(time.time())
        self.c.execute(
            "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
            "VALUES(?,?,'participant','Existing','active',?,?)",
            ("race@example.test", auth.hash_password(PASSWORD), now, now),
        )
        self.c.commit()
        result = onboarding.handle_public(
            onboarding.ACCEPT_ROUTE,
            {"token": invite.payload["token"], "password": PASSWORD},
        )
        self.assertEqual(result, ({"error": "account_exists"}, 409))
        row = self.c.execute(
            "SELECT status FROM participant_invites WHERE id=?",
            (invite.payload["invite_id"],),
        ).fetchone()
        self.assertEqual(row["status"], "revoked")

    def test_duplicate_pending_invite_is_rejected(self):
        self.assertEqual(self.create("one@example.test").status, 201)
        second = self.create("one@example.test")
        self.assertEqual(second.status, 409)
        self.assertEqual(second.payload["error"], "invite_pending")

    def test_expired_pending_is_closed_before_reissue(self):
        first = self.create("reissue@example.test")
        now = int(time.time())
        self.c.execute(
            "UPDATE participant_invites SET created_at=?,expires_at=? WHERE id=?",
            (now - 3600, now - 1, first.payload["invite_id"]),
        )
        self.c.commit()
        second = self.create("reissue@example.test")
        self.assertEqual(second.status, 201)
        self.assertNotEqual(first.payload["invite_id"], second.payload["invite_id"])
        old = self.c.execute(
            "SELECT status,consumed_at FROM participant_invites WHERE id=?",
            (first.payload["invite_id"],),
        ).fetchone()
        self.assertEqual(old["status"], "revoked")
        self.assertIsNotNone(old["consumed_at"])


if __name__ == "__main__":
    unittest.main()
