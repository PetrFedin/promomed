import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import evidence_interchange, institutional_working_session, syndication_network
from app.auth import seed_demo_accounts


class InstitutionalWorkingSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "SQLITE_PATH":str(Path(self.tmp.name)/"working-session.db"),
            "PROMOMED_SEED_DEMO":"true",
        },clear=False)
        self.env.start()
        import app.db as db
        importlib.reload(db)
        self.c=db.connect()
        db.migrate(self.c)
        seed_demo_accounts(self.c)
        evidence_interchange.register_organization(
            self.c,
            organization_id="INST-WORK-DEMO-001",
            name="Synthetic Working Session Institution",
            organization_type="strategic_partner",
            actor="governance@demo.ru",
            external_ref="urn:synthetic:working-session:001",
            credential_source="synthetic test fixture",
            demo_only=True,
        )
        syndication_network.bind_member(
            self.c,"INST-WORK-DEMO-001","participant2@demo.ru","administrator",
            "governance@demo.ru","synthetic-membership-proof",demo_only=True
        )
        evidence_interchange.bind_role(
            self.c,
            organization_id="INST-WORK-DEMO-001",
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

    def test_session_stays_read_only(self):
        result=institutional_working_session.snapshot(self.c,"INST-WORK-DEMO-001")
        self.assertTrue(result["truthBoundary"]["readOnly"])
        self.assertFalse(result["truthBoundary"]["documentReceiptPersisted"])
        self.assertFalse(result["truthBoundary"]["questionAnswerPersisted"])
        self.assertFalse(result["truthBoundary"]["ownerAssignmentAccepted"])
        self.assertFalse(result["truthBoundary"]["approvalPersisted"])

    def test_participation_acceptance_is_gated(self):
        result=institutional_working_session.snapshot(self.c,"INST-WORK-DEMO-001")
        self.assertEqual(result["truthBoundary"]["externalParticipationAcceptance"],"GATED")
        req=next(x for x in result["documentRequests"] if x["id"]=="participation_acceptance")
        self.assertEqual(req["state"],"gated")
        route=next(x for x in result["questionRoutes"] if x["topic"]=="participation")
        self.assertEqual(route["state"],"gated")

    def test_roles_do_not_approve(self):
        result=institutional_working_session.snapshot(self.c,"INST-WORK-DEMO-001")
        self.assertGreaterEqual(len(result["participantRoles"]),5)
        self.assertTrue(all(not x["canApprove"] for x in result["participantRoles"]))

    def test_gap_ownership_is_not_acceptance(self):
        result=institutional_working_session.snapshot(self.c,"INST-WORK-DEMO-001")
        self.assertTrue(result["gapOwnership"])
        self.assertTrue(all(not x["resolutionCanBeAcceptedHere"] for x in result["gapOwnership"]))

    def test_export_is_deterministic(self):
        first=institutional_working_session.snapshot(self.c,"INST-WORK-DEMO-001",now=1234567890)
        second=institutional_working_session.snapshot(self.c,"INST-WORK-DEMO-001",now=1234567890)
        self.assertEqual(first["export"]["sha256"],second["export"]["sha256"])
        self.assertEqual(len(first["export"]["sha256"]),64)


if __name__=="__main__":
    unittest.main()
