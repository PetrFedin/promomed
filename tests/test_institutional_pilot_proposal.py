import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import institutional_pilot_proposal, strategic_reads
from app.auth import seed_demo_accounts


class InstitutionalPilotProposalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "SQLITE_PATH":str(Path(self.tmp.name)/"proposal.db"),
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

    def test_supported_archetypes_are_explicit(self):
        ids={x["id"] for x in institutional_pilot_proposal.archetypes()}
        self.assertEqual(ids,{"clinic","university","medical_society","pharma","knowledge_provider","strategic_partner"})

    def test_proposal_never_claims_real_customer_or_commitment(self):
        result=institutional_pilot_proposal.snapshot(self.c,"pharma")
        truth=result["truthBoundary"]
        self.assertTrue(truth["proposalOnly"])
        self.assertFalse(truth["realCustomerClaimed"])
        self.assertFalse(truth["realPilotClaimed"])
        self.assertFalse(truth["commercialCommitmentClaimed"])
        self.assertFalse(truth["targetsAgreed"])
        self.assertFalse(truth["timelineAgreed"])
        self.assertFalse(truth["pricingAgreed"])
        self.assertEqual(truth["externalParticipationAcceptance"],"GATED")

    def test_commercial_terms_are_not_invented(self):
        result=institutional_pilot_proposal.snapshot(self.c,"clinic")
        commercial=result["commercial"]
        self.assertEqual(commercial["pricing"],"TO_PRICE")
        self.assertEqual(commercial["pilotDuration"],"TO_AGREE")
        self.assertEqual(commercial["supportModel"],"TO_AGREE")
        self.assertEqual(commercial["purchaseOrder"],"NOT_CLAIMED")
        self.assertEqual(commercial["revenue"],"NOT_CLAIMED")
        for metric in result["successCriteria"]:
            self.assertIn(metric["target"],("to_agree","to_agree_if_in_scope"))

    def test_participation_acceptance_stays_gated(self):
        result=institutional_pilot_proposal.snapshot(self.c,"university")
        participation=next(x for x in result["prerequisites"] if x["id"]=="participation")
        self.assertEqual(participation["state"],"GATED")
        self.assertIn("real non-demo institution",participation["evidenceRequired"])

    def test_all_archetypes_generate_distinct_positioning(self):
        outputs={k:institutional_pilot_proposal.snapshot(self.c,k,now=1234567890) for k in (
            "clinic","university","medical_society","pharma","knowledge_provider","strategic_partner"
        )}
        labels={x["archetypeLabel"] for x in outputs.values()}
        self.assertEqual(len(labels),6)
        self.assertTrue(all(x["positioning"]["businessObjectives"] for x in outputs.values()))
        self.assertTrue(all(x["positioning"]["useCases"] for x in outputs.values()))

    def test_export_is_deterministic(self):
        first=institutional_pilot_proposal.snapshot(self.c,"strategic_partner",now=1234567890)
        second=institutional_pilot_proposal.snapshot(self.c,"strategic_partner",now=1234567890)
        self.assertEqual(first["export"]["sha256"],second["export"]["sha256"])
        self.assertEqual(len(first["export"]["sha256"]),64)

    def test_unsupported_archetype_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"unsupported_archetype"):
            institutional_pilot_proposal.snapshot(self.c,"invented_customer")

    def test_guarded_strategic_route(self):
        path="/api/institutional-pilot-proposal/pharma"
        payload,status=strategic_reads.read(self.c,path,"sales")
        self.assertEqual(status,200)
        self.assertEqual(payload["archetype"],"pharma")
        forbidden,status=strategic_reads.read(self.c,path,"participant")
        self.assertEqual(status,403)
        self.assertEqual(forbidden["error"],"forbidden")


if __name__=="__main__":
    unittest.main()
