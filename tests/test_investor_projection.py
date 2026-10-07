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
        self.assertEqual(statuses["institutional_evidence_network"], "ci_proven")
        self.assertEqual(statuses["certified_syndication_network"], "ci_proven")
        self.assertEqual(statuses["partner_delivery_protocol"], "ci_proven")
        self.assertEqual(statuses["partner_trust_bundle"], "ci_proven")
        self.assertEqual(proof["counts"]["institutional_organizations"], 0)
        self.assertEqual(proof["counts"]["evidence_exchange_packages"], 0)
        self.assertEqual(proof["counts"]["qualified_syndication_partners"], 0)
        self.assertEqual(proof["counts"]["external_contributions_admitted"], 0)
        self.assertEqual(proof["counts"]["production_webhook_endpoints"], 0)
        self.assertEqual(proof["counts"]["production_delivery_events"], 0)
        self.assertEqual(proof["counts"]["production_delivery_acks"], 0)
        self.assertEqual(proof["counts"]["production_trust_snapshots"], 0)
        self.assertEqual(proof["counts"]["production_trust_bundles"], 0)
        self.assertEqual(proof["counts"]["production_external_trust_verifications"], 0)

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

    def test_50_100m_value_case_is_formula_bound_and_not_a_forecast(self):
        proof = self.investor.snapshot(self.c)
        envelopes = {x["amount_rub"]: x for x in proof["investment_envelopes"]}
        self.assertEqual(set(envelopes), {50_000_000, 75_000_000, 100_000_000})
        self.assertEqual(proof["public_company_context"]["period"], "FY2025")
        self.assertGreater(proof["public_company_context"]["revenue_rub"], 0)
        self.assertGreater(proof["public_company_context"]["adjusted_ebitda_rub"], 0)
        refs = {x["amount_rub"]: x for x in proof["payback_reference"]}
        self.assertEqual(refs[50_000_000]["thresholds"][1]["months"], 12)
        self.assertEqual(refs[50_000_000]["thresholds"][1]["annual_verified_value_rub"], 50_000_000)
        self.assertEqual(refs[100_000_000]["thresholds"][0]["months"], 6)
        self.assertEqual(refs[100_000_000]["thresholds"][0]["annual_verified_value_rub"], 200_000_000)
        levers = {x["id"]: x for x in proof["value_levers"]}
        self.assertTrue(levers["budget_substitution"]["base_case"])
        self.assertTrue(levers["contracted_partner_value"]["base_case"])
        self.assertFalse(levers["product_sales"]["base_case"])
        self.assertTrue(levers["product_sales"]["gated"])
        truth = str(proof["value_case_truth"]).lower()
        self.assertIn("not an asserted valuation", truth)
        self.assertIn("double", truth)
        self.assertNotIn("guaranteed payback", truth)

    def test_value_capture_map_has_owner_formula_proof_and_guardrail(self):
        proof = self.investor.snapshot(self.c)
        rows = proof["value_capture_map"]
        self.assertGreaterEqual(len(rows), 6)
        for row in rows:
            self.assertTrue(row["owner"])
            self.assertTrue(row["baseline"])
            self.assertTrue(row["formula"])
            self.assertTrue(row["proof"])
            self.assertTrue(row["decision"])
        by_id = {x["id"]: x for x in rows}
        self.assertEqual(by_id["budget_baseline"]["counting"], "discovery_only")
        self.assertEqual(by_id["external_substitution"]["counting"], "counts_once")
        self.assertEqual(by_id["owned_365_audience"]["status"], "upside_until_proven")
        protocol = proof["value_evidence_protocol"]
        self.assertGreaterEqual(len(protocol["steps"]), 5)
        self.assertIn("No value line enters payback twice", protocol["guardrail"])

    def test_institutional_distribution_is_commercially_visible_without_traction_claim(self):
        proof = self.investor.snapshot(self.c)
        products = {x["id"]: x for x in proof["revenue_architecture"]}
        institutional = products["knowledge_licensing"]
        self.assertEqual(institutional["status"], "ci_proven")
        text = (institutional["model"] + " " + institutional["evidence"]).lower()
        self.assertIn("no external institution", text)
        self.assertNotIn("signed customer", text)
        self.assertNotIn("arr", text)

    def test_certified_syndication_is_visible_without_partner_adoption_claim(self):
        proof = self.investor.snapshot(self.c)
        capabilities = {x["id"]: x for x in proof["capabilities"]}
        network = capabilities["certified_syndication_network"]
        self.assertEqual(network["status"], "ci_proven")
        text = network["proof"].lower()
        self.assertIn("no qualified production partner", text)
        self.assertIn("no", text)
        self.assertEqual(proof["counts"]["qualified_syndication_partners"], 0)
        self.assertEqual(proof["counts"]["external_contributions_admitted"], 0)

    def test_partner_delivery_protocol_is_visible_without_production_traffic_claim(self):
        proof = self.investor.snapshot(self.c)
        capabilities = {x["id"]: x for x in proof["capabilities"]}
        delivery = capabilities["partner_delivery_protocol"]
        self.assertEqual(delivery["status"], "ci_proven")
        text = delivery["proof"].lower()
        self.assertIn("no production endpoint", text)
        self.assertIn("no production", text)
        self.assertEqual(proof["counts"]["production_webhook_endpoints"], 0)
        self.assertEqual(proof["counts"]["production_delivery_events"], 0)
        self.assertEqual(proof["counts"]["production_delivery_acks"], 0)

    def test_partner_trust_bundle_is_visible_without_external_adoption_claim(self):
        proof=self.investor.snapshot(self.c)
        capabilities={x["id"]:x for x in proof["capabilities"]}
        trust=capabilities["partner_trust_bundle"]
        self.assertEqual(trust["status"],"ci_proven")
        text=trust["proof"].lower()
        self.assertIn("no production trust snapshot",text)
        self.assertIn("no",text)
        self.assertEqual(proof["counts"]["production_trust_snapshots"],0)
        self.assertEqual(proof["counts"]["production_trust_bundles"],0)
        self.assertEqual(proof["counts"]["production_external_trust_verifications"],0)

    def test_revenue_architecture_does_not_claim_financial_forecasts(self):
        proof = self.investor.snapshot(self.c)
        revenue_text = str(proof["revenue_architecture"]).lower()
        for forbidden in ("valuation", "arr", "mrr", "revenue forecast", "market share"):
            self.assertNotIn(forbidden, revenue_text)
        self.assertTrue(any("No revenue" in x for x in proof["disclaimers"]))
        self.assertTrue(proof["blockers"])


if __name__ == "__main__":
    unittest.main()
