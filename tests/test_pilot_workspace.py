import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import evidence_interchange, pilot_workspace, syndication_network
from app.auth import seed_demo_accounts


class InstitutionalPilotWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "SQLITE_PATH":str(Path(self.tmp.name)/"pilot-workspace.db"),
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
            organization_id="INST-PILOT-DEMO-001",
            name="Synthetic Pilot Institution",
            organization_type="university",
            actor="governance@demo.ru",
            external_ref="urn:synthetic:pilot:001",
            credential_source="synthetic test fixture",
            demo_only=True,
        )
        syndication_network.bind_member(
            self.c,
            "INST-PILOT-DEMO-001",
            "participant2@demo.ru",
            "administrator",
            "governance@demo.ru",
            "synthetic-membership-proof",
            demo_only=True,
        )
        evidence_interchange.bind_role(
            self.c,
            organization_id="INST-PILOT-DEMO-001",
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

    def _counts(self):
        tables=(
            "institutional_organizations",
            "institutional_memberships",
            "institutional_role_bindings",
            "syndication_partner_qualifications",
            "institutional_federated_anchors",
            "federation_profile_evaluations",
            "federation_discovery_bundles",
            "syndication_delivery_endpoints",
        )
        return {
            table:self.c.execute(f"SELECT COUNT(*) n FROM {table}").fetchone()["n"]
            for table in tables
        }

    def test_demo_organization_is_never_presented_as_external_pilot_ready(self):
        result=pilot_workspace.snapshot(self.c,"INST-PILOT-DEMO-001")
        self.assertEqual(result["readiness"],"blocked")
        self.assertTrue(result["organization"]["demoOnly"])
        identity=next(x for x in result["steps"] if x["key"]=="institution_identity")
        self.assertEqual(identity["state"],"demo_only")
        self.assertEqual(identity["blocker"],"demo_organization_cannot_be_external_pilot")
        self.assertIn("demo_organization_cannot_be_external_pilot",result["blockers"])
        self.assertFalse(result["truthBoundary"]["externalAdoptionInferred"])
        self.assertFalse(result["truthBoundary"]["demoOrganizationCanBecomeRealPilot"])

    def test_workspace_is_read_only_over_existing_authorities(self):
        before=self._counts()
        first=pilot_workspace.snapshot(self.c,"INST-PILOT-DEMO-001")
        second=pilot_workspace.snapshot(self.c,"INST-PILOT-DEMO-001")
        after=self._counts()
        self.assertEqual(before,after)
        self.assertEqual(first["blockers"],second["blockers"])
        self.assertTrue(first["truthBoundary"]["readOnlyProjection"])
        self.assertFalse(first["truthBoundary"]["admitsTrustAnchor"])
        self.assertFalse(first["truthBoundary"]["changesQualification"])

    def test_participation_evidence_remains_explicitly_gated(self):
        result=pilot_workspace.snapshot(self.c,"INST-PILOT-DEMO-001")
        participation=next(
            x for x in result["steps"] if x["key"]=="participation_evidence"
        )
        self.assertTrue(participation["required"])
        self.assertEqual(participation["state"],"blocked")
        self.assertEqual(
            participation["blocker"],
            "no_canonical_participation_evidence_authority_implemented_until_real_participant_exists",
        )

    def test_missing_organization_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"organization_not_found"):
            pilot_workspace.snapshot(self.c,"INST-NOT-THERE")


if __name__=="__main__":
    unittest.main()
