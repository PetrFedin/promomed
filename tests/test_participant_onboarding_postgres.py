"""PostgreSQL 17 one-time participant invite and concurrency proof."""
import os
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor

from app import auth, db, participant_onboarding as onboarding

PASSWORD = "ParticipantPassphrase42!"


@unittest.skipUnless(
    os.environ.get("PROMOMED_INVITE_PG_TEST") == "1",
    "dedicated PostgreSQL invite qualification only",
)
class ParticipantInvitePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if db.backend_name() != "postgres":
            raise RuntimeError("postgres_required")
        cls.c = db.connect()
        db.migrate(cls.c)

    @classmethod
    def tearDownClass(cls):
        cls.c.rollback()
        cls.c.close()

    def setUp(self):
        suffix = uuid.uuid4().hex[:12]
        self.organizer = f"organizer-{suffix}@example.test"
        self.participant = f"participant-{suffix}@example.test"
        now = int(time.time())
        self.c.execute(
            "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
            "VALUES(?,?,'organizer','PG Organizer','active',?,?)",
            (self.organizer, auth.hash_password("OrganizerPassphrase42!"), now, now),
        )
        self.c.commit()

    def tearDown(self):
        self.c.rollback()
        self.c.execute("DELETE FROM auth_sessions WHERE email IN (?,?)",
                       (self.organizer, self.participant))
        self.c.execute("DELETE FROM registrations WHERE email=?", (self.participant,))
        self.c.execute("DELETE FROM participant_invites WHERE email=?", (self.participant,))
        self.c.execute("DELETE FROM events WHERE actor=?", (self.organizer,))
        self.c.execute("DELETE FROM accounts WHERE email IN (?,?)",
                       (self.organizer, self.participant))
        self.c.commit()

    def create(self):
        out = onboarding.handle_command(
            self.c,
            onboarding.CREATE_ROUTE,
            "organizer",
            self.organizer,
            {"email": self.participant, "name": "PG Participant"},
        )
        self.assertEqual(out.status, 201)
        self.c.commit()
        return out.payload["token"], out.payload["invite_id"]

    def test_one_token_one_account_under_parallel_acceptance(self):
        token, invite_id = self.create()

        def accept(_):
            return onboarding.handle_public(
                onboarding.ACCEPT_ROUTE,
                {"token": token, "password": PASSWORD},
            )[1]

        with ThreadPoolExecutor(max_workers=8) as pool:
            statuses = list(pool.map(accept, range(8)))

        self.assertEqual(statuses.count(201), 1, statuses)
        self.assertTrue(all(x in (201, 404) for x in statuses), statuses)
        account = self.c.execute(
            "SELECT role,status FROM accounts WHERE email=?", (self.participant,)
        ).fetchone()
        self.assertEqual((account["role"], account["status"]), ("participant", "active"))
        registration = self.c.execute(
            "SELECT status FROM registrations WHERE email=?", (self.participant,)
        ).fetchone()
        self.assertEqual(registration["status"], "confirmed")
        invite = self.c.execute(
            "SELECT status,consumed_at,token_hash FROM participant_invites WHERE id=?",
            (invite_id,),
        ).fetchone()
        self.assertEqual(invite["status"], "accepted")
        self.assertIsNotNone(invite["consumed_at"])
        self.assertEqual(invite["token_hash"], auth.token_hash(token))
        self.assertNotEqual(invite["token_hash"], token)
        self.assertEqual(
            self.c.execute(
                "SELECT COUNT(*) n FROM accounts WHERE email=?", (self.participant,)
            ).fetchone()["n"],
            1,
        )

    def test_acceptance_creates_no_session_and_requires_normal_login(self):
        token, _ = self.create()
        result, status = onboarding.handle_public(
            onboarding.ACCEPT_ROUTE,
            {"token": token, "password": PASSWORD},
        )
        self.assertEqual(status, 201)
        self.assertFalse(result["sessionCreated"])
        self.assertEqual(
            self.c.execute(
                "SELECT COUNT(*) n FROM auth_sessions WHERE email=?", (self.participant,)
            ).fetchone()["n"],
            0,
        )
        account = auth.authenticate(self.c, self.participant, PASSWORD)
        self.assertEqual(account["role"], "participant")

    def test_parallel_invite_creation_has_one_pending_authority(self):
        def create(_):
            c = db.connect()
            try:
                out = onboarding.handle_command(
                    c, onboarding.CREATE_ROUTE, "organizer", self.organizer,
                    {"email": self.participant, "name": "PG Participant"},
                )
                if out.status < 400:
                    c.commit()
                else:
                    c.rollback()
                return out.status
            finally:
                c.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(create, range(2)))
        self.assertEqual(statuses.count(201), 1, statuses)
        self.assertEqual(statuses.count(409), 1, statuses)
        self.assertEqual(
            self.c.execute(
                "SELECT COUNT(*) n FROM participant_invites "
                "WHERE email=? AND status='pending'",
                (self.participant,),
            ).fetchone()["n"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
