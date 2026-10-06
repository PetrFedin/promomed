import os
import tempfile
import unittest
from pathlib import Path


class ContractBuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "contract-builder.db")
        os.environ["PROMOMED_SEED_DEMO"] = "true"
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("PROMOMED_REQUIRE_POSTGRES", None)

        import importlib
        import app.db as db
        import app.contract_builder as contract_builder
        import server

        importlib.reload(db)
        importlib.reload(contract_builder)
        importlib.reload(server)
        self.contract_builder = contract_builder
        self.server = server
        self.server.init()
        self.c = self.server.conn()

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def test_builder_contains_three_investment_packages(self):
        data = self.contract_builder.snapshot(self.c)
        packages = {x["id"]: x for x in data["packages"]}
        self.assertEqual(set(packages), {"t50", "t75", "t100"})
        self.assertEqual(packages["t50"]["amount_rub"], 50_000_000)
        self.assertEqual(packages["t75"]["amount_rub"], 75_000_000)
        self.assertEqual(packages["t100"]["amount_rub"], 100_000_000)

    def test_payment_template_sums_to_100_percent(self):
        data = self.contract_builder.snapshot(self.c)
        self.assertEqual(data["payment_template"]["shares_total_pct"], 100)
        for package in data["packages"]:
            self.assertEqual(sum(x["share_pct"] for x in package["payment_milestones"]), 100)
            self.assertEqual(sum(x["amount_rub"] for x in package["payment_milestones"]), package["amount_rub"])
            self.assertTrue(all(x["commercial_state"] == "illustrative_template_not_quote" for x in package["payment_milestones"]))

    def test_each_milestone_has_control_chain(self):
        data = self.contract_builder.snapshot(self.c)
        for package in data["packages"]:
            for milestone in package["payment_milestones"]:
                self.assertTrue(milestone["responsible"])
                self.assertTrue(milestone["deliverable"])
                self.assertTrue(milestone["kpi"])
                self.assertTrue(milestone["evidence"])
                self.assertTrue(milestone["payment_rule"])
                self.assertTrue(milestone["stop_go"])

    def test_certificate_preview_never_has_legal_or_capital_effect(self):
        data = self.contract_builder.snapshot(self.c)
        for package in data["packages"]:
            cert = package["board_decision_certificate"]
            self.assertEqual(cert["legal_effect"], "NONE")
            self.assertEqual(cert["capital_release_effect"], "NONE")
        self.assertFalse(data["truth_boundary"]["is_legal_contract"])
        self.assertFalse(data["truth_boundary"]["is_commercial_quote"])
        self.assertFalse(data["truth_boundary"]["is_e_signature"])
        self.assertFalse(data["truth_boundary"]["auto_releases_money"])

    def test_t50_is_hold_until_phase0(self):
        data = self.contract_builder.snapshot(self.c)
        p50 = {x["id"]: x for x in data["packages"]}["t50"]
        self.assertEqual(p50["contract_state"], "blocked_by_phase0")
        self.assertEqual(p50["board_decision_certificate"]["decision"], "HOLD")
        self.assertIn("Phase 0 production admission", p50["board_decision_certificate"]["blockers"])


if __name__ == "__main__":
    unittest.main()
