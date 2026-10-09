import importlib, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from app import institutional_outreach_pack, strategic_reads
from app.auth import seed_demo_accounts

class InstitutionalOutreachPackTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "SQLITE_PATH":str(Path(self.tmp.name)/"outreach.db"),
            "PROMOMED_SEED_DEMO":"true",
        },clear=False)
        self.env.start()
        import app.db as db
        importlib.reload(db)
        self.c=db.connect(); db.migrate(self.c); seed_demo_accounts(self.c); self.c.commit()
    def tearDown(self):
        self.c.close(); self.env.stop(); self.tmp.cleanup()

    def test_truth_boundary_has_no_fake_meeting_or_pipeline(self):
        r=institutional_outreach_pack.snapshot(self.c,"pharma")
        t=r["truthBoundary"]
        self.assertTrue(t["planningOnly"])
        self.assertFalse(t["meetingOccurredClaimed"])
        self.assertFalse(t["buyerInterestClaimed"])
        self.assertFalse(t["pipelineStageClaimed"])
        self.assertFalse(t["nextMeetingClaimed"])
        self.assertFalse(t["pilotClaimed"])
        self.assertEqual(t["externalParticipationAcceptance"],"GATED")

    def test_agenda_and_discovery_are_practical(self):
        r=institutional_outreach_pack.snapshot(self.c,"clinic")
        self.assertGreaterEqual(len(r["agenda"]),7)
        self.assertGreaterEqual(len(r["discoveryQuestions"]),10)
        self.assertGreaterEqual(len(r["evidenceToShow"]),6)
        self.assertGreaterEqual(len(r["claimsNotToMake"]),6)

    def test_outputs_are_not_persisted_facts(self):
        r=institutional_outreach_pack.snapshot(self.c,"university")
        for item in r["meetingOutputsExpected"]:
            self.assertIn(item["state"],("to_capture_in_real_meeting","GATED"))

    def test_all_archetypes_work(self):
        for archetype in ("clinic","university","medical_society","pharma","knowledge_provider","strategic_partner"):
            r=institutional_outreach_pack.snapshot(self.c,archetype)
            self.assertEqual(r["archetype"],archetype)

    def test_export_is_deterministic(self):
        a=institutional_outreach_pack.snapshot(self.c,"strategic_partner",now=1234567890)
        b=institutional_outreach_pack.snapshot(self.c,"strategic_partner",now=1234567890)
        self.assertEqual(a["export"]["sha256"],b["export"]["sha256"])

    def test_guarded_route(self):
        p,s=strategic_reads.read(self.c,"/api/institutional-outreach-pack/pharma","sales")
        self.assertEqual(s,200); self.assertEqual(p["archetype"],"pharma")
        p,s=strategic_reads.read(self.c,"/api/institutional-outreach-pack/pharma","participant")
        self.assertEqual(s,403)

if __name__=="__main__": unittest.main()
