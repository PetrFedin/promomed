import os
import tempfile
import unittest
from pathlib import Path


class InvestmentProofSystemTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "investment-proof.db")
        os.environ["PROMOMED_SEED_DEMO"] = "true"
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("PROMOMED_REQUIRE_POSTGRES", None)

        import importlib
        import app.db as db
        import app.investment_proof as investment_proof
        import server

        importlib.reload(db)
        importlib.reload(investment_proof)
        importlib.reload(server)
        self.investment_proof = investment_proof
        self.server = server
        self.server.init()
        self.c = self.server.conn()

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def test_tranches_are_evidence_gated(self):
        proof = self.investment_proof.snapshot(self.c)
        tranches = {x["id"]: x for x in proof["tranches"]}
        self.assertEqual(set(tranches), {"t50", "t75", "t100"})
        self.assertEqual(tranches["t50"]["amount_rub"], 50_000_000)
        self.assertEqual(tranches["t75"]["amount_rub"], 75_000_000)
        self.assertEqual(tranches["t100"]["amount_rub"], 100_000_000)
        self.assertEqual(tranches["t50"]["state"], "blocked_by_phase0")
        self.assertEqual(tranches["t75"]["state"], "gated_by_50m_acceptance")
        self.assertEqual(tranches["t100"]["state"], "gated_by_75m_acceptance")

    def test_finance_is_required_for_value_acceptance(self):
        proof = self.investment_proof.snapshot(self.c)
        roles = {x["id"]: x for x in proof["acceptance_roles"]}
        self.assertIn("finance", roles)
        self.assertIn("economic value", roles["finance"]["accepts"])
        kpis = {x["id"]: x for x in proof["contractual_kpis"]}
        self.assertIn("accepted_net_value", kpis)
        self.assertEqual(kpis["accepted_net_value"]["owner"], "Finance")

    def test_no_auto_release_or_guaranteed_roi(self):
        proof = self.investment_proof.snapshot(self.c)
        decision = proof["decision_state"]
        self.assertFalse(decision["can_release_50m"])
        self.assertFalse(decision["can_release_75m"])
        self.assertFalse(decision["can_release_100m"])
        boundary = " ".join(decision["truth_boundary"])
        self.assertIn("No tranche is auto-released", boundary)
        self.assertIn("Finance acceptance", boundary)

    def test_evidence_ledger_has_acceptance_chain(self):
        proof = self.investment_proof.snapshot(self.c)
        stages = [x["stage"] for x in proof["evidence_ledger"]]
        self.assertEqual(stages, [
            "LOCK BASELINE",
            "CAPTURE DELIVERY",
            "MEASURE KPI",
            "FINANCE ACCEPTANCE",
            "TRANCHE DECISION",
        ])


if __name__ == "__main__":
    unittest.main()
