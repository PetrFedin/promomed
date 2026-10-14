"""Proof that synthetic participant, partner and finance activity never unlocks real investor gates."""
import hashlib
import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import (client365, commercial_evidence_ledger as ledger,
                 evidence_interchange, partner_collaboration as collab,
                 pilot_revenue_ladder as ladder, strategic_reads, syndication_network)
from app.auth import seed_demo_accounts

ORG_A = "TRUTH-ORG-SYNTH-A"
ORG_B = "TRUTH-ORG-SYNTH-B"


class IntegratedTruthBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {
            "SQLITE_PATH": str(Path(self.temp.name) / "integration.sqlite"),
            "DATABASE_URL": "",
            "PROMOMED_SEED_DEMO": "true",
            "PROMOMED_REQUIRE_POSTGRES": "false",
        })
        self.environment.start()
        import app.db as db
        importlib.reload(db)
        self.db = db
        self.c = db.connect()
        db.migrate(self.c)
        seed_demo_accounts(self.c)
        for org in (ORG_A, ORG_B):
            evidence_interchange.register_organization(
                self.c, organization_id=org, name="Synthetic " + org,
                organization_type="strategic_partner",
                actor="governance@demo.ru",
                external_ref="urn:synthetic:" + org,
                credential_source="CI fixture only", demo_only=True,
            )
            syndication_network.bind_member(
                self.c, org, "organizer@demo.ru", "administrator",
                "governance@demo.ru", "test-verified-demo", demo_only=True,
            )
        syndication_network.bind_member(
            self.c, ORG_A, "partner@demo.ru", "operator",
            "governance@demo.ru", "test-verified-demo", demo_only=True,
        )
        self.c.commit()
        self.seq = 0

    def tearDown(self):
        self.c.rollback()
        self.c.close()
        self.environment.stop()
        self.temp.cleanup()

    def command(self, route, *, role="partner", actor="partner@demo.ru", **body):
        self.seq += 1
        result = collab.handle_command(
            self.c, route, role, actor,
            {"operation_id": "integrated-op-" + str(self.seq), **body},
        )
        if result.status < 400:
            self.c.commit()
        else:
            self.c.rollback()
        self.assertLess(result.status, 400, result.payload)
        return result.payload

    def test_internal_receipt_and_candidate_contract_leave_investor_gates_closed(self):
        pr = "/api/partner-collaboration"
        pid = self.command(
            pr + "/create", organization_id=ORG_A,
            title="Synthetic health Studio", format="studio",
        )["project_id"]
        tid = self.command(
            pr + "/task", project_id=pid,
            title="Prepare synthetic presentation", lane="partner",
        )["task_id"]
        self.command(pr + "/project", project_id=pid,
                     action="request_review", expected_version=1)
        self.command(pr + "/project", role="organizer",
                     actor="organizer@demo.ru", project_id=pid,
                     action="review", expected_version=2)
        self.command(pr + "/execute", project_id=pid, task_id=tid,
                     action="start", expected_version=1)
        self.command(
            pr + "/execute", project_id=pid, task_id=tid,
            action="submit", expected_version=2,
            evidence_ref="demo:studio-synthetic",
            evidence_sha256="a" * 64,
        )
        self.command(
            pr + "/execute", role="organizer",
            actor="organizer@demo.ru", project_id=pid, task_id=tid,
            action="accept", expected_version=3,
            decision_note="Internal demo check only",
        )
        internal = collab.snapshot(self.c, "partner", "partner@demo.ru", pid)
        self.assertEqual(internal["tasks"][0]["status"], "accepted")
        self.assertEqual(len(internal["receipts"]), 3)
        self.assertFalse(internal["contractAccepted"])
        self.assertFalse(internal["artifactIntegrityIndependentlyVerified"])

        contract = ledger.record_contract(
            self.c, organization_id=ORG_A, actor="organizer@demo.ru",
            external_ref="synthetic-studio-001", version=1,
            currency_code="RUB", net_amount_minor=987654,
            source_ref="demo:contract-claim",
            source_sha256=hashlib.sha256(b"synthetic document").hexdigest(),
            idempotency_key="integrated-synthetic-contract-001",
        )
        self.assertTrue(contract["created"])
        self.c.commit()
        a = ladder.snapshot(self.c, ORG_A, actor_email="organizer@demo.ru")
        b = ladder.snapshot(self.c, ORG_B, actor_email="organizer@demo.ru")
        self.assertTrue(a["organization"]["demoOnly"])
        self.assertEqual(a["sourceSignals"]["candidateContractVersions"], 1)
        self.assertEqual(a["candidatePortfolio"]["scope"], "EXACT_ORGANIZATION")
        self.assertEqual(a["candidatePortfolio"]["displayed"], 1)
        self.assertEqual(a["candidatePortfolio"]["items"][0]["sourceState"], "CANDIDATE_ONLY")
        self.assertIsNone(a["candidatePortfolio"]["items"][0]["financialActuals"])
        self.assertTrue(ledger.verify_chain(self.c, ORG_A, actor="organizer@demo.ru")["valid"])
        self.assertEqual(b["sourceSignals"]["candidateContractVersions"], 0)
        self.assertEqual(a["acceptanceSummary"]["acceptedStages"], 0)
        self.assertEqual(a["acceptanceSummary"]["decision"],
                         "HOLD_EXTERNAL_PILOT_AND_FINANCE_GATES")
        self.assertTrue(all(stage["state"] == "GATED" for stage in a["stages"]))
        self.assertIsNone(a["economics"]["recognizedRevenueRub"])
        self.assertIsNone(a["economics"]["cashCollectedRub"])
        self.assertIsNone(a["economics"]["contractedRub"])
        self.assertFalse(a["acceptanceSummary"]["capitalReleaseAuthorized"])

    def test_finance_reads_not_exposed_to_partner_or_other_tenants(self):
        contract = ledger.record_contract(
            self.c, organization_id=ORG_A, actor="organizer@demo.ru",
            external_ref="synthetic-finance-tenant-proof", version=1,
            currency_code="RUB", net_amount_minor=999900,
            source_ref="demo:unverified-contract",
            source_sha256=hashlib.sha256(b"candidate only").hexdigest(),
            idempotency_key="cross-domain-tenant-proof",
        )
        self.assertTrue(contract["created"])
        self.c.commit()
        route = "/api/pilot-revenue-ladder/" + ORG_A
        for role in ("partner", "participant", "sales", "staff"):
            with self.subTest(role=role):
                result, status = strategic_reads.read(
                    self.c, route, role, actor_email="partner@demo.ru"
                )
                self.assertEqual((result, status), ({"error": "forbidden"}, 403))
                self.assertNotIn("999900", str(result))
        unauthorised, status = strategic_reads.read(
            self.c, route, "organizer", actor_email="unbound@example.test"
        )
        self.assertEqual((unauthorised, status),
                         ({"error": "organization_not_found"}, 404))
        permitted, status = strategic_reads.read(
            self.c, route, "organizer", actor_email="organizer@demo.ru"
        )
        self.assertEqual(status, 200)
        self.assertEqual(permitted["candidatePortfolio"]["displayed"], 1)
        self.assertFalse(permitted["candidatePortfolio"]["items"][0]["signedContractVerified"])
        self.assertEqual(permitted["candidatePortfolio"]["financialAuthority"], "NONE")
        self.assertIsNone(permitted["economics"]["recognizedRevenueRub"])
        other, status = strategic_reads.read(
            self.c, "/api/pilot-revenue-ladder/" + ORG_B,
            "organizer", actor_email="organizer@demo.ru",
        )
        self.assertEqual(status, 200)
        self.assertEqual(other["candidatePortfolio"]["items"], [])
        self.assertEqual(other["sourceSignals"]["candidateContractVersions"], 0)
        self.assertTrue(ledger.verify_chain(self.c, ORG_A,
                                            actor="organizer@demo.ru")["valid"])

    def test_cancelled_organization_membership_revokes_partner_and_finance_views(self):
        self.c.execute(
            "UPDATE institutional_memberships SET status='suspended' "
            "WHERE organization_id=? AND account_email=?",
            (ORG_A, "organizer@demo.ru"),
        )
        self.c.commit()
        result, status = strategic_reads.read(
            self.c, "/api/pilot-revenue-ladder/" + ORG_A,
            "organizer", actor_email="organizer@demo.ru",
        )
        self.assertEqual((result, status),
                         ({"error": "organization_not_found"}, 404))
        self.assertIsNone(
            ledger.snapshot(self.c, ORG_B, actor="organizer@demo.ru")["recognizedRevenue"]
        )

    def test_demo_client_timeline_never_means_retention_or_partner_lead(self):
        private_marker = "PRIVATE-ACCOUNT-NOTE-DO-NOT-EXPORT"
        self.c.execute(
            "INSERT INTO takeaways(email,session_id,note,source,ts) "
            "VALUES(?,'SYNTH',?,'private',1)",
            ("participant@demo.ru", private_marker),
        )
        self.c.commit()
        personal = client365.snapshot(self.c, "participant@demo.ru")
        self.assertTrue(personal["demoOnly"])
        self.assertIsNone(personal["truthBoundary"]["cohortRetentionRate"])
        self.assertIsNone(personal["truthBoundary"]["recognizedRevenue"])
        a = ladder.snapshot(self.c, ORG_A, actor_email="organizer@demo.ru")
        self.assertNotIn(private_marker, str(personal))
        self.assertNotIn(private_marker, str(a))
        self.assertNotIn("participant@demo.ru", str(a))
        self.assertFalse(a["acceptanceSummary"]["externalParticipationAccepted"])

    def test_all_migrations_coexist_and_have_immutable_checksums(self):
        st = self.db.migration_status(self.c)
        for name in (
            "026_commercial_evidence_ledger", "026_partner_collaboration",
            "027_partner_task_execution", "028_partner_organization_tenancy",
            "029_auth_session_revocation",
        ):
            self.assertIn(name, st["applied"])
        self.assertTrue(st["schema_ready"], st)
        self.db.migrate(self.c)
        self.assertEqual(self.db.migration_status(self.c)["checksum_drift"], [])


if __name__ == "__main__":
    unittest.main()
