import sqlite3
import unittest

from app.evidence_graph import seed_demo
from app.evidence_seal import build, portable_bundle


def _db():
    c=sqlite3.connect(":memory:")
    c.row_factory=sqlite3.Row
    c.executescript("""
    CREATE TABLE evidence_sources(id TEXT PRIMARY KEY,source_kind TEXT,title TEXT,publisher TEXT,source_ref TEXT,published_at TEXT,status TEXT,disclosure TEXT,demo_only INTEGER);
    CREATE TABLE evidence_claims(id TEXT PRIMARY KEY,artifact_kind TEXT,artifact_ref TEXT,claim_text TEXT,topic TEXT,status TEXT,version INTEGER,reviewer TEXT,reviewed_at INTEGER,supersedes_claim_id TEXT,correction_note TEXT,demo_only INTEGER);
    CREATE TABLE evidence_citations(id TEXT PRIMARY KEY,claim_id TEXT,source_id TEXT,locator TEXT,quote_excerpt TEXT,support_type TEXT,status TEXT,demo_only INTEGER);
    CREATE TABLE evidence_links(id TEXT PRIMARY KEY,claim_id TEXT,target_kind TEXT,target_ref TEXT,relation TEXT,start_sec INTEGER,end_sec INTEGER,demo_only INTEGER);
    """)
    seed_demo(c)
    return c


class EvidenceSealTests(unittest.TestCase):
    def setUp(self):
        self.c=_db()

    def tearDown(self):
        self.c.close()

    def test_demo_seal_is_deterministic_and_truth_bounded(self):
        one=build(self.c,artifact_kind="content",artifact_ref="CT01")
        two=build(self.c,artifact_kind="content",artifact_ref="CT01")
        self.assertEqual(one["state"],"VERIFIED_DEMO_PROCESS")
        self.assertTrue(one["validForProcess"])
        self.assertFalse(one["medicalEfficacyCertified"])
        self.assertEqual(one["counts"]["currentClaims"],2)
        self.assertEqual(one["counts"]["trustedCurrentClaims"],2)
        self.assertEqual(len(one["evidencePackageSha256"]),64)
        self.assertEqual(one["evidencePackageSha256"],two["evidencePackageSha256"])

    def test_missing_locator_fails_closed(self):
        self.c.execute("UPDATE evidence_citations SET locator='' WHERE claim_id='CL01'")
        seal=build(self.c,artifact_kind="content",artifact_ref="CT01")
        self.assertEqual(seal["state"],"INCOMPLETE")
        self.assertFalse(seal["validForProcess"])

    def test_no_claims_never_gets_seal(self):
        seal=build(self.c,artifact_kind="content",artifact_ref="CT99")
        self.assertEqual(seal["state"],"NO_CURRENT_CLAIMS")
        self.assertFalse(seal["validForProcess"])

    def test_portable_bundle_is_redacted_and_hash_stable(self):
        one=portable_bundle(self.c,artifact_kind="content",artifact_ref="CT01")
        two=portable_bundle(self.c,artifact_kind="content",artifact_ref="CT01")
        self.assertEqual(one["schemaVersion"],"promomed-content-evidence-bundle-v1")
        self.assertFalse(one["disclosureBoundary"]["reviewerIdentityIncluded"])
        self.assertFalse(one["disclosureBoundary"]["medicalEfficacyCertified"])
        self.assertEqual(one["signature"]["status"],"unsigned")
        self.assertEqual(len(one["bundleSha256"]),64)
        self.assertEqual(one["bundleSha256"],two["bundleSha256"])
        self.assertNotIn("reviewer",one["claims"][0])


if __name__=="__main__":
    unittest.main()
