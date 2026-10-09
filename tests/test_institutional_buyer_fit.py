import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import institutional_buyer_fit, strategic_reads
from app.auth import seed_demo_accounts


class InstitutionalBuyerFitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "SQLITE_PATH":str(Path(self.tmp.name)/"buyer-fit.db"),
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

    def test_all_six_archetypes_are_compared(self):
        result=institutional_buyer_fit.snapshot(self.c)
        ids={x["archetype"] for x in result["rows"]}
        self.assertEqual(ids,{"clinic","university","medical_society","pharma","knowledge_provider","strategic_partner"})

    def test_no_synthetic_commercial_scoring(self):
        result=institutional_buyer_fit.snapshot(self.c)
        boundary=result["usageBoundary"]
        self.assertTrue(boundary["noMarketDemandClaim"])
        self.assertTrue(boundary["noWinProbabilityClaim"])
        self.assertTrue(boundary["noRevenuePotentialClaim"])
        self.assertTrue(boundary["noCustomerPriorityClaim"])
        self.assertTrue(boundary["noSyntheticScore"])
        self.assertTrue(boundary["fitIsCapabilityMatchOnly"])

    def test_fit_values_are_only_strong_or_conditional(self):
        result=institutional_buyer_fit.snapshot(self.c)
        for row in result["rows"]:
            self.assertEqual(set(row["fit"]),{x["id"] for x in result["dimensions"]})
            for value in row["fit"].values():
                self.assertIn(value,("strong","conditional"))

    def test_each_archetype_requires_real_validation_questions(self):
        result=institutional_buyer_fit.snapshot(self.c)
        for row in result["rows"]:
            self.assertGreaterEqual(len(row["validationQuestions"]),3)
            self.assertEqual(row["participationAcceptance"],"GATED")

    def test_truth_boundary_remains_planning_only(self):
        result=institutional_buyer_fit.snapshot(self.c)
        truth=result["truthBoundary"]
        self.assertTrue(truth["planningOnly"])
        self.assertFalse(truth["realCustomerClaimed"])
        self.assertFalse(truth["realPipelineClaimed"])
        self.assertFalse(truth["realPilotClaimed"])
        self.assertEqual(truth["externalParticipationAcceptance"],"GATED")

    def test_export_is_deterministic(self):
        first=institutional_buyer_fit.snapshot(self.c,now=1234567890)
        second=institutional_buyer_fit.snapshot(self.c,now=1234567890)
        self.assertEqual(first["export"]["sha256"],second["export"]["sha256"])
        self.assertEqual(len(first["export"]["sha256"]),64)

    def test_guarded_route(self):
        payload,status=strategic_reads.read(self.c,"/api/institutional-buyer-fit-matrix","sales")
        self.assertEqual(status,200)
        self.assertEqual(len(payload["rows"]),6)
        forbidden,status=strategic_reads.read(self.c,"/api/institutional-buyer-fit-matrix","participant")
        self.assertEqual(status,403)
        self.assertEqual(forbidden["error"],"forbidden")


if __name__=="__main__":
    unittest.main()
