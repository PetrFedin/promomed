import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import evidence_interchange, institutional_command_center, strategic_reads, syndication_network
from app.auth import seed_demo_accounts


class InstitutionalCommandCenterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ,
            {
                "SQLITE_PATH": str(Path(self.tmp.name) / "command-center.db"),
                "PROMOMED_SEED_DEMO": "true",
            },
            clear=False,
        )
        self.env.start()
        import app.db as db

        importlib.reload(db)
        self.c = db.connect()
        db.migrate(self.c)
        seed_demo_accounts(self.c)
        evidence_interchange.register_organization(
            self.c,
            organization_id="INST-COMMAND-DEMO-001",
            name="Synthetic Command Center Institution",
            organization_type="strategic_partner",
            actor="governance@demo.ru",
            external_ref="urn:synthetic:command-center:001",
            credential_source="synthetic test fixture",
            demo_only=True,
        )
        syndication_network.bind_member(
            self.c,
            "INST-COMMAND-DEMO-001",
            "participant2@demo.ru",
            "administrator",
            "governance@demo.ru",
            "synthetic-membership-proof",
            demo_only=True,
        )
        evidence_interchange.bind_role(
            self.c,
            organization_id="INST-COMMAND-DEMO-001",
            role_scope="consumer",
            actor="governance@demo.ru",
            verification_ref="synthetic-role-proof",
            demo_only=True,
        )
        self.c.commit()

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.tmp.cleanup()

    def test_executive_composition_has_required_domains(self):
        result = institutional_command_center.snapshot(self.c, "INST-COMMAND-DEMO-001")
        self.assertEqual(set(result["domains"]), {"pilot", "procurement", "legal", "security"})
        for domain in result["domains"].values():
            self.assertIn(domain["status"], ("BLOCKED", "READY_FOR_DECISION", "NO_ACTIVE_ITEMS"))
            self.assertIn("blockers", domain)
            self.assertIn("readyForDecision", domain)

    def test_participation_acceptance_is_hard_stop(self):
        result = institutional_command_center.snapshot(self.c, "INST-COMMAND-DEMO-001")
        participation = next(x for x in result["criticalPath"] if x["id"] == "participation_acceptance")
        self.assertTrue(participation["hardStop"])
        self.assertFalse(participation["parallelizable"])
        self.assertEqual(participation["status"], "BLOCKED")
        self.assertEqual(result["executiveSummary"]["verdict"], "HARD_STOP_PARTICIPATION_ACCEPTANCE_MISSING")
        self.assertEqual(result["truthBoundary"]["externalParticipationAcceptance"], "GATED")

    def test_ready_for_decision_never_becomes_approval(self):
        result = institutional_command_center.snapshot(self.c, "INST-COMMAND-DEMO-001")
        self.assertFalse(result["truthBoundary"]["readyForDecisionEqualsApproved"])
        for item in result["readyForDecision"]:
            self.assertFalse(item["approved"])

    def test_owner_queue_and_parallel_tracks_are_planning_only(self):
        result = institutional_command_center.snapshot(self.c, "INST-COMMAND-DEMO-001")
        self.assertTrue(result["ownerQueue"])
        self.assertEqual({x["id"] for x in result["parallelTracks"]}, {"technical", "security_legal", "commercial"})
        self.assertTrue(all(x["canProceedInParallel"] for x in result["parallelTracks"]))
        self.assertTrue(result["truthBoundary"]["parallelTracksArePlanningOnly"])
        self.assertTrue(result["truthBoundary"]["criticalPathIsProjection"])

    def test_impossible_without_participation_is_explicit(self):
        result = institutional_command_center.snapshot(self.c, "INST-COMMAND-DEMO-001")
        impossible = " ".join(result["impossibleWithoutParticipation"]).lower()
        self.assertIn("real institutional pilot commitment", impossible)
        self.assertIn("approved", impossible)
        self.assertIn("contract", impossible)
        self.assertFalse(result["truthBoundary"]["contractOrRevenueClaimed"])
        self.assertFalse(result["truthBoundary"]["realPilotClaimed"])

    def test_export_is_deterministic(self):
        first = institutional_command_center.snapshot(self.c, "INST-COMMAND-DEMO-001", now=1234567890)
        second = institutional_command_center.snapshot(self.c, "INST-COMMAND-DEMO-001", now=1234567890)
        self.assertEqual(first["export"]["sha256"], second["export"]["sha256"])
        self.assertEqual(len(first["export"]["sha256"]), 64)

    def test_guarded_strategic_route(self):
        path = "/api/institutional-command-center/INST-COMMAND-DEMO-001"
        payload, status = strategic_reads.read(self.c, path, "sales")
        self.assertEqual(status, 200)
        self.assertEqual(payload["organization"]["id"], "INST-COMMAND-DEMO-001")

        forbidden, status = strategic_reads.read(self.c, path, "participant")
        self.assertEqual(status, 403)
        self.assertEqual(forbidden["error"], "forbidden")


if __name__ == "__main__":
    unittest.main()
