import os
import tempfile
import unittest
from pathlib import Path


class KnowledgeChangeImpactTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"]=str(Path(self.tmp.name)/"impact.db")
        os.environ["PROMOMED_SEED_DEMO"]="true"
        os.environ.pop("DATABASE_URL",None);os.environ.pop("PROMOMED_REQUIRE_POSTGRES",None)
        import importlib
        import app.db as db
        import app.change_impact as change_impact
        import app.evidence_graph as evidence_graph
        import app.content as content
        import app.personalization as personalization
        import server
        importlib.reload(db);importlib.reload(evidence_graph);importlib.reload(change_impact);importlib.reload(content);importlib.reload(personalization);importlib.reload(server)
        self.impact=change_impact;self.graph=evidence_graph;self.content=content;self.personalization=personalization;self.server=server
        self.server.init();self.c=self.server.conn()
        self.email="participant@demo.ru"

    def tearDown(self):
        self.c.close();self.tmp.cleanup()

    def _create(self):
        event_id=self.impact.analyze_source_change(self.c,"ES01","source_retracted","DEMO source retracted","editor@demo.ru")
        self.c.commit()
        return event_id

    def test_retracted_source_invalidates_claim_and_traverses_downstream(self):
        event_id=self._create()
        d=self.impact.snapshot(self.c,event_id)
        kinds={x["target_kind"] for x in d["impacts"]}
        self.assertTrue({"content","transcript","expert","event","replay","studio","takeaway","recommendation"}.issubset(kinds))
        self.assertGreater(d["summary"]["active_holds"],0)
        claim=self.graph.snapshot(self.c,claim_id="CL01")["claims"][0]
        self.assertFalse(claim["trust"]["trusted"])
        self.assertEqual(claim["trust"]["status"],"INCOMPLETE_EVIDENCE")
        source=self.c.execute("SELECT status FROM evidence_sources WHERE id='ES01'").fetchone()
        self.assertEqual(source["status"],"source_retracted_demo")

    def test_content_projection_surfaces_active_hold(self):
        self._create()
        snap=self.content.snapshot(self.c)
        ct01=next(x for x in snap["content_catalog"] if x["id"]=="CT01")
        self.assertTrue(ct01["publication_hold"])
        self.assertIn("source_retracted",ct01["publication_hold_reason"])

    def test_held_topic_is_removed_from_personalized_ranking(self):
        self.c.execute("INSERT INTO topic_subscriptions(email,topic,status,ts) VALUES(?,?,'active',1)",(self.email,"Метаболическое здоровье"))
        self.c.commit()
        before=self.personalization.snapshot(self.c,self.email)
        self.assertTrue(any("метабол" in str(x.get("topic") or "").lower() for x in before["personalized_items"]))
        self._create()
        after=self.personalization.snapshot(self.c,self.email)
        self.assertGreaterEqual(after["personalization_signals"]["held_topic_count"],1)
        self.assertFalse(any("метабол" in str(x.get("topic") or "").lower() for x in after["personalized_items"]))

    def test_hold_cannot_release_before_evidence_remediation(self):
        event_id=self._create()
        with self.assertRaisesRegex(ValueError,"evidence_remediation_required"):
            self.impact.resolve_case(self.c,event_id,"Reviewed only","editor@demo.ru",release_holds=True)
        self.c.rollback()
        self.assertTrue(self.impact.is_held(self.c,"content","CT01"))

    def test_retract_impacted_claim_then_release_hold(self):
        event_id=self._create()
        self.graph.retract_demo_claim(self.c,"CL01","Source retracted; claim withdrawn.","editor@demo.ru")
        self.c.commit()
        self.impact.resolve_case(self.c,event_id,"Claim retracted; downstream reviewed.","editor@demo.ru",release_holds=True)
        self.c.commit()
        d=self.impact.snapshot(self.c,event_id)
        self.assertEqual(d["summary"]["active_holds"],0)
        self.assertFalse(self.impact.is_held(self.c,"content","CT01"))
        claim=self.graph.snapshot(self.c,claim_id="CL01")["claims"][0]
        self.assertEqual(claim["trust"]["status"],"RETRACTED")

    def test_critical_change_creates_short_sla(self):
        event_id=self._create()
        d=self.impact.snapshot(self.c,event_id)
        event=d["events"][0]
        case=d["review_cases"][0]
        self.assertEqual(case["severity"],"critical")
        self.assertLessEqual(int(case["deadline_at"])-int(event["detected_at"]),4*3600)


if __name__=="__main__":unittest.main()
