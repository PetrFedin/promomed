import base64
import sqlite3

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    CRYPTO_AVAILABLE=True
except ModuleNotFoundError:
    serialization=None
    Ed25519PrivateKey=None
    CRYPTO_AVAILABLE=False

from app import evidence_checkpoint
from app.evidence_graph import seed_demo


def _key_b64():
    private=Ed25519PrivateKey.generate()
    raw=private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _db():
    c=sqlite3.connect(":memory:")
    c.row_factory=sqlite3.Row
    c.executescript("""
    CREATE TABLE evidence_sources(
      id TEXT PRIMARY KEY,source_kind TEXT,title TEXT,publisher TEXT,source_ref TEXT,
      published_at TEXT,status TEXT,disclosure TEXT,demo_only INTEGER
    );
    CREATE TABLE evidence_claims(
      id TEXT PRIMARY KEY,artifact_kind TEXT,artifact_ref TEXT,claim_text TEXT,topic TEXT,
      status TEXT,version INTEGER,reviewer TEXT,reviewed_at INTEGER,supersedes_claim_id TEXT,
      correction_note TEXT,demo_only INTEGER
    );
    CREATE TABLE evidence_citations(
      id TEXT PRIMARY KEY,claim_id TEXT,source_id TEXT,locator TEXT,quote_excerpt TEXT,
      support_type TEXT,status TEXT,demo_only INTEGER
    );
    CREATE TABLE evidence_links(
      id TEXT PRIMARY KEY,claim_id TEXT,target_kind TEXT,target_ref TEXT,relation TEXT,
      start_sec INTEGER,end_sec INTEGER,demo_only INTEGER
    );
    CREATE TABLE publication_holds(
      id TEXT PRIMARY KEY,event_id TEXT,artifact_kind TEXT,artifact_ref TEXT,reason TEXT,
      status TEXT,placed_at INTEGER,placed_by TEXT,released_at INTEGER,released_by TEXT,demo_only INTEGER
    );
    CREATE TABLE evidence_checkpoint_revocations(
      checkpoint_sha256 TEXT PRIMARY KEY,artifact_kind TEXT,artifact_ref TEXT,reason TEXT,
      revoked_by TEXT,revoked_at INTEGER
    );
    """)
    seed_demo(c)
    return c


def test_checkpoint_tracks_current_seal_hold_and_revocation(monkeypatch):
    if not CRYPTO_AVAILABLE:
        return
    monkeypatch.setenv("PROMOMED_EVIDENCE_SIGNING_PRIVATE_KEY_B64",_key_b64())
    c=_db()

    envelope=evidence_checkpoint.issue(c,"content","CT01")
    valid=evidence_checkpoint.verify(c,envelope)
    assert valid["status"]=="VALID"
    assert valid["current"] is True
    assert valid["medicalEfficacyCertified"] is False

    tampered={
        **envelope,
        "payload":{**envelope["payload"],"sealSha256":"f"*64},
    }
    invalid=evidence_checkpoint.verify(c,tampered)
    assert invalid["status"]=="INVALID_SIGNATURE"

    c.execute(
        "INSERT INTO publication_holds(id,event_id,artifact_kind,artifact_ref,reason,status,placed_at,placed_by,demo_only) VALUES(?,?,?,?,?,'active',?,?,1)",
        ("hold-1","event-1","content","CT01","Source retracted",1,"governance"),
    )
    held=evidence_checkpoint.verify(c,envelope)
    assert held["status"]=="STALE_OR_HELD"
    assert held["publication_hold"] is True

    c.execute("DELETE FROM publication_holds")
    evidence_checkpoint.revoke(c,envelope["checkpointSha256"],"content","CT01","Governance withdrawal","editor@test")
    revoked=evidence_checkpoint.verify(c,envelope)
    assert revoked["status"]=="REVOKED"
    assert revoked["revoked"] is True


def test_checkpoint_issuer_fails_closed_without_key(monkeypatch):
    if not CRYPTO_AVAILABLE:
        return
    monkeypatch.delenv("PROMOMED_EVIDENCE_SIGNING_PRIVATE_KEY_B64",raising=False)
    c=_db()
    try:
        evidence_checkpoint.issue(c,"content","CT01")
        assert False,"issuance must fail without issuer key"
    except ValueError as exc:
        assert str(exc)=="evidence_checkpoint_issuer_not_configured"
