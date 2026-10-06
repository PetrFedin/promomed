import os
import tempfile
import unittest
from pathlib import Path


class CapitalAllocationPlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "capital-plan.db")
        os.environ["PROMOMED_SEED_DEMO"] = "true"
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("PROMOMED_REQUIRE_POSTGRES", None)

        import importlib
        import app.db as db
        import app.capital_plan as capital_plan
        import server

        importlib.reload(db)
        importlib.reload(capital_plan)
        importlib.reload(server)
        self.capital_plan = capital_plan
        self.server = server
        self.server.init()
        self.c = self.server.conn()

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def test_security_packages_sum_to_10m(self):
        d = self.capital_plan.snapshot(self.c)
        packages = d["plan"]["packages"]
        self.assertEqual(sum(x["allocation_rub"] for x in packages), 10_000_000)
        self.assertEqual(packages[-1]["cumulative_allocation_rub"], 10_000_000)

    def test_step_zero_requires_no_capital_and_unlocks_operations(self):
        d = self.capital_plan.snapshot(self.c)
        pre = d["plan"]["precondition"]
        self.assertEqual(pre["capital_required_rub"], 0)
        self.assertEqual(pre["owner"], "Commercial Director")
        self.assertEqual(pre["potential_unlock_rub"], 12_500_000)
        step0 = d["trajectory"][1]
        self.assertEqual(step0["capital_used_rub"], 0)
        self.assertEqual(step0["state"]["at_risk"], 0)
        self.assertEqual(step0["state"]["eligible"], 32_500_000)

    def test_security_capital_stays_blocked_until_final_acceptance(self):
        d = self.capital_plan.snapshot(self.c)
        rows = {x["step"]: x for x in d["trajectory"]}
        self.assertEqual(rows["S1"]["state"]["blocked"], 32_500_000)
        self.assertEqual(rows["S2"]["state"]["blocked"], 32_500_000)
        self.assertEqual(rows["S3"]["state"]["blocked"], 32_500_000)
        self.assertEqual(rows["S4"]["state"]["blocked"], 22_500_000)
        self.assertEqual(rows["S4"]["state"]["eligible"], 42_500_000)
        self.assertEqual(rows["S4"]["effect"], "Final acceptance moves 10000000 RUB from blocked to eligible.")

    def test_final_projection_is_hold_not_go(self):
        d = self.capital_plan.snapshot(self.c)
        final = d["final_projection"]
        self.assertEqual(final["programme_decision"], "HOLD")
        self.assertEqual(final["blocked_rub"], 22_500_000)
        self.assertEqual(final["at_risk_rub"], 0)
        self.assertEqual(final["overdue_obligations"], 1)

    def test_plan_is_explicitly_non_binding(self):
        d = self.capital_plan.snapshot(self.c)
        self.assertTrue(d["truth_boundary"]["demo_plan"])
        self.assertFalse(d["truth_boundary"]["approved_budget"])
        self.assertFalse(d["truth_boundary"]["commercial_quote"])
        self.assertFalse(d["truth_boundary"]["automatic_payment"])
        self.assertEqual(d["plan"]["commercial_state"], "illustrative_plan_not_quote")


if __name__ == "__main__":
    unittest.main()
