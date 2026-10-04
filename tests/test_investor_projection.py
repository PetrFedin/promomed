import os
import tempfile
import unittest
from pathlib import Path


class InvestorProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "investor.db")
        os.environ["PROMOMED_SEED_DEMO"] = "true"
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("PROMOMED_REQUIRE_POSTGRES", None)

        import importlib
        import app.db as db
        import app.investor as investor
        import server

        importlib.reload(db)
        importlib.reload(investor)
        importlib.reload(server)
        self.db = db
        self.investor = investor
        self.server = server
        self.server.init()
        self.c = self.server.conn()

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def test_runtime_truth_is_explicit(self):
        proof = self.investor.snapshot(self.c)
        self.assertEqual(proof["runtime"]["backend"], "sqlite")
        self.assertFalse(proof["runtime"]["durable"])
        self.assertFalse(proof["runtime"]["production_ready"])
        self.assertGreaterEqual(proof["counts"]["program_items"], 42)
        self.assertGreaterEqual(proof["counts"]["content_items"], 10)
        self.assertGreaterEqual(proof["counts"]["speakers"], 10)

    def test_phase_one_authorities_remain_gated(self):
        proof = self.investor.snapshot(self.c)
        statuses = {x["id"]: x["status"] for x in proof["capabilities"]}
        self.assertEqual(statuses["postgres"], "ci_proven")
        self.assertEqual(statuses["identity"], "ci_proven")
        self.assertEqual(statuses["medical_review"], "gated")
        self.assertEqual(statuses["evidence_claim"], "gated")
        self.assertEqual(statuses["medical_info"], "gated")

    def test_capital_milestones_are_dependency_gated(self):
        proof = self.investor.snapshot(self.c)
        milestones = {x["id"]: x["status"] for x in proof["capital_milestones"]}
        self.assertEqual(milestones["phase0"], "ci_proven")
        self.assertEqual(milestones["phase1"], "gated")
        self.assertEqual(milestones["phase2"], "gated")
        self.assertEqual(milestones["phase3"], "gated")
        self.assertEqual(milestones["scale"], "gated")
        thesis = proof["investor_thesis"]
        self.assertIn("event operating system", thesis["category"])
        self.assertGreaterEqual(len(thesis["value_creation_logic"]), 4)

    def test_investment_committee_truth_boundaries(self):
        proof = self.investor.snapshot(self.c)
        committee = proof["committee_state"]
        self.assertEqual(committee["evidence_state"], "pilot_diligence_ready")
        self.assertIn("Phase 0 COMPLETE", committee["next_gate"])
        self.assertIn("Paid market traction", committee["not_claimed"])
        diligence = {x["id"]: x["status"] for x in proof["diligence_domains"]}
        self.assertEqual(diligence["product_experience"], "live")
        self.assertEqual(diligence["technical_architecture"], "ci_proven")
        self.assertEqual(diligence["market_traction"], "gated")
        self.assertEqual(diligence["medical_governance"], "gated")
        risks = {x["id"]: x["severity"] for x in proof["risk_register"]}
        self.assertEqual(risks["infra_capacity"], "blocking")
        self.assertEqual(risks["traction"], "unproven")
        scale = {x["title"]: x["status"] for x in proof["scale_paths"]}
        self.assertEqual(scale["Governed scientific-information platform"], "gated")
        self.assertEqual(scale["White-label operating system"], "gated")

    def test_revenue_architecture_does_not_claim_financial_forecasts(self):
        proof = self.investor.snapshot(self.c)
        revenue_text = str(proof["revenue_architecture"]).lower()
        for forbidden in ("valuation", "arr", "mrr", "revenue forecast", "market share"):
            self.assertNotIn(forbidden, revenue_text)
        self.assertTrue(any("No revenue" in x for x in proof["disclaimers"]))
        self.assertTrue(proof["blockers"])


if __name__ == "__main__":
    unittest.main()
