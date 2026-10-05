import os
import tempfile
import unittest
from pathlib import Path


class CorporateReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "corporate.db")
        os.environ["PROMOMED_SEED_DEMO"] = "true"
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("PROMOMED_REQUIRE_POSTGRES", None)

        import importlib
        import app.corporate as corporate
        import app.db as db
        import app.investor as investor
        import server

        importlib.reload(db)
        importlib.reload(investor)
        importlib.reload(corporate)
        importlib.reload(server)
        self.corporate = corporate
        self.server = server
        self.server.init()
        self.c = self.server.conn()

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def test_security_truth_is_fail_closed(self):
        room = self.corporate.snapshot(self.c)
        truth = room["security_truth"]
        self.assertEqual(truth["current_state"], "pre_production_security_review")
        self.assertFalse(truth["can_claim_certification"])
        self.assertFalse(truth["can_claim_approved_rto_rpo"])
        self.assertFalse(truth["can_claim_approved_dpa_sla"])
        self.assertFalse(truth["can_claim_central_siem"])
        self.assertFalse(truth["can_claim_live_postgres"])
        self.assertTrue(truth["can_claim_auth_restore_controls_ci_proven"])

    def test_auth_and_restore_controls_are_evidence_backed(self):
        room = self.corporate.snapshot(self.c)
        status = {x["id"]: x["status"] for x in room["controls"]}
        self.assertEqual(status["password_storage"], "ci_proven")
        self.assertEqual(status["session_security"], "ci_proven")
        self.assertEqual(status["role_gates"], "ci_proven")
        self.assertEqual(status["consent_partner"], "ci_proven")
        self.assertEqual(status["migration_integrity"], "ci_proven")
        self.assertEqual(status["backup_restore"], "ci_proven")
        self.assertEqual(status["fail_closed_readiness"], "ci_proven")

    def test_unimplemented_enterprise_controls_stay_to_prepare(self):
        room = self.corporate.snapshot(self.c)
        status = {x["id"]: x["status"] for x in room["controls"]}
        for key in (
            "incident_runbook",
            "rto_rpo",
            "vendor_terms",
            "encryption_evidence",
            "dependency_security",
            "retention_deletion",
            "central_audit",
        ):
            self.assertEqual(status[key], "to_prepare")

    def test_data_inventory_does_not_invent_retention(self):
        room = self.corporate.snapshot(self.c)
        self.assertGreaterEqual(len(room["data_inventory"]), 6)
        self.assertTrue(all(x["production_retention"] == "to_define" for x in room["data_inventory"]))

    def test_vendor_answers_do_not_claim_certification(self):
        room = self.corporate.snapshot(self.c)
        cert = next(x for x in room["vendor_questions"] if x["id"] == "security_certifications")
        self.assertEqual(cert["answer_state"], "not_claimed")
        self.assertIn("No security certification is claimed", cert["answer"])

    def test_framework_crosswalk_is_reference_not_compliance_claim(self):
        room = self.corporate.snapshot(self.c)
        crosswalk = room["framework_crosswalk"]
        nist = [x for x in crosswalk if x["framework"] == "NIST CSF 2.0"]
        self.assertEqual({x["area"] for x in nist}, {"GOVERN", "IDENTIFY", "PROTECT", "DETECT", "RESPOND", "RECOVER"})
        asvs = next(x for x in crosswalk if x["framework"] == "OWASP ASVS 5.0.0")
        self.assertEqual(asvs["status"], "partial")
        self.assertIn("No full ASVS assessment", asvs["boundary"])
        self.assertTrue(all("certification" in x["boundary"].lower() or x["framework"].startswith("OWASP") for x in crosswalk if x["framework"] == "NIST CSF 2.0"))

    def test_procurement_requires_security_and_production_gates(self):
        room = self.corporate.snapshot(self.c)
        gates = {x["id"]: x["status"] for x in room["procurement_gates"]}
        self.assertEqual(gates["product_demo"], "complete")
        self.assertEqual(gates["technical_diligence"], "ci_proven")
        self.assertEqual(gates["production_persistence"], "blocking")
        self.assertEqual(gates["security_privacy_approval"], "to_prepare")
        self.assertEqual(gates["commercial_legal"], "to_prepare")
        self.assertEqual(gates["medical_governance"], "gated")


if __name__ == "__main__":
    unittest.main()
