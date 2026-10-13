import importlib
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import evidence_interchange, pilot_revenue_ladder, strategic_reads, commercial_evidence_ledger


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
        for org, demo in (("INST-LADDER-A-001", 0), ("INST-LADDER-B-001", 0),
                          ("INST-LADDER-DEMO", 1)):
            self.c.execute(
                """INSERT INTO institutional_memberships
                   (id,organization_id,account_email,member_role,status,effective_at,
                    expires_at,verified_by,verification_ref,demo_only)
                   VALUES(?,?,?,'administrator','active',1,NULL,'test','synthetic membership fixture',?)""",
                ("test-member:"+org, org, "scoped-organizer@example.test", demo),
            )
        self.c.commit()

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.tmp.cleanup()

    def _record_candidate(self, ref, amount=20000):
        return commercial_evidence_ledger.record_contract(
            self.c, organization_id="INST-LADDER-DEMO",
            actor="scoped-organizer@example.test",
            external_ref=ref, version=1, currency_code="RUB",
            net_amount_minor=amount, source_ref="fixture:"+ref,
            source_sha256=hashlib.sha256(ref.encode("utf-8")).hexdigest(),
            idempotency_key="candidate:"+ref,
        )["id"]

    def test_candidate_document_coverage_is_metadata_not_finance(self):
        cid=self._record_candidate("candidate-coverage-a")
        commercial_evidence_ledger.record_event(
            self.c,organization_id="INST-LADDER-DEMO",
            actor="scoped-organizer@example.test",contract_id=cid,
            event_type="obligation",external_ref="ob-a",version=1,
            amount_minor=5000,source_ref="fixture:ob",
            source_sha256=hashlib.sha256(b"ob-a").hexdigest(),
            idempotency_key="candidate:ob-a",
        )
        self.c.commit()
        scoped=pilot_revenue_ladder.snapshot(
            self.c,"INST-LADDER-DEMO",actor_email="scoped-organizer@example.test")
        candidate=scoped["candidatePortfolio"]
        self.assertEqual(candidate["scope"],"EXACT_ORGANIZATION")
        self.assertEqual(candidate["sourceState"],"CANDIDATE_ONLY")
        self.assertEqual(candidate["financialAuthority"],"NONE")
        self.assertFalse(candidate["truncated"])
        self.assertEqual(candidate["displayed"],1)
        self.assertEqual(candidate["items"][0]["contractDocumentId"],cid)
        self.assertEqual(candidate["items"][0]["eventVersions"]["obligation"],1)
        self.assertEqual(candidate["items"][0]["eventVersions"]["invoice"],0)
        self.assertIsNone(candidate["items"][0]["financialActuals"])
        self.assertFalse(candidate["items"][0]["signedContractVerified"])
        self.assertEqual(scoped["acceptanceSummary"]["acceptedStages"],0)
        self.assertIsNone(scoped["economics"]["contractedRub"])
        self.assertEqual(scoped["sourceSignals"]["candidateContractVersions"],1)
        self.assertEqual(scoped["sourceSignals"]["candidateDocumentVersions"],1)
        other=pilot_revenue_ladder.snapshot(
            self.c,"INST-LADDER-A-001",actor_email="scoped-organizer@example.test")
        self.assertEqual(other["candidatePortfolio"]["items"],[])
        self.assertEqual(other["sourceSignals"]["candidateDocumentVersions"],0)

    def test_candidate_list_is_bounded_and_does_not_leak_unapproved_money(self):
        for n in range(22):
            self._record_candidate("many-"+str(n))
        result=pilot_revenue_ladder.snapshot(
            self.c,"INST-LADDER-DEMO",actor_email="scoped-organizer@example.test")
        visible=result["candidatePortfolio"]
        self.assertEqual(visible["displayed"],20)
        self.assertEqual(len(visible["items"]),20)
        self.assertTrue(visible["truncated"])
        self.assertEqual(
            len({x["contractDocumentId"] for x in visible["items"]}),20)
        self.assertIsNone(result["economics"]["invoicedRub"])
        self.assertFalse(result["acceptanceSummary"]["capitalReleaseAuthorized"])
        with self.assertRaisesRegex(ValueError,"organization_not_found"):
            pilot_revenue_ladder.snapshot(
                self.c,"INST-LADDER-DEMO",actor_email="not-member@example.test")

    def test_absent_financial_evidence_is_null_not_zero(self):
        d = pilot_revenue_ladder.snapshot(self.c, "INST-LADDER-A-001", actor_email="scoped-organizer@example.test")
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
        a = pilot_revenue_ladder.snapshot(self.c, "INST-LADDER-A-001", actor_email="scoped-organizer@example.test")
        b = pilot_revenue_ladder.snapshot(self.c, "INST-LADDER-B-001", actor_email="scoped-organizer@example.test")
        self.assertEqual(a["sourceSignals"]["technicalEvidenceAcknowledgements"], 1)
        self.assertEqual(b["sourceSignals"]["technicalEvidenceAcknowledgements"], 0)
        for s in a["stages"]:
            self.assertEqual(s["state"], "GATED")
        self.assertIsNone(a["economics"]["recognizedRevenueRub"])
        self.assertFalse(a["acceptanceSummary"]["capitalReleaseAuthorized"])

    def test_demo_metadata_not_promoted_to_real_identity(self):
        d = pilot_revenue_ladder.snapshot(self.c, "INST-LADDER-DEMO", actor_email="scoped-organizer@example.test")
        self.assertTrue(d["organization"]["demoOnly"])
        self.assertFalse(d["sourceSignals"]["nonDemoIdentityMetadata"])
        self.assertFalse(d["acceptanceSummary"]["externalParticipationAccepted"])

    def test_org_scope_and_identifier_are_strict(self):
        for bad in ("", "../INST-LADDER-A-001", "INST/LADDER",
                    " " * 4, "a" * 101, "org%2FA"):
            with self.assertRaises(ValueError):
                pilot_revenue_ladder.snapshot(self.c, bad, actor_email="scoped-organizer@example.test")
        with self.assertRaisesRegex(ValueError, "organization_not_found"):
            pilot_revenue_ladder.snapshot(self.c, "UNKNOWN-INSTITUTION", actor_email="scoped-organizer@example.test")

    def test_read_route_is_organizer_only_and_no_existence_leak(self):
        path = "/api/pilot-revenue-ladder/INST-LADDER-A-001"
        for role in ("participant", "partner", "sales", "staff", "editor"):
            payload, status = strategic_reads.read(self.c, path, role, actor_email="scoped-organizer@example.test")
            self.assertEqual((payload, status), ({"error": "forbidden"}, 403))
            missing, missing_status = strategic_reads.read(
                self.c, "/api/pilot-revenue-ladder/UNKNOWN-INSTITUTION", role,
                actor_email="scoped-organizer@example.test"
            )
            self.assertEqual((missing, missing_status), ({"error": "forbidden"}, 403))
        data, status = strategic_reads.read(self.c, path, "organizer", actor_email="scoped-organizer@example.test")
        self.assertEqual(status, 200)
        self.assertEqual(data["organization"]["id"], "INST-LADDER-A-001")
        bad, bad_status = strategic_reads.read(
            self.c, "/api/pilot-revenue-ladder/UNKNOWN-INSTITUTION", "organizer",
            actor_email="scoped-organizer@example.test"
        )
        self.assertEqual((bad, bad_status), ({"error": "organization_not_found"}, 404))
        invalid, invalid_status = strategic_reads.read(
            self.c, "/api/pilot-revenue-ladder/INST%2FLADDER", "organizer",
            actor_email="scoped-organizer@example.test"
        )
        self.assertEqual(invalid_status, 422)

    def test_membership_denial_does_not_reveal_organization_existence(self):
        route = "/api/pilot-revenue-ladder/INST-LADDER-A-001"
        for account in ("unbound@example.test", "", "scoped-organizer@demo.ru"):
            d, status = strategic_reads.read(
                self.c, route, "organizer", actor_email=account)
            self.assertEqual((d, status), ({"error": "organization_not_found"}, 404))
        with self.assertRaisesRegex(ValueError, "organization_not_found"):
            pilot_revenue_ladder.snapshot(self.c, "INST-LADDER-A-001")

    def test_demo_login_cannot_enter_non_demo_even_if_membership_is_misconfigured(self):
        self.c.execute(
            """INSERT INTO institutional_memberships
               (id,organization_id,account_email,member_role,status,effective_at,
                expires_at,verified_by,verification_ref,demo_only)
               VALUES(?,?,?,'administrator','active',1,NULL,'test','invalid admin assignment',0)""",
            ("bad-demo-member", "INST-LADDER-A-001", "demo-organizer@demo.ru"),
        )
        self.c.commit()
        payload, status = strategic_reads.read(
            self.c, "/api/pilot-revenue-ladder/INST-LADDER-A-001",
            "organizer", actor_email="demo-organizer@demo.ru",
        )
        self.assertEqual((payload, status), ({"error": "organization_not_found"}, 404))

    def test_suspended_membership_denied(self):
        self.c.execute(
            "UPDATE institutional_memberships SET status='suspended' "
            "WHERE organization_id=? AND account_email=?",
            ("INST-LADDER-A-001", "scoped-organizer@example.test"),
        )
        self.c.commit()
        denied, status = strategic_reads.read(
            self.c, "/api/pilot-revenue-ladder/INST-LADDER-A-001",
            "organizer", actor_email="scoped-organizer@example.test",
        )
        self.assertEqual((denied, status), ({"error": "organization_not_found"}, 404))

    def test_evidence_request_export_is_deterministic_and_not_signature(self):
        x = pilot_revenue_ladder.snapshot(self.c, "INST-LADDER-A-001", actor_email="scoped-organizer@example.test")
        y = pilot_revenue_ladder.snapshot(self.c, "INST-LADDER-A-001", actor_email="scoped-organizer@example.test")
        self.assertEqual(x["evidenceRequestPack"]["sha256"], y["evidenceRequestPack"]["sha256"])
        self.assertEqual(len(x["evidenceRequestPack"]["sha256"]), 64)
        doc = x["evidenceRequestPack"]["document"]
        self.assertTrue(doc["truthBoundary"]["noPaymentOrContractAuthority"])
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
        self.assertIn('id="candidateCards"', html)
        self.assertIn('id="candidateStatus"', html)
        self.assertIn("candidate-custody-summary-v1", js)
        self.assertIn("renderCandidatePortfolio(data.candidatePortfolio)", js)
        self.assertIn("candidate-card", css)
        self.assertIn("candidatePortfolio", (root / "app" / "pilot_revenue_ladder.py").read_text(encoding="utf-8"))

    def test_schema_remains_25_migrations_no_unverified_finance_ledger(self):
        root = Path(__file__).resolve().parents[1]
        postgres = sorted((root / "migrations" / "postgres").glob("*.sql"))
        sqlite = sorted((root / "migrations" / "sqlite").glob("*.sql"))
        self.assertGreaterEqual(len(postgres), 25)
        self.assertEqual([p.name for p in postgres], [p.name for p in sqlite])
        ladder = (root / "app" / "pilot_revenue_ladder.py").read_text(encoding="utf-8")
        self.assertNotIn("INSERT INTO", ladder)
        self.assertNotIn("UPDATE institutional_", ladder)
        self.assertIn("organization_id=?", ladder)
        self.assertIn("NO_ACCEPTED_COMMERCIAL_AUTHORITY", ladder)


if __name__ == "__main__":
    unittest.main()
