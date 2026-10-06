import os
import tempfile
import unittest
from pathlib import Path


class PersonalizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "personalization.db")
        os.environ["PROMOMED_SEED_DEMO"] = "true"
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("PROMOMED_REQUIRE_POSTGRES", None)

        import importlib
        import app.db as db
        import app.personalization as personalization
        import server

        importlib.reload(db)
        importlib.reload(personalization)
        importlib.reload(server)
        self.personalization = personalization
        self.server = server
        self.server.init()
        self.c = self.server.conn()
        self.email = "participant@demo.ru"

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def test_default_profile_has_explainable_non_medical_recommendations(self):
        d = self.personalization.snapshot(self.c, self.email)
        self.assertEqual(d["personalization_mode"], "deterministic_rules_v1")
        self.assertFalse(d["personalization_medical_inference"])
        self.assertGreaterEqual(len(d["personalized_items"]), 2)
        self.assertTrue(all(x["reason"]["code"] for x in d["personalized_items"]))
        self.assertTrue(all(x["reason"]["medical_inference"] is False for x in d["personalized_items"]))
        self.assertIn("drug recommendation", d["personalization_forbidden_outputs"])

    def test_subscription_and_follow_raise_related_items(self):
        self.c.execute(
            "INSERT INTO topic_subscriptions(email,topic,status,ts) VALUES(?,?,'active',1)",
            (self.email, "Метаболическое здоровье"),
        )
        self.c.execute(
            "INSERT INTO expert_follows(email,speaker_id,status,ts) VALUES(?,?,'active',1)",
            (self.email, "SP06"),
        )
        self.c.commit()
        d = self.personalization.snapshot(self.c, self.email)
        codes = {x["reason"]["code"] for x in d["personalized_items"]}
        self.assertIn("subscribed_topic", codes)
        self.assertIn("follows_expert", codes)

    def test_active_learning_is_ranked_first(self):
        self.c.execute(
            "INSERT INTO learning_enrollments(email,track_id,status,current_step,started,updated) VALUES(?,?,'active',1,1,1)",
            (self.email, "LT01"),
        )
        self.c.commit()
        d = self.personalization.snapshot(self.c, self.email)
        first = d["personalized_items"][0]
        self.assertEqual(first["kind"], "learning")
        self.assertEqual(first["reason"]["code"], "continue_learning_track")
        self.assertEqual(first["target_kind"], "expert")
        self.assertEqual(first["target_ref"], "SP06")

    def test_attendance_creates_replay_continuation(self):
        self.c.execute(
            "INSERT INTO session_attendance(email,item_id,status,checkin_ts,checkout_ts,source) VALUES(?,?,'attended',1,2,'demo')",
            (self.email, "P21"),
        )
        self.c.commit()
        d = self.personalization.snapshot(self.c, self.email)
        replay = [x for x in d["personalized_items"] if x["target_kind"] == "replay" and x["target_ref"] == "P21"]
        self.assertEqual(len(replay), 1)
        self.assertEqual(replay[0]["reason"]["code"], "attended_related_session")

    def test_output_is_deterministic_for_same_state(self):
        a = self.personalization.snapshot(self.c, self.email)
        b = self.personalization.snapshot(self.c, self.email)
        self.assertEqual(a["personalized_items"], b["personalized_items"])


if __name__ == "__main__":
    unittest.main()
