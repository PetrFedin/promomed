import sqlite3

from app.evidence_graph import seed_demo
from app.evidence_seal import build


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


def test_demo_seal_is_deterministic_and_truth_bounded():
    c=_db()
    one=build(c,artifact_kind="content",artifact_ref="CT01")
    two=build(c,artifact_kind="content",artifact_ref="CT01")
    assert one["state"]=="VERIFIED_DEMO_PROCESS"
    assert one["validForProcess"] is True
    assert one["medicalEfficacyCertified"] is False
    assert one["counts"]["currentClaims"]==2
    assert one["counts"]["trustedCurrentClaims"]==2
    assert len(one["evidencePackageSha256"])==64
    assert one["evidencePackageSha256"]==two["evidencePackageSha256"]


def test_missing_locator_fails_closed():
    c=_db()
    c.execute("UPDATE evidence_citations SET locator='' WHERE claim_id='CL01'")
    seal=build(c,artifact_kind="content",artifact_ref="CT01")
    assert seal["state"]=="INCOMPLETE"
    assert seal["validForProcess"] is False


def test_no_claims_never_gets_seal():
    c=_db()
    seal=build(c,artifact_kind="content",artifact_ref="CT99")
    assert seal["state"]=="NO_CURRENT_CLAIMS"
    assert seal["validForProcess"] is False
