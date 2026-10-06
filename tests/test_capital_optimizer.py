import os
import tempfile
import unittest
from pathlib import Path


class CapitalAllocationOptimizerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "optimizer.db")
        os.environ["PROMOMED_SEED_DEMO"] = "true"
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("PROMOMED_REQUIRE_POSTGRES", None)

        import importlib
        import app.db as db
        import app.capital_optimizer as capital_optimizer
        import server

        importlib.reload(db)
        importlib.reload(capital_optimizer)
        importlib.reload(server)
        self.optimizer = capital_optimizer
        self.server = server
        self.server.init()
        self.c = self.server.conn()

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def test_optimizer_distinguishes_capital_from_management_blocker(self):
        d = self.optimizer.snapshot(self.c)
        rows = {x["id"]: x for x in d["scenarios"]}
        self.assertEqual(rows["operations"]["capital_dependency"], "not_required")
        self.assertEqual(rows["operations"]["capital_recommendation"], "DO_NOT_ALLOCATE_INCREMENTAL_CAPITAL")
        self.assertEqual(rows["operations"]["risk_adjusted_unlock_rub"], 0)
        self.assertEqual(d["recommendation"]["before_spending"]["capital_required_rub"], 0)
        self.assertEqual(d["recommendation"]["before_spending"]["potential_unlock_rub"], 12_500_000)

    def test_security_is_primary_capital_candidate(self):
        d = self.optimizer.snapshot(self.c)
        self.assertEqual(d["recommendation"]["primary"], "security")
        self.assertEqual(d["recommendation"]["allocation_rub"], 10_000_000)
        self.assertEqual(d["recommendation"]["decision"], "ALLOCATE_CONDITIONALLY")

    def test_scenarios_preserve_portfolio_total(self):
        d = self.optimizer.snapshot(self.c)
        for row in d["scenarios"]:
            p = row["projected_portfolio_if_successful"]
            self.assertEqual(
                p["paid"] + p["eligible"] + p["blocked"] + p["at_risk"],
                75_000_000,
            )

    def test_method_is_explicit_and_not_forecast(self):
        d = self.optimizer.snapshot(self.c)
        self.assertIn("risk-adjusted capital unlock", d["method"]["score_formula"])
        self.assertIn("0% capital attribution", d["method"]["capital_attribution_rule"])
        self.assertTrue(d["truth_boundary"]["demo_optimizer"])
        self.assertFalse(d["truth_boundary"]["approved_capital_plan"])
        self.assertFalse(d["truth_boundary"]["forecast"])
        self.assertFalse(d["truth_boundary"]["scenario_assumptions_are_actuals"])


if __name__ == "__main__":
    unittest.main()
