import os
import tempfile
import unittest
from pathlib import Path


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"]=str(Path(self.tmp.name)/"discovery.db")
        os.environ["PROMOMED_SEED_DEMO"]="true"
        os.environ.pop("DATABASE_URL",None);os.environ.pop("PROMOMED_REQUIRE_POSTGRES",None)
        import importlib
        import app.db as db
        import app.discovery as discovery
        import app.participant_commands as participant_commands
        import app.personalization as personalization
        import server
        importlib.reload(db);importlib.reload(discovery);importlib.reload(participant_commands);importlib.reload(personalization);importlib.reload(server)
        self.discovery=discovery;self.commands=participant_commands;self.personalization=personalization;self.server=server
        self.server.init();self.c=self.server.conn();self.email="participant@demo.ru"

    def tearDown(self):
        self.c.close();self.tmp.cleanup()

    def test_search_spans_multiple_canonical_kinds(self):
        d=self.discovery.search(self.c,query="сон",email=self.email,limit=100)
        kinds={x["kind"] for x in d["results"]}
        self.assertIn("content",kinds)
        self.assertTrue("event" in kinds or "studio" in kinds or "topic" in kinds)
        self.assertFalse(d["medical_inference"])
        self.assertEqual(d["authority"],"Promomed canonical tables; search projection is rebuildable")

    def test_facets_include_required_dimensions(self):
        d=self.discovery.search(self.c,limit=5)
        for key in ("kind","topic","content_type","expert","event","review_status","replay"):
            self.assertIn(key,d["facets"])

    def test_kind_and_replay_filters_work(self):
        d=self.discovery.search(self.c,kind="replay",replay=True,limit=100)
        self.assertGreater(len(d["results"]),0)
        self.assertTrue(all(x["kind"]=="replay" and x["replay"] for x in d["results"]))

    def test_save_is_validated_and_feeds_personalization(self):
        out=self.commands.handle_command(self.c,"/api/discovery/save","participant",self.email,{"target_kind":"content","target_ref":"CT02"})
        self.assertTrue(out.use_state)
        self.c.commit()
        saved=self.discovery.saved_items(self.c,self.email)
        self.assertTrue(any(x["target_kind"]=="content" and x["target_ref"]=="CT02" for x in saved))
        p=self.personalization.snapshot(self.c,self.email)
        rows=[x for x in p["personalized_items"] if x["target_ref"]=="CT02"]
        self.assertEqual(rows[0]["reason"]["code"],"saved_for_later")

    def test_unknown_target_cannot_be_saved(self):
        out=self.commands.handle_command(self.c,"/api/discovery/save","participant",self.email,{"target_kind":"content","target_ref":"NOPE"})
        self.assertEqual(out.status,404)
        self.assertEqual(out.payload["error"],"discovery_target_not_found")

    def test_unsave_removes_feedback_signal(self):
        self.commands.handle_command(self.c,"/api/discovery/save","participant",self.email,{"target_kind":"content","target_ref":"CT02"})
        self.c.commit()
        self.commands.handle_command(self.c,"/api/discovery/unsave","participant",self.email,{"target_kind":"content","target_ref":"CT02"})
        self.c.commit()
        self.assertFalse(self.discovery.saved_items(self.c,self.email))


if __name__=="__main__":unittest.main()
