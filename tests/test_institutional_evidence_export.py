import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import institutional_evidence_export, strategic_reads
from app.auth import seed_demo_accounts


class InstitutionalEvidenceExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "SQLITE_PATH":str(Path(self.tmp.name)/"evidence-export.db"),
            "PROMOMED_SEED_DEMO":"true",
        },clear=False)
        self.env.start()
        import app.db as db
        importlib.reload(db)
        self.c=db.connect()
        db.migrate(self.c)
        seed_demo_accounts(self.c)
        self.c.commit()

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.tmp.cleanup()

    def test_pack_binds_three_source_exports(self):
        result=institutional_evidence_export.snapshot(self.c,"pharma",now=1234567890)
        self.assertEqual(set(result["generatedFrom"]),{
            "buyerFitExportSha256","proposalExportSha256","outreachExportSha256"
        })
        for value in result["generatedFrom"].values():
            self.assertEqual(len(value),64)

    def test_command_center_is_not_faked_for_archetype_only_pack(self):
        result=institutional_evidence_export.snapshot(self.c,"clinic")
        command=next(x for x in result["artifactCatalog"] if x["id"]=="command_center")
        self.assertEqual(command["authority"],"requires_real_organization_context")
        self.assertIsNone(command["sourceSha256"])
        self.assertFalse(result["diligenceBoundary"]["organizationSpecificCommandCenterIncluded"])

    def test_truth_boundary_denies_customer_pipeline_and_revenue_claims(self):
        result=institutional_evidence_export.snapshot(self.c,"strategic_partner")
        truth=result["truthBoundary"]
        self.assertTrue(truth["planningPackageOnly"])
        for key in (
            "namedCustomerClaimed","meetingOccurredClaimed","buyerInterestClaimed",
            "pipelineClaimed","pilotClaimed","pricingAgreed","targetsAgreed",
            "contractClaimed","purchaseOrderClaimed","revenueClaimed",
        ):
            self.assertFalse(truth[key])
        self.assertEqual(truth["externalParticipationAcceptance"],"GATED")

    def test_export_is_deterministic(self):
        first=institutional_evidence_export.snapshot(self.c,"medical_society",now=1234567890)
        second=institutional_evidence_export.snapshot(self.c,"medical_society",now=1234567890)
        self.assertEqual(first["export"]["sha256"],second["export"]["sha256"])
        self.assertEqual(first["export"]["document"],second["export"]["document"])
        self.assertEqual(first["export"]["contentType"],"application/json")
        self.assertTrue(first["export"]["suggestedFilename"].endswith(".json"))

    def test_all_archetypes_generate_pack(self):
        for archetype in ("clinic","university","medical_society","pharma","knowledge_provider","strategic_partner"):
            result=institutional_evidence_export.snapshot(self.c,archetype)
            self.assertEqual(result["archetype"],archetype)
            self.assertGreaterEqual(len(result["artifactCatalog"]),5)

    def test_guarded_route(self):
        payload,status=strategic_reads.read(self.c,"/api/institutional-evidence-export/pharma","sales")
        self.assertEqual(status,200)
        self.assertEqual(payload["archetype"],"pharma")
        forbidden,status=strategic_reads.read(self.c,"/api/institutional-evidence-export/pharma","participant")
        self.assertEqual(status,403)
        self.assertEqual(forbidden["error"],"forbidden")


if __name__=="__main__":
    unittest.main()
