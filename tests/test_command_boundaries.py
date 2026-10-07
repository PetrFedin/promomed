import os
import tempfile
import unittest
from pathlib import Path

from app import (
    community_commands,
    learning_commands,
    participant_commands,
    programme_commands,
    operations_commands,
    partner_commands,
    editorial_commands,
    institutional_commands,
    syndication_commands,
    demo_commands,
)

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
            {"speaker_id": "SP01", "action": "follow"}
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


    def test_operations_role_and_capacity_boundary(self):
        denied = operations_commands.handle_command(
            self.c, "/api/venue-state", "participant", "participant@demo.ru",
            {"venue": "Главная сцена", "occupied": 10, "capacity": 20, "status": "open"},
        )
        self.assertEqual(denied.status, 403)
        self.assertEqual(denied.payload["error"], "forbidden")

        over = operations_commands.handle_command(
            self.c, "/api/venue-state", "organizer", "organizer@demo.ru",
            {"venue": "Главная сцена", "occupied": 21, "capacity": 20, "status": "open"},
        )
        self.assertEqual(over.status, 409)
        self.assertEqual(over.payload["error"], "occupied_exceeds_capacity")

        ok = operations_commands.handle_command(
            self.c, "/api/venue-state", "organizer", "organizer@demo.ru",
            {"venue": "Главная сцена", "occupied": 18, "capacity": 20, "status": "open"},
        )
        self.assertTrue(ok.use_state)

    def test_partner_consent_and_role_boundary(self):
        denied = partner_commands.handle_command(
            self.c, "/api/lead", "participant", "participant@demo.ru",
            {"kind": "materials", "consent": False},
        )
        self.assertEqual(denied.status, 422)
        self.assertEqual(denied.payload["error"], "consent_required")

        allowed = partner_commands.handle_command(
            self.c, "/api/lead", "participant", "participant@demo.ru",
            {"kind": "materials", "consent": True},
        )
        self.assertTrue(allowed.use_state)
        row = self.c.execute("SELECT COUNT(*) n FROM leads WHERE status='new'").fetchone()
        self.assertGreaterEqual(row["n"], 1)

        wrong_role = partner_commands.handle_command(
            self.c, "/api/placement", "participant", "participant@demo.ru",
            {"status": "active"},
        )
        self.assertEqual(wrong_role.status, 403)

    def test_editorial_role_boundary(self):
        denied = editorial_commands.handle_command(
            self.c, "/api/cms", "participant", "participant@demo.ru",
            {"status": "approved"},
        )
        self.assertEqual(denied.status, 403)

        allowed = editorial_commands.handle_command(
            self.c, "/api/cms", "editor", "editor@demo.ru",
            {"status": "approved"},
        )
        self.assertTrue(allowed.use_state)
        row = self.c.execute("SELECT status FROM cms WHERE id='A-014'").fetchone()
        self.assertEqual(row["status"], "approved")

    def test_institutional_exchange_governance_boundary(self):
        denied = institutional_commands.handle_command(
            self.c, "/api/institution/register", "participant", "participant@demo.ru",
            {
                "organization_id": "INST-DEMO-BOUNDARY",
                "name": "Synthetic University",
                "organization_type": "university",
                "demo_only": True,
            },
        )
        self.assertEqual(denied.status, 403)
        self.assertEqual(denied.payload["error"], "forbidden")

        allowed = institutional_commands.handle_command(
            self.c, "/api/institution/register", "governance", "governance@demo.ru",
            {
                "organization_id": "INST-DEMO-BOUNDARY",
                "name": "Synthetic University",
                "organization_type": "university",
                "demo_only": True,
            },
        )
        self.assertEqual(allowed.status, 201)
        row = self.c.execute(
            "SELECT organization_type,status FROM institutional_organizations WHERE id=?",
            ("INST-DEMO-BOUNDARY",),
        ).fetchone()
        self.assertEqual(row["organization_type"], "university")
        self.assertEqual(row["status"], "active")

    def test_syndication_governance_and_member_boundaries(self):
        institutional_commands.handle_command(
            self.c, "/api/institution/register", "governance", "governance@demo.ru",
            {
                "organization_id": "INST-SYND-BOUNDARY",
                "name": "Synthetic Society",
                "organization_type": "scientific_society",
                "demo_only": True,
            },
        )
        denied = syndication_commands.handle_command(
            self.c, "/api/syndication/qualification/start", "participant", "participant@demo.ru",
            {"organization_id": "INST-SYND-BOUNDARY", "demo_only": True},
        )
        self.assertEqual(denied.status, 403)
        self.assertEqual(denied.payload["error"], "forbidden")

        allowed = syndication_commands.handle_command(
            self.c, "/api/syndication/qualification/start", "governance", "governance@demo.ru",
            {"organization_id": "INST-SYND-BOUNDARY", "demo_only": True},
        )
        self.assertEqual(allowed.status, 201)
        self.assertEqual(allowed.payload["data"]["qualification"]["status"], "pending")

        contribution = syndication_commands.handle_command(
            self.c, "/api/external-contribution/submit", "participant", "participant@demo.ru",
            {
                "organization_id": "INST-SYND-BOUNDARY",
                "contribution_type": "source_recommendation",
                "title": "Must be blocked without membership and qualification",
                "payload": {"source_ref": "urn:test"},
            },
        )
        self.assertEqual(contribution.status, 409)
        self.assertEqual(contribution.payload["error"], "syndication_partner_not_qualified")

    def test_demo_control_role_boundary(self):
        denied = demo_commands.handle_command(
            self.c, "/api/demo/reset", "participant", "participant@demo.ru", {}
        )
        self.assertEqual(denied.status, 403)

        allowed = demo_commands.handle_command(
            self.c, "/api/demo/reset", "sales", "sales@demo.ru", {}
        )
        self.assertTrue(allowed.use_state)
        self.assertEqual(self.server.sval(self.c, "demo_step", "missing"), "0")
    
    def test_failed_command_transaction_rolls_back(self):
        from app.commanding import error, finalize_command
        self.c.execute("INSERT INTO questions(text,status,ts) VALUES('atomicity probe','review',1)")
        outcome=error("forced_failure",409)
        committed=finalize_command(self.c,outcome)
        self.assertFalse(committed)
        row=self.c.execute("SELECT COUNT(*) n FROM questions WHERE text='atomicity probe'").fetchone()
        self.assertEqual(row["n"],0)

    def test_successful_command_transaction_commits(self):
        from app.commanding import ok, finalize_command
        self.c.execute("INSERT INTO questions(text,status,ts) VALUES('atomicity success','review',2)")
        committed=finalize_command(self.c,ok())
        self.assertTrue(committed)
        row=self.c.execute("SELECT COUNT(*) n FROM questions WHERE text='atomicity success'").fetchone()
        self.assertEqual(row["n"],1)


if __name__ == "__main__":
    unittest.main()
