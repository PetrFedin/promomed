import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import evidence_interchange, pilot_revenue_ladder, strategic_reads


class PilotRevenueEvidenceLadderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "SQLITE_PATH": str(Path(self.tmp.name) / "commercial-ladder.db"),
            "PROMOMED_SEED_DEMO": "true",
            "DATABASE_URL": "",
            "PROMOMED_REQUIRE_POSTGRES": "false",
        })
        self.env.start()
        from app import db
        importlib.reload(db)
        self.db = db
        self.c = db.connect()
        db.migrate(self.c)
        for org in ("INST-LADDER-A-001", "INST-LADDER-B-001"):
            evidence_interchange.register_organization(
                self.c, organization_id=org,
                name="Synthetic scoped " + org[-1:],
                organization_type="strategic_partner",
                actor="fixture@demo.ru", external_ref="urn:synthetic:" + org,
                credential_source="test fixture only", demo_only=False,
            )
        evidence_interchange.register_organization(
            self.c, organization_id="INST-LADDER-DEMO",
            name="Synthetic demonstration entity",
            organization_type="strategic_partner", actor="fixture@demo.ru",
            external_ref="urn:demo:institution", credential_source="demo fixture",
            demo_only=True,
        )
        self.c.commit()

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.tmp.cleanup()

    def test_absent_financial_evidence_is_null_not_zero(self):
        d = pilot_revenue_ladder.snapshot(self.c, "INST-LADDER-A-001")
        self.assertEqual(d["version"], pilot_revenue_ladder.VERSION)
        self.assertEqual(len(d["stages"]), 7)
        self.assertTrue(all(x["state"] == "GATED" for x in d["stages"]))
        self.assertFalse(any(x["commercialAcceptance"] for x in d["stages"]))
        values = d["economics"]
        for key in ("contractedRub", "invoicedRub", "cashCollectedRub",
                    "recognizedRevenueRub", "directCostsRub",
                    "acceptedContributionRub", "renewalRevenueRub"):
            self.assertIsNone(values[key], key)
        self.assertEqual(values["nullSemantics"], "NOT_VERIFIED_NOT_ZERO")
        self.assertEqual(d["acceptanceSummary"]["acceptedStages"], 0)
        self.assertFalse(d["acceptanceSummary"]["capitalReleaseAuthorized"])
        self.assertFalse(d["acceptanceSummary"]["financeAccepted"])
        self.assertFalse(d["acceptanceSummary"]["productionRevenueClaimed"])

    def test_proposal_and_technical_ack_do_not_unlock_commercial_states(self):
        self.c.execute(
            """INSERT INTO evidence_exchange_deliveries
               (id,package_id,organization_id,delivery_role,status,delivered_at,
                acknowledged_at,receipt_sha256,created_by,demo_only)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            ("ladder-ack-a", "synthetic-package", "INST-LADDER-A-001",
             "consumer", "acknowledged", 123, 124, "synthetic-receipt-sha",
             "test", 0),
        )
        self.c.commit()
        a = pilot_revenue_ladder.snapshot(self.c, "INST-LADDER-A-001")
        b = pilot_revenue_ladder.snapshot(self.c, "INST-LADDER-B-001")
        self.assertEqual(a["sourceSignals"]["technicalEvidenceAcknowledgements"], 1)
        self.assertEqual(b["sourceSignals"]["technicalEvidenceAcknowledgements"], 0)
        for s in a["stages"]:
            self.assertEqual(s["state"], "GATED")
        self.assertIsNone(a["economics"]["recognizedRevenueRub"])
        self.assertFalse(a["acceptanceSummary"]["capitalReleaseAuthorized"])

    def test_demo_metadata_not_promoted_to_real_identity(self):
        d = pilot_revenue_ladder.snapshot(self.c, "INST-LADDER-DEMO")
        self.assertTrue(d["organization"]["demoOnly"])
        self.assertFalse(d["sourceSignals"]["nonDemoIdentityMetadata"])
        self.assertFalse(d["acceptanceSummary"]["externalParticipationAccepted"])

    def test_org_scope_and_identifier_are_strict(self):
        for bad in ("", "../INST-LADDER-A-001", "INST/LADDER",
                    " " * 4, "a" * 101, "org%2FA"):
            with self.assertRaises(ValueError):
                pilot_revenue_ladder.snapshot(self.c, bad)
        with self.assertRaisesRegex(ValueError, "organization_not_found"):
            pilot_revenue_ladder.snapshot(self.c, "UNKNOWN-INSTITUTION")

    def test_read_route_is_organizer_only_and_no_existence_leak(self):
        path = "/api/pilot-revenue-ladder/INST-LADDER-A-001"
        for role in ("participant", "partner", "sales", "staff", "editor"):
            payload, status = strategic_reads.read(self.c, path, role)
            self.assertEqual((payload, status), ({"error": "forbidden"}, 403))
            missing, missing_status = strategic_reads.read(
                self.c, "/api/pilot-revenue-ladder/UNKNOWN-INSTITUTION", role
            )
            self.assertEqual((missing, missing_status), ({"error": "forbidden"}, 403))
        data, status = strategic_reads.read(self.c, path, "organizer")
        self.assertEqual(status, 200)
        self.assertEqual(data["organization"]["id"], "INST-LADDER-A-001")
        bad, bad_status = strategic_reads.read(
            self.c, "/api/pilot-revenue-ladder/UNKNOWN-INSTITUTION", "organizer"
        )
        self.assertEqual((bad, bad_status), ({"error": "organization_not_found"}, 404))
        invalid, invalid_status = strategic_reads.read(
            self.c, "/api/pilot-revenue-ladder/INST%2FLADDER", "organizer"
        )
        self.assertEqual(invalid_status, 422)

    def test_evidence_request_export_is_deterministic_and_not_signature(self):
        x = pilot_revenue_ladder.snapshot(self.c, "INST-LADDER-A-001")
        y = pilot_revenue_ladder.snapshot(self.c, "INST-LADDER-A-001")
        self.assertEqual(x["evidenceRequestPack"]["sha256"], y["evidenceRequestPack"]["sha256"])
        self.assertEqual(len(x["evidenceRequestPack"]["sha256"]), 64)
        doc = x["evidenceRequestPack"]["document"]
        self.assertFalse(doc["truthBoundary"]["noPaymentOrContractAuthority"] is False)
        self.assertEqual(doc["acceptanceSummary"]["decision"], "HOLD_EXTERNAL_PILOT_AND_FINANCE_GATES")


class LadderUIContractTests(unittest.TestCase):
    def test_page_and_navigation_are_connected(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "public" / "pilot-revenue-ladder.html").read_text(encoding="utf-8")
        js = (root / "public" / "pilot-revenue-ladder.js").read_text(encoding="utf-8")
        css = (root / "public" / "pilot-revenue-ladder.css").read_text(encoding="utf-8")
        nav = (root / "public" / "institutional-shell.js").read_text(encoding="utf-8")
        self.assertIn("pilot-revenue-ladder.html", nav)
        self.assertIn("institutional-shell.js", html)
        self.assertEqual(html.count('class="stage-control'), 7)
        for role in ("pilot_acceptance","contract","delivery","invoice","cash","finance","renewal"):
            self.assertIn('data-step="' + role + '"', html)
        self.assertIn('id="metricRevenue"', html)
        self.assertIn('id="scopedProof" hidden', html)
        self.assertIn("Organization ID", html.replace("ORGANIZATION ID", "Organization ID"))
        self.assertIn("@media(max-width:650px)", css)
        self.assertIn("@media(prefers-reduced-motion:reduce)", css)
        self.assertNotIn(".innerHTML", js)
        self.assertNotIn("localStorage", js)
        self.assertNotIn("sessionStorage", js)
        self.assertIn('credentials:"omit"', js)
        self.assertIn('auth.role!=="organizer"', js)
        self.assertIn('state:"GATED"', js)
        self.assertIn("revenue", js.lower())

    def test_schema_remains_25_migrations_no_unverified_finance_ledger(self):
        root = Path(__file__).resolve().parents[1]
        postgres = sorted((root / "migrations" / "postgres").glob("*.sql"))
        sqlite = sorted((root / "migrations" / "sqlite").glob("*.sql"))
        self.assertEqual(len(postgres), 25)
        self.assertEqual(len(sqlite), 25)
        ladder = (root / "app" / "pilot_revenue_ladder.py").read_text(encoding="utf-8")
        self.assertNotIn("INSERT INTO", ladder)
        self.assertNotIn("UPDATE institutional_", ladder)
        self.assertIn("organization_id=?", ladder)
        self.assertIn("NO_ACCEPTED_COMMERCIAL_AUTHORITY", ladder)


if __name__ == "__main__":
    unittest.main()
