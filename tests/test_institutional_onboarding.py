import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import evidence_interchange, institutional_onboarding, syndication_network
from app.auth import seed_demo_accounts


class InstitutionalOnboardingRoomTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "SQLITE_PATH":str(Path(self.tmp.name)/"onboarding.db"),
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
            organization_id="INST-ONBOARD-DEMO-001",
            name="Synthetic Onboarding Institution",
            organization_type="university",
            actor="governance@demo.ru",
            external_ref="urn:synthetic:onboarding:001",
            credential_source="synthetic test fixture",
            demo_only=True,
        )
        syndication_network.bind_member(
            self.c,"INST-ONBOARD-DEMO-001","participant2@demo.ru","administrator",
            "governance@demo.ru","synthetic-membership-proof",demo_only=True
        )
        evidence_interchange.bind_role(
            self.c,
            organization_id="INST-ONBOARD-DEMO-001",
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
            "institutional_organizations","institutional_memberships",
            "institutional_role_bindings","syndication_partner_qualifications",
            "institutional_federated_anchors","federation_profile_evaluations",
            "federation_discovery_bundles","syndication_delivery_endpoints",
        )
        return {t:self.c.execute(f"SELECT COUNT(*) n FROM {t}").fetchone()["n"] for t in tables}

    def test_demo_room_never_claims_real_pilot(self):
        room=institutional_onboarding.snapshot(self.c,"INST-ONBOARD-DEMO-001")
        self.assertEqual(room["overallState"],"demo_only_workthrough")
        self.assertTrue(room["organization"]["demoOnly"])
        self.assertFalse(room["truthBoundary"]["realPilotClaimed"])
        self.assertFalse(room["truthBoundary"]["commercialRelationshipClaimed"])
        external=next(x for x in room["sections"] if x["key"]=="external_participation_acceptance")
        self.assertEqual(external["state"],"gated")

    def test_room_is_read_only(self):
        before=self._counts()
        first=institutional_onboarding.snapshot(self.c,"INST-ONBOARD-DEMO-001")
        second=institutional_onboarding.snapshot(self.c,"INST-ONBOARD-DEMO-001")
        after=self._counts()
        self.assertEqual(before,after)
        self.assertEqual(
            first["procurementEvidencePack"]["packSha256"],
            second["procurementEvidencePack"]["packSha256"],
        )
        self.assertTrue(first["truthBoundary"]["readOnlyOrchestration"])

    def test_procurement_pack_truth_boundary_is_explicit(self):
        room=institutional_onboarding.snapshot(self.c,"INST-ONBOARD-DEMO-001")
        pack=room["procurementEvidencePack"]
        truth=pack["pack"]["truthBoundary"]
        self.assertEqual(len(pack["packSha256"]),64)
        self.assertFalse(truth["securityCertificationClaimed"])
        self.assertFalse(truth["accreditationClaimed"])
        self.assertFalse(truth["medicalEfficacyClaimed"])
        self.assertFalse(truth["externalAdoptionInferred"])
        self.assertFalse(truth["commercialContractClaimed"])
        self.assertEqual(truth["externalParticipationAcceptance"],"GATED")

    def test_success_criteria_do_not_invent_targets(self):
        room=institutional_onboarding.snapshot(self.c,"INST-ONBOARD-DEMO-001")
        criteria=room["successCriteria"]
        self.assertGreaterEqual(len(criteria),5)
        for item in criteria:
            self.assertIn(item["target"],("to_agree","to_agree_if_in_scope"))
        self.assertFalse(room["truthBoundary"]["successTargetsAreAgreed"])

    def test_commercial_handoff_remains_pre_contract(self):
        room=institutional_onboarding.snapshot(self.c,"INST-ONBOARD-DEMO-001")
        handoff=room["commercialHandoff"]
        self.assertEqual(handoff["state"],"pre_contract")
        self.assertIn("signed pilot",handoff["notClaimed"])
        self.assertIn("revenue",handoff["notClaimed"])
        self.assertIn("external participation acceptance",handoff["requiredBeforeSignature"])


if __name__=="__main__":
    unittest.main()
