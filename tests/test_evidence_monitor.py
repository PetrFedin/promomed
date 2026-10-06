import os
import tempfile
import unittest
from pathlib import Path


class ExternalEvidenceAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"]=str(Path(self.tmp.name)/"monitor.db")
        os.environ["PROMOMED_SEED_DEMO"]="true"
        os.environ.pop("DATABASE_URL",None);os.environ.pop("PROMOMED_REQUIRE_POSTGRES",None)
        import importlib
        import app.db as db
        import app.evidence_monitor as monitor
        import app.evidence_graph as graph
        import app.change_impact as impact
        import server
        importlib.reload(db);importlib.reload(graph);importlib.reload(impact);importlib.reload(monitor);importlib.reload(server)
        self.monitor=monitor;self.graph=graph;self.impact=impact;self.server=server
        self.server.init();self.c=self.server.conn()

    def tearDown(self):
        self.c.close();self.tmp.cleanup()

    def test_doi_and_pmid_identity_normalization(self):
        self.assertEqual(self.monitor.canonical_external_id("crossref","https://doi.org/10.1000/ABC.Def"),"10.1000/abc.def")
        self.assertEqual(self.monitor.canonical_external_id("crossref","DOI:10.1000/Test"),"10.1000/test")
        self.assertEqual(self.monitor.canonical_external_id("pubmed","PMID: 12345678"),"12345678")

    def test_pubmed_normalization_detects_retracted_publication_type(self):
        payload={"result":{"123":{"uid":"123","title":"Example","source":"Journal","pubdate":"2025","pubtype":["Journal Article","Retracted Publication"]}}}
        d=self.monitor.normalize_pubmed(payload,"123")
        self.assertEqual(d["provider_status"],"retracted")
        self.assertEqual(d["canonical_key"],"pmid:123")

    def test_demo_seed_has_admitted_baseline_and_claim_link(self):
        d=self.monitor.snapshot(self.c)
        self.assertEqual(d["summary"]["watch_targets"],1)
        target=d["targets"][0]
        self.assertTrue(target["source_id"])
        citation=self.c.execute("SELECT source_id,status FROM evidence_citations WHERE id='EC-EXT-CL01'").fetchone()
        self.assertEqual(citation["source_id"],target["source_id"])
        self.assertEqual(citation["status"],"active")

    def test_duplicate_snapshot_is_idempotent(self):
        r=self.monitor.ingest_payload(self.c,"crossref","10.5555/promomed.demo.metabolic",self.monitor.DEMO_CROSSREF_BASE,"editor@demo.ru",1)
        self.assertTrue(r["duplicate"])
        self.assertIsNone(r["candidate_id"])

    def test_retraction_requires_two_reviews_before_admission(self):
        r=self.monitor.ingest_payload(self.c,"crossref","10.5555/promomed.demo.metabolic",self.monitor.DEMO_CROSSREF_RETRACTED,"editor@demo.ru",1)
        cid=r["candidate_id"]
        self.assertEqual(r["change_type"],"source_retracted")
        with self.assertRaisesRegex(ValueError,"candidate_reviews_required"):
            self.monitor.admit_candidate(self.c,cid,"editor@demo.ru")
        self.monitor.review_candidate(self.c,cid,"editorial","editor@demo.ru")
        with self.assertRaisesRegex(ValueError,"candidate_reviews_required"):
            self.monitor.admit_candidate(self.c,cid,"editor@demo.ru")
        self.monitor.review_candidate(self.c,cid,"scientific","editor@demo.ru")
        admitted=self.monitor.admit_candidate(self.c,cid,"editor@demo.ru")
        self.c.commit()
        self.assertTrue(admitted["change_event_id"])
        row=self.c.execute("SELECT status,change_event_id FROM evidence_admission_candidates WHERE id=?",(cid,)).fetchone()
        self.assertEqual(row["status"],"admitted_demo")
        self.assertEqual(row["change_event_id"],admitted["change_event_id"])

    def test_admitted_retraction_propagates_to_claim_and_hold(self):
        r=self.monitor.ingest_payload(self.c,"crossref","10.5555/promomed.demo.metabolic",self.monitor.DEMO_CROSSREF_RETRACTED,"editor@demo.ru",1)
        cid=r["candidate_id"]
        for role in self.monitor.REVIEW_ROLES:
            self.monitor.review_candidate(self.c,cid,role,"editor@demo.ru")
        admitted=self.monitor.admit_candidate(self.c,cid,"editor@demo.ru")
        self.c.commit()
        claim=self.graph.snapshot(self.c,claim_id="CL01")["claims"][0]
        self.assertEqual(claim["trust"]["status"],"DRAFT")
        self.assertTrue(self.impact.is_held(self.c,"content","CT01"))
        impact=self.impact.snapshot(self.c,admitted["change_event_id"])
        self.assertGreater(impact["summary"]["open_impacts"],0)
        self.assertGreater(impact["summary"]["active_holds"],0)

    def test_provider_failure_is_recorded_not_silent(self):
        original=self.monitor.fetch_live
        try:
            def fail(*args,**kwargs):
                raise TimeoutError("provider timeout")
            self.monitor.fetch_live=fail
            with self.assertRaisesRegex(ValueError,"provider_fetch_failed"):
                self.monitor.fetch_and_ingest(self.c,"pubmed","123456","editor@demo.ru",email="editor@example.com")
            self.c.commit()
        finally:
            self.monitor.fetch_live=original
        d=self.monitor.snapshot(self.c)
        self.assertEqual(d["summary"]["provider_errors"],1)
        self.assertEqual(d["provider_errors"][0]["error_type"],"TimeoutError")

    def test_demo_boundary_does_not_claim_independent_scientific_review(self):
        d=self.monitor.snapshot(self.c)
        self.assertTrue(d["truth_boundary"]["live_provider_adapter_present"])
        self.assertFalse(d["truth_boundary"]["continuous_monitoring"])
        self.assertFalse(d["truth_boundary"]["independent_scientific_reviewer"])
        self.assertFalse(d["truth_boundary"]["automatic_medical_truth"])


if __name__=="__main__":unittest.main()
