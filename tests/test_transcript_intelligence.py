import os
import tempfile
import unittest
from pathlib import Path


class TranscriptIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"]=str(Path(self.tmp.name)/"transcript.db")
        os.environ["PROMOMED_SEED_DEMO"]="true"
        os.environ.pop("DATABASE_URL",None);os.environ.pop("PROMOMED_REQUIRE_POSTGRES",None)
        import importlib
        import app.db as db
        import app.transcript_intelligence as ti
        import app.discovery as discovery
        import app.editorial_commands as editorial_commands
        import server
        importlib.reload(db);importlib.reload(ti);importlib.reload(discovery);importlib.reload(editorial_commands);importlib.reload(server)
        self.ti=ti;self.discovery=discovery;self.commands=editorial_commands;self.server=server
        self.server.init();self.c=self.server.conn()

    def tearDown(self):
        self.c.close();self.tmp.cleanup()

    def test_participant_sees_only_reviewed_takeaways(self):
        d=self.ti.snapshot(self.c,item_id="P39",editor=False)
        ids={x["id"] for x in d["takeaways"]}
        self.assertIn("GT-P39-01",ids)
        self.assertNotIn("GT-P39-02",ids)
        self.assertTrue(d["truth_boundary"]["human_review_required"])
        self.assertFalse(d["truth_boundary"]["automatic_medical_publication"])

    def test_editor_sees_pending_takeaway(self):
        d=self.ti.snapshot(self.c,item_id="P39",editor=True)
        ids={x["id"] for x in d["takeaways"]}
        self.assertIn("GT-P39-02",ids)
        self.assertEqual(d["counts"]["pending_takeaways"],1)

    def test_editor_approval_makes_takeaway_public(self):
        out=self.commands.handle_command(self.c,"/api/transcript-takeaway-review","editor","editor@demo.ru",{"takeaway_id":"GT-P39-02","action":"approve_demo"})
        self.assertTrue(out.use_state)
        self.c.commit()
        d=self.ti.snapshot(self.c,item_id="P39",editor=False)
        row=next(x for x in d["takeaways"] if x["id"]=="GT-P39-02")
        self.assertEqual(row["status"],"approved_demo")
        self.assertEqual(row["reviewer"],"editor@demo.ru")

    def test_participant_cannot_approve_takeaway(self):
        out=self.commands.handle_command(self.c,"/api/transcript-takeaway-review","participant","participant@demo.ru",{"takeaway_id":"GT-P39-02","action":"approve_demo"})
        self.assertEqual(out.status,403)

    def test_discovery_indexes_reviewed_segments_and_only_approved_takeaways(self):
        d=self.discovery.search(self.c,query="wearable",limit=100)
        kinds={x["kind"] for x in d["results"]}
        self.assertIn("transcript",kinds)
        self.assertTrue(any(x["kind"]=="takeaway" and x["ref"]=="GT-P39-01" for x in d["results"]))
        self.assertFalse(any(x["ref"]=="GT-P39-02" for x in d["results"]))


if __name__=="__main__":unittest.main()
