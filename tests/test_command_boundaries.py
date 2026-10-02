import os
import tempfile
import unittest
from pathlib import Path

from app import community_commands, learning_commands, participant_commands, programme_commands

ROOT = Path(__file__).resolve().parents[1]


class CommandBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "commands.db")
        os.environ["PROMOMED_SEED_DEMO"] = "true"
        import importlib
        import app.db as db
        import server
        importlib.reload(db)
        importlib.reload(server)
        self.db = db
        self.server = server
        self.server.init()
        self.c = self.server.conn()

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def test_community_follow_and_consent_message_boundary(self):
        out = community_commands.handle_command(
            self.c, "/api/follow-expert", "participant", "participant@demo.ru",
            {"speaker_id": "SP01", "action": "follow"}, self.server.ACCOUNTS
        )
        self.assertTrue(out.use_state)
        followed = self.c.execute(
            "SELECT 1 FROM expert_follows WHERE email=? AND speaker_id=?",
            ("participant@demo.ru", "SP01"),
        ).fetchone()
        self.assertTrue(followed)

        blocked = community_commands.handle_command(
            self.c, "/api/direct-message", "participant", "participant@demo.ru",
            {"recipient": "participant2@demo.ru", "body": "Проверка consent boundary"},
            self.server.ACCOUNTS,
        )
        self.assertEqual(blocked.status, 403)
        self.assertEqual(blocked.payload["error"], "conversation_requires_mutual_consent")

    def test_learning_command_boundary(self):
        track = self.c.execute("SELECT id FROM learning_tracks ORDER BY id LIMIT 1").fetchone()["id"]
        out = learning_commands.handle_command(
            self.c, "/api/learning", "participant", "participant@demo.ru",
            {"track_id": track, "action": "enroll"},
        )
        self.assertTrue(out.use_state)
        row = self.c.execute(
            "SELECT status FROM learning_enrollments WHERE email=? AND track_id=?",
            ("participant@demo.ru", track),
        ).fetchone()
        self.assertEqual(row["status"], "active")

    def test_participant_profile_and_consent_boundary(self):
        out = participant_commands.handle_command(
            self.c, "/api/profile", "participant", "participant@demo.ru",
            {"intent": "Понять тему", "interests": "сон,движение", "networking": True, "visibility": "event_only"},
        )
        self.assertTrue(out.use_state)
        profile = self.c.execute(
            "SELECT intent,visibility FROM attendee_profiles WHERE email=?",
            ("participant@demo.ru",),
        ).fetchone()
        self.assertEqual(profile["intent"], "Понять тему")
        denied = participant_commands.handle_command(
            self.c, "/api/product-interest", "participant", "participant@demo.ru",
            {"track": "metabolic_health", "consent": False},
        )
        self.assertEqual(denied.status, 422)
        self.assertEqual(denied.payload["error"], "consent_required")

    def test_programme_registration_and_role_boundary(self):
        out = programme_commands.handle_command(
            self.c, "/api/register", "participant", "participant@demo.ru", {}
        )
        self.assertTrue(out.use_state)
        row = self.c.execute(
            "SELECT status FROM registrations WHERE email=?",
            ("participant@demo.ru",),
        ).fetchone()
        self.assertEqual(row["status"], "confirmed")
        denied = programme_commands.handle_command(
            self.c, "/api/register", "organizer", "organizer@demo.ru", {}
        )
        self.assertEqual(denied.status, 403)
        self.assertEqual(denied.payload["error"], "forbidden")


if __name__ == "__main__":
    unittest.main()
