import os
import tempfile
import unittest
from pathlib import Path


class ExecutiveProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "executive.db")
        os.environ["PROMOMED_SEED_DEMO"] = "true"
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("PROMOMED_REQUIRE_POSTGRES", None)

        import importlib
        import app.db as db
        import app.executive as executive
        import app.investor as investor
        import server

        importlib.reload(db)
        importlib.reload(investor)
        importlib.reload(executive)
        importlib.reload(server)
        self.executive = executive
        self.server = server
        self.server.init()
        self.c = self.server.conn()

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def test_demo_runtime_allows_only_controlled_pilot_decision(self):
        room = self.executive.snapshot(self.c)
        board = room["board_summary"]
        self.assertEqual(board["decision_state"], "controlled_pilot_only")
        self.assertEqual(board["decision_label"], "CONTROLLED PILOT ONLY")
        self.assertFalse(board["production_ready"])
        self.assertIn("Phase 0 COMPLETE", board["next_gate"])

    def test_truth_boundary_is_fail_closed(self):
        room = self.executive.snapshot(self.c)
        truth = room["truth_boundary"]
        self.assertTrue(truth["can_show_to_executives"])
        self.assertFalse(truth["can_claim_production_ready"])
        self.assertFalse(truth["can_claim_market_traction"])
        self.assertFalse(truth["can_claim_validated_unit_economics"])
        self.assertFalse(truth["can_claim_medical_governance"])

    def test_funding_is_milestone_based_without_amounts(self):
        room = self.executive.snapshot(self.c)
        tranches = {x["id"]: x for x in room["funding_tranches"]}
        self.assertEqual(tranches["t0"]["status"], "blocking")
        self.assertEqual(tranches["t1"]["status"], "eligible_after_t0")
        self.assertEqual(tranches["t2"]["status"], "gated")
        self.assertEqual(tranches["t3"]["status"], "gated")
        text = str(room["funding_tranches"]).lower()
        for forbidden in ("₽", "$", "valuation", "arr", "mrr"):
            self.assertNotIn(forbidden, text)

    def test_pilot_contract_and_kpis_do_not_invent_targets(self):
        room = self.executive.snapshot(self.c)
        self.assertIn("Personalized medical advice", room["pilot_contract"]["out_of_scope"])
        self.assertGreaterEqual(len(room["kpi_dictionary"]), 7)
        targets = {x["target"] for x in room["kpi_dictionary"]}
        self.assertIn("to_agree_before_pilot", targets)
        self.assertIn("measure_actual", targets)
        self.assertIn("measure_after_pilot", targets)

    def test_corporate_readiness_keeps_vendor_and_medical_gated(self):
        room = self.executive.snapshot(self.c)
        status = {x["id"]: x["status"] for x in room["corporate_readiness"]}
        self.assertEqual(status["architecture"], "ci_proven")
        self.assertEqual(status["identity"], "ci_proven")
        self.assertEqual(status["continuity"], "ci_proven")
        self.assertEqual(status["vendor"], "gated")
        self.assertEqual(status["medical"], "gated")
        self.assertEqual(status["observability"], "gated")

    def test_partner_exchange_protects_data_and_editorial_boundary(self):
        room = self.executive.snapshot(self.c)
        never = " ".join(room["strategic_partner_exchange"]["never_implied"])
        self.assertIn("sensitive health data", never)
        self.assertIn("Silent participant contact export", never)
        self.assertIn("medical/editorial approval", never)
        self.assertIn("Guaranteed leads or revenue", never)


if __name__ == "__main__":
    unittest.main()
