import os
import tempfile
import unittest
from pathlib import Path


class ClaimEvidenceGraphTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"]=str(Path(self.tmp.name)/"evidence.db")
        os.environ["PROMOMED_SEED_DEMO"]="true"
        os.environ.pop("DATABASE_URL",None);os.environ.pop("PROMOMED_REQUIRE_POSTGRES",None)
        import importlib
        import app.db as db
        import app.evidence_graph as evidence_graph
        import app.editorial_commands as editorial_commands
        import server
        importlib.reload(db);importlib.reload(evidence_graph);importlib.reload(editorial_commands);importlib.reload(server)
        self.graph=evidence_graph;self.commands=editorial_commands;self.server=server
        self.server.init();self.c=self.server.conn()

    def tearDown(self):
        self.c.close();self.tmp.cleanup()

    def test_reviewed_claim_requires_complete_evidence_chain(self):
        d=self.graph.snapshot(self.c,"content","CT01")
        self.assertGreaterEqual(d["summary"]["trusted"],2)
        for claim in d["claims"]:
            self.assertTrue(claim["trust"]["has_reviewer"])
            self.assertTrue(claim["trust"]["has_active_source"])
            self.assertTrue(claim["trust"]["has_exact_locator"])
            self.assertTrue(claim["trust"]["has_graph_trace"])
        self.assertTrue(d["truth_boundary"]["demo_sources"])
        self.assertFalse(d["truth_boundary"]["external_publication_verified"])

    def test_superseded_version_remains_visible(self):
        d=self.graph.snapshot(self.c,"content","CT02")
        statuses={x["id"]:x["trust"]["status"] for x in d["claims"]}
        self.assertEqual(statuses["CL03"],"SUPERSEDED")
        self.assertEqual(statuses["CL04"],"VERIFIED_DEMO")
        self.assertEqual(d["summary"]["superseded"],1)

    def test_missing_locator_blocks_trust(self):
        self.c.execute("UPDATE evidence_citations SET locator='' WHERE claim_id='CL01'")
        self.c.commit()
        d=self.graph.snapshot(self.c,"content","CT01")
        cl=next(x for x in d["claims"] if x["id"]=="CL01")
        self.assertFalse(cl["trust"]["trusted"])
        self.assertEqual(cl["trust"]["status"],"INCOMPLETE_EVIDENCE")

    def test_editor_correction_creates_new_version_without_erasing_old(self):
        out=self.commands.handle_command(self.c,"/api/evidence-claim-correct","editor","editor@demo.ru",{"claim_id":"CL01","claim_text":"Уточнённая демонстрационная формулировка."})
        self.assertTrue(out.use_state)
        self.c.commit()
        d=self.graph.snapshot(self.c,"content","CT01")
        ids={x["id"] for x in d["claims"]}
        self.assertIn("CL01",ids)
        self.assertIn("CL01-V2",ids)
        old=next(x for x in d["claims"] if x["id"]=="CL01")
        new=next(x for x in d["claims"] if x["id"]=="CL01-V2")
        self.assertEqual(old["trust"]["status"],"SUPERSEDED")
        self.assertEqual(new["trust"]["status"],"VERIFIED_DEMO")
        self.assertEqual(new["supersedes_claim_id"],"CL01")

    def test_editor_can_retract_but_participant_cannot(self):
        denied=self.commands.handle_command(self.c,"/api/evidence-claim-retract","participant","participant@demo.ru",{"claim_id":"CL02","note":"x"})
        self.assertEqual(denied.status,403)
        ok=self.commands.handle_command(self.c,"/api/evidence-claim-retract","editor","editor@demo.ru",{"claim_id":"CL02","note":"Demo retraction"})
        self.assertTrue(ok.use_state)
        self.c.commit()
        d=self.graph.snapshot(self.c,"content","CT01")
        row=next(x for x in d["claims"] if x["id"]=="CL02")
        self.assertEqual(row["trust"]["status"],"RETRACTED")
        self.assertFalse(row["trust"]["trusted"])

    def test_graph_contains_transcript_expert_event_and_replay_links(self):
        d=self.graph.snapshot(self.c,"content","CT01")
        cl=next(x for x in d["claims"] if x["id"]=="CL01")
        kinds={x["target_kind"] for x in cl["links"]}
        self.assertTrue({"transcript","expert","event","replay"}.issubset(kinds))


if __name__=="__main__":unittest.main()
