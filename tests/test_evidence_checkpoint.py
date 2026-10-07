import base64
import os
import sqlite3
import unittest
from unittest.mock import patch

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


@unittest.skipUnless(CRYPTO_AVAILABLE,"cryptography dependency unavailable")
class EvidenceCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.c=_db()

    def tearDown(self):
        self.c.close()

    def _env(self,key_id="key-v1",key=None):
        return patch.dict(
            os.environ,
            {
                "PROMOMED_EVIDENCE_ISSUER_ID":"promomed-test-issuer",
                "PROMOMED_EVIDENCE_KEY_ID":key_id,
                "PROMOMED_EVIDENCE_SIGNING_PRIVATE_KEY_B64":key or _key_b64(),
            },
            clear=False,
        )

    def test_checkpoint_tracks_current_seal_hold_and_revocation(self):
        with self._env():
            envelope=evidence_checkpoint.issue(self.c,"content","CT01")
            stored=evidence_checkpoint.checkpoint_document(self.c,envelope["checkpointSha256"])
            self.assertEqual(stored,envelope)

            valid=evidence_checkpoint.verify(self.c,envelope)
            self.assertEqual(valid["status"],"VALID")
            self.assertTrue(valid["current"])
            self.assertFalse(valid["medicalEfficacyCertified"])

            tampered={
                **envelope,
                "payload":{**envelope["payload"],"sealSha256":"f"*64},
            }
            invalid=evidence_checkpoint.verify(self.c,tampered)
            self.assertEqual(invalid["status"],"INVALID_SIGNATURE")

            self.c.execute(
                "INSERT INTO publication_holds(id,event_id,artifact_kind,artifact_ref,reason,status,placed_at,placed_by,demo_only) VALUES(?,?,?,?,?,'active',?,?,1)",
                ("hold-1","event-1","content","CT01","Source retracted",1,"governance"),
            )
            held=evidence_checkpoint.verify(self.c,envelope)
            self.assertEqual(held["status"],"STALE_OR_HELD")
            self.assertTrue(held["publication_hold"])

            self.c.execute("DELETE FROM publication_holds")
            evidence_checkpoint.revoke(
                self.c,envelope["checkpointSha256"],"content","CT01",
                "Governance withdrawal","editor@test",
            )
            revoked=evidence_checkpoint.verify(self.c,envelope)
            self.assertEqual(revoked["status"],"REVOKED")
            self.assertTrue(revoked["revoked"])

    def test_checkpoint_issuer_fails_closed_without_key(self):
        env={
            "PROMOMED_EVIDENCE_ISSUER_ID":"promomed-test-issuer",
            "PROMOMED_EVIDENCE_KEY_ID":"key-v1",
        }
        with patch.dict(os.environ,env,clear=False):
            os.environ.pop("PROMOMED_EVIDENCE_SIGNING_PRIVATE_KEY_B64",None)
            with self.assertRaisesRegex(ValueError,"evidence_checkpoint_issuer_not_configured"):
                evidence_checkpoint.issue(self.c,"content","CT01")

    def test_portable_verifier_uses_public_key_not_private_key(self):
        with self._env():
            envelope=evidence_checkpoint.issue(self.c,"content","CT01")
            issuer_doc=evidence_checkpoint.issuer_document(self.c)
            status_doc=evidence_checkpoint.status_list(self.c)

        with patch.dict(os.environ,{},clear=False):
            os.environ.pop("PROMOMED_EVIDENCE_SIGNING_PRIVATE_KEY_B64",None)
            result=evidence_checkpoint.verify_portable(envelope,issuer_doc,status_doc)

        self.assertEqual(result["status"],"VALID_PORTABLE")
        self.assertTrue(result["signature_valid"])
        self.assertFalse(result["currentCanonicalStateVerified"])
        self.assertFalse(result["medicalEfficacyCertified"])

    def test_key_rotation_preserves_old_signature_then_revocation_invalidates_trust(self):
        with self._env("key-v1"):
            old_envelope=evidence_checkpoint.issue(self.c,"content","CT01")

        with self._env("key-v2"):
            rotated=evidence_checkpoint.activate_current_key(self.c,"governance@test")
        self.assertEqual(rotated["keyId"],"key-v2")
        self.assertEqual(rotated["rotatedFromKeyId"],"key-v1")

        issuer_doc=evidence_checkpoint.issuer_document(self.c,"promomed-test-issuer")
        old_key=next(k for k in issuer_doc["keys"] if k["keyId"]=="key-v1")
        self.assertEqual(old_key["status"],"retired")
        self.assertEqual(
            evidence_checkpoint.verify_portable(
                old_envelope,issuer_doc,evidence_checkpoint.status_list(self.c,"promomed-test-issuer")
            )["status"],
            "VALID_PORTABLE",
        )

        evidence_checkpoint.revoke_key(
            self.c,"promomed-test-issuer","key-v1","Compromise drill","governance@test",
        )
        revoked_doc=evidence_checkpoint.issuer_document(self.c,"promomed-test-issuer")
        result=evidence_checkpoint.verify_portable(
            old_envelope,revoked_doc,evidence_checkpoint.status_list(self.c,"promomed-test-issuer")
        )
        self.assertEqual(result["status"],"ISSUER_KEY_REVOKED")
        self.assertTrue(result["revoked"])

    def test_status_list_exposes_checkpoint_revocation_without_private_material(self):
        with self._env():
            envelope=evidence_checkpoint.issue(self.c,"content","CT01")
            evidence_checkpoint.revoke(
                self.c,envelope["checkpointSha256"],"content","CT01",
                "Correction published","editor@test",
            )
            status=evidence_checkpoint.status_list(self.c)

        self.assertEqual(status["schemaVersion"],"promomed-evidence-status-list-v1")
        self.assertEqual(
            status["revokedCheckpoints"][0]["checkpointSha256"],
            envelope["checkpointSha256"],
        )
        self.assertNotIn("private",str(status).lower())

    def test_status_list_must_match_checkpoint_issuer(self):
        with self._env():
            envelope=evidence_checkpoint.issue(self.c,"content","CT01")
            issuer=evidence_checkpoint.issuer_document(self.c)
        result=evidence_checkpoint.verify_portable(
            envelope,issuer,
            {"issuerId":"different-issuer","revokedCheckpoints":[]},
        )
        self.assertEqual(result["status"],"STATUS_LIST_ISSUER_MISMATCH")


if __name__=="__main__":
    unittest.main()
