import sqlite3
import time
from app.evidence_governance import build_manifest, record_review, verification_projection

def db():
    c=sqlite3.connect(":memory:"); c.row_factory=sqlite3.Row
    c.executescript("""
    CREATE TABLE content_catalog(id TEXT PRIMARY KEY,kind TEXT,theme TEXT,title TEXT,dek TEXT,duration TEXT,author TEXT,reviewer TEXT,partner TEXT,status TEXT,version INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE evidence_sources(id TEXT PRIMARY KEY,content_id TEXT,content_version INTEGER,source_type TEXT,source_ref TEXT,source_date TEXT,metadata_json TEXT,created_at INTEGER);
    CREATE TABLE evidence_reviews(id TEXT PRIMARY KEY,content_id TEXT,content_version INTEGER,source_id TEXT,reviewer_email TEXT,reviewer_role TEXT,disclosure TEXT,decision TEXT,reviewed_at INTEGER,valid_until INTEGER,superseded_at INTEGER);
    """)
    c.execute("INSERT INTO content_catalog(id,kind,theme,title,author,reviewer,partner,status,version) VALUES(?,?,?,?,?,?,?,?,?)",("CT01","article","science","Evidence-aware article","Editorial","Medical review","Partner","review",3))
    return c

def test_manifest_is_fail_closed_until_approved_review():
    c=db()
    assert build_manifest(c,content_id="CT01",now=1000)["seal"]["status"]=="missing_review"
    m=record_review(c,content_id="CT01",source_type="study",source_ref="doi:10.0000/example",reviewer_email="editor@example.test",reviewer_role="medical_editor",disclosure="No conflict declared.",decision="approved",valid_until=int(time.time())+86400)
    assert m["seal"]["valid"] is True
    assert len(m["evidencePackageSha256"])==64
    assert verification_projection(m)["disclosurePresent"] is True

def test_needs_changes_never_gets_valid_seal():
    c=db()
    m=record_review(c,content_id="CT01",source_type="guideline",source_ref="guideline:demo",reviewer_email="editor@example.test",reviewer_role="medical_editor",disclosure="Partner relationship disclosed.",decision="needs_changes",valid_until=int(time.time())+86400)
    assert m["seal"]["status"]=="not_approved"
