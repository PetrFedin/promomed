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
    CREATE TABLE evidence_issuer_keys(
      issuer_id TEXT NOT NULL,key_id TEXT NOT NULL,alg TEXT NOT NULL,public_key_b64 TEXT NOT NULL,
      status TEXT NOT NULL,valid_from INTEGER NOT NULL,valid_until INTEGER,rotated_from_key_id TEXT,
      created_at INTEGER NOT NULL,created_by TEXT NOT NULL,retired_at INTEGER,revoked_at INTEGER,
      revoked_reason TEXT,PRIMARY KEY(issuer_id,key_id)
    );
    CREATE TABLE evidence_checkpoint_issuance(
      checkpoint_sha256 TEXT PRIMARY KEY,issuer_id TEXT NOT NULL,key_id TEXT NOT NULL,
      artifact_kind TEXT NOT NULL,artifact_ref TEXT NOT NULL,issued_at INTEGER NOT NULL,
      seal_sha256 TEXT NOT NULL,payload_json TEXT NOT NULL,signature_b64 TEXT NOT NULL
    );
    """)
    seed_demo(c)
    return c


def _configure(monkeypatch,key_id="key-v1",key=None):
    monkeypatch.setenv("PROMOMED_EVIDENCE_ISSUER_ID","promomed-test-issuer")
    monkeypatch.setenv("PROMOMED_EVIDENCE_KEY_ID",key_id)
    monkeypatch.setenv("PROMOMED_EVIDENCE_SIGNING_PRIVATE_KEY_B64",key or _key_b64())


def test_checkpoint_tracks_current_seal_hold_and_revocation(monkeypatch):
    if not CRYPTO_AVAILABLE:
        return
    _configure(monkeypatch)
    c=_db()

    envelope=evidence_checkpoint.issue(c,"content","CT01")
    stored=evidence_checkpoint.checkpoint_document(c,envelope["checkpointSha256"])
    assert stored==envelope
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
    monkeypatch.setenv("PROMOMED_EVIDENCE_ISSUER_ID","promomed-test-issuer")
    monkeypatch.setenv("PROMOMED_EVIDENCE_KEY_ID","key-v1")
    monkeypatch.delenv("PROMOMED_EVIDENCE_SIGNING_PRIVATE_KEY_B64",raising=False)
    c=_db()
    try:
        evidence_checkpoint.issue(c,"content","CT01")
        assert False,"issuance must fail without issuer key"
    except ValueError as exc:
        assert str(exc)=="evidence_checkpoint_issuer_not_configured"


def test_portable_verifier_uses_public_key_not_private_key(monkeypatch):
    if not CRYPTO_AVAILABLE:
        return
    _configure(monkeypatch)
    c=_db()
    envelope=evidence_checkpoint.issue(c,"content","CT01")
    issuer_doc=evidence_checkpoint.issuer_document(c)
    status_doc=evidence_checkpoint.status_list(c)

    monkeypatch.delenv("PROMOMED_EVIDENCE_SIGNING_PRIVATE_KEY_B64",raising=False)
    result=evidence_checkpoint.verify_portable(envelope,issuer_doc,status_doc)

    assert result["status"]=="VALID_PORTABLE"
    assert result["signature_valid"] is True
    assert result["currentCanonicalStateVerified"] is False
    assert result["medicalEfficacyCertified"] is False


def test_key_rotation_preserves_old_signature_then_revocation_invalidates_trust(monkeypatch):
    if not CRYPTO_AVAILABLE:
        return
    _configure(monkeypatch,"key-v1")
    c=_db()
    old_envelope=evidence_checkpoint.issue(c,"content","CT01")

    _configure(monkeypatch,"key-v2")
    rotated=evidence_checkpoint.activate_current_key(c,"governance@test")
    assert rotated["keyId"]=="key-v2"
    assert rotated["rotatedFromKeyId"]=="key-v1"

    issuer_doc=evidence_checkpoint.issuer_document(c)
    old_key=next(k for k in issuer_doc["keys"] if k["keyId"]=="key-v1")
    assert old_key["status"]=="retired"
    assert evidence_checkpoint.verify_portable(old_envelope,issuer_doc,evidence_checkpoint.status_list(c))["status"]=="VALID_PORTABLE"

    evidence_checkpoint.revoke_key(
        c,"promomed-test-issuer","key-v1","Compromise drill","governance@test"
    )
    revoked_doc=evidence_checkpoint.issuer_document(c)
    result=evidence_checkpoint.verify_portable(old_envelope,revoked_doc,evidence_checkpoint.status_list(c))
    assert result["status"]=="ISSUER_KEY_REVOKED"
    assert result["revoked"] is True


def test_status_list_exposes_checkpoint_revocation_without_private_material(monkeypatch):
    if not CRYPTO_AVAILABLE:
        return
    _configure(monkeypatch)
    c=_db()
    envelope=evidence_checkpoint.issue(c,"content","CT01")
    evidence_checkpoint.revoke(
        c,envelope["checkpointSha256"],"content","CT01","Correction published","editor@test"
    )
    status=evidence_checkpoint.status_list(c)

    assert status["schemaVersion"]=="promomed-evidence-status-list-v1"
    assert status["revokedCheckpoints"][0]["checkpointSha256"]==envelope["checkpointSha256"]
    assert "private" not in str(status).lower()
