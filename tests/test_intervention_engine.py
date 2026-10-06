import os
import tempfile
import unittest
from pathlib import Path


class CapitalInterventionEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "intervention.db")
        os.environ["PROMOMED_SEED_DEMO"] = "true"
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("PROMOMED_REQUIRE_POSTGRES", None)

        import importlib
        import app.db as db
        import app.intervention_engine as intervention_engine
        import server

        importlib.reload(db)
        importlib.reload(intervention_engine)
        importlib.reload(server)
        self.engine = intervention_engine
        self.server = server
        self.server.init()
        self.c = self.server.conn()

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def test_s2_is_primary_recovery_intervention(self):
        d = self.engine.snapshot(self.c)
        self.assertEqual(d["summary"]["primary_package"], "s2")
        self.assertEqual(d["summary"]["primary_intervention"], "RECOVERY_SPRINT")
        self.assertTrue(d["summary"]["freeze_next_commitment"])
        self.assertEqual(d["summary"]["programme_action"], "ITERATE")

    def test_engine_distinguishes_reallocation_candidate_from_committed_unspent(self):
        d = self.engine.snapshot(self.c)
        rows = {x["package_id"]: x for x in d["diagnostics"]}
        self.assertEqual(rows["s2"]["reallocation_candidate_rub"], 0)
        self.assertGreater(rows["s2"]["capital_at_risk_rub"], 0)
        self.assertEqual(rows["s3"]["reallocation_candidate_rub"], 1_500_000)
        self.assertEqual(rows["s4"]["reallocation_candidate_rub"], 3_000_000)

    def test_downstream_value_at_risk_is_not_double_counted(self):
        d = self.engine.snapshot(self.c)
        self.assertEqual(d["summary"]["downstream_value_at_risk_rub"], 10_000_000)
        self.assertLessEqual(d["summary"]["downstream_value_at_risk_rub"], 10_000_000)

    def test_create_intervention_is_record_only(self):
        self.engine.create_demo_intervention(self.c, "s2", "sales@demo.ru")
        self.c.commit()
        d = self.engine.snapshot(self.c)
        self.assertEqual(len(d["open_interventions"]), 1)
        row = d["open_interventions"][0]
        self.assertEqual(row["package_id"], "s2")
        self.assertEqual(row["status"], "open_demo")
        self.assertEqual(row["intervention_type"], "RECOVERY_SPRINT")

    def test_truth_boundary_prevents_automatic_actions(self):
        d = self.engine.snapshot(self.c)
        self.assertTrue(d["truth_boundary"]["demo_engine"])
        self.assertFalse(d["truth_boundary"]["actual_forecast"])
        self.assertFalse(d["truth_boundary"]["automatic_reallocation"])
        self.assertFalse(d["truth_boundary"]["automatic_commitment_freeze"])
        self.assertFalse(d["truth_boundary"]["actual_payment_authority"])


if __name__ == "__main__":
    unittest.main()
