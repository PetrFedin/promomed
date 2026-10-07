import base64
import hashlib
import json
import os
import time

from app import change_impact, evidence_seal


CHECKPOINT_VERSION = "promomed-evidence-checkpoint-v1"
ISSUER_DOCUMENT_VERSION = "promomed-evidence-issuer-document-v1"
STATUS_LIST_VERSION = "promomed-evidence-status-list-v1"
DEFAULT_ISSUER_ID = "sostoyanie-evidence-authority"
DEFAULT_KEY_ID = "sostoyanie-evidence-v1"


def _issuer_id():
    return os.environ.get("PROMOMED_EVIDENCE_ISSUER_ID", DEFAULT_ISSUER_ID).strip() or DEFAULT_ISSUER_ID


def _key_id():
    return os.environ.get("PROMOMED_EVIDENCE_KEY_ID", DEFAULT_KEY_ID).strip() or DEFAULT_KEY_ID


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _sha(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _b64u(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _ub64u(value):
    value = str(value or "")
    return base64.urlsafe_b64decode(value + "=" * ((-len(value)) % 4))


def _private_key():
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("cryptography_required_for_evidence_checkpoint") from exc
    raw = os.environ.get("PROMOMED_EVIDENCE_SIGNING_PRIVATE_KEY_B64", "").strip()
    if not raw:
        raise ValueError("evidence_checkpoint_issuer_not_configured")
    decoded = _ub64u(raw)
    if len(decoded) != 32:
        raise ValueError("evidence_checkpoint_key_invalid")
    return Ed25519PrivateKey.from_private_bytes(decoded)


def _public_key_b64(private=None):
    from cryptography.hazmat.primitives import serialization

    private = private or _private_key()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return _b64u(public)


def _public_key_from_b64(value):
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("cryptography_required_for_evidence_checkpoint") from exc
    raw = _ub64u(value)
    if len(raw) != 32:
        raise ValueError("issuer_public_key_invalid")
    return Ed25519PublicKey.from_public_bytes(raw)


def _key_row(c, issuer_id, key_id):
    row = c.execute(
        """SELECT issuer_id,key_id,alg,public_key_b64,status,valid_from,valid_until,
                  rotated_from_key_id,created_at,created_by,retired_at,revoked_at,revoked_reason
           FROM evidence_issuer_keys WHERE issuer_id=? AND key_id=?""",
        (issuer_id, key_id),
    ).fetchone()
    return dict(row) if row else None


def _safe_key_record(row):
    if not row:
        return None
    return {
        "issuerId": row["issuer_id"],
        "keyId": row["key_id"],
        "alg": row["alg"],
        "publicKeyB64": row["public_key_b64"],
        "status": row["status"],
        "validFrom": row["valid_from"],
        "validUntil": row["valid_until"],
        "rotatedFromKeyId": row["rotated_from_key_id"],
        "retiredAt": row["retired_at"],
        "revokedAt": row["revoked_at"],
        "revokedReason": row["revoked_reason"],
    }


def _insert_key(c, issuer_id, key_id, public_key_b64, actor, rotated_from=None, now=None):
    now = int(now or time.time())
    c.execute(
        """INSERT INTO evidence_issuer_keys(
             issuer_id,key_id,alg,public_key_b64,status,valid_from,valid_until,
             rotated_from_key_id,created_at,created_by,retired_at,revoked_at,revoked_reason
           ) VALUES(?,?, 'Ed25519',?,'active',?,NULL,?,?,?,NULL,NULL,NULL)""",
        (issuer_id, key_id, public_key_b64, now, rotated_from, now, actor),
    )
    return _key_row(c, issuer_id, key_id)


def ensure_current_key_registered(c, actor="issuer_bootstrap"):
    issuer_id = _issuer_id()
    key_id = _key_id()
    private = _private_key()
    public_key_b64 = _public_key_b64(private)
    row = _key_row(c, issuer_id, key_id)
    if row:
        if row["public_key_b64"] != public_key_b64:
            raise ValueError("evidence_checkpoint_key_id_collision")
        if row["status"] != "active":
            raise ValueError("evidence_checkpoint_key_not_active")
        return row

    count = c.execute(
        "SELECT COUNT(*) n FROM evidence_issuer_keys WHERE issuer_id=?",
        (issuer_id,),
    ).fetchone()["n"]
    if count:
        raise ValueError("evidence_checkpoint_key_activation_required")
    return _insert_key(c, issuer_id, key_id, public_key_b64, actor)


def activate_current_key(c, actor):
    issuer_id = _issuer_id()
    key_id = _key_id()
    private = _private_key()
    public_key_b64 = _public_key_b64(private)
    existing = _key_row(c, issuer_id, key_id)
    if existing:
        if existing["public_key_b64"] != public_key_b64:
            raise ValueError("evidence_checkpoint_key_id_collision")
        if existing["status"] == "active":
            return _safe_key_record(existing)
        raise ValueError("issuer_key_not_activatable")

    now = int(time.time())
    prior = c.execute(
        """SELECT key_id FROM evidence_issuer_keys
           WHERE issuer_id=? AND status='active'
           ORDER BY valid_from DESC,key_id DESC LIMIT 1""",
        (issuer_id,),
    ).fetchone()
    rotated_from = prior["key_id"] if prior else None
    if prior:
        c.execute(
            """UPDATE evidence_issuer_keys
               SET status='retired',valid_until=?,retired_at=?
               WHERE issuer_id=? AND key_id=? AND status='active'""",
            (now, now, issuer_id, rotated_from),
        )
    row = _insert_key(c, issuer_id, key_id, public_key_b64, actor, rotated_from=rotated_from, now=now)
    return _safe_key_record(row)


def retire_key(c, issuer_id, key_id, actor):
    row = _key_row(c, issuer_id, key_id)
    if not row:
        raise ValueError("issuer_key_not_found")
    if row["status"] == "revoked":
        raise ValueError("issuer_key_revoked")
    if row["status"] == "retired":
        return _safe_key_record(row)
    now = int(time.time())
    c.execute(
        """UPDATE evidence_issuer_keys
           SET status='retired',valid_until=?,retired_at=?
           WHERE issuer_id=? AND key_id=?""",
        (now, now, issuer_id, key_id),
    )
    return _safe_key_record(_key_row(c, issuer_id, key_id))


def revoke_key(c, issuer_id, key_id, reason, actor):
    reason = str(reason or "").strip()
    if len(reason) < 3 or len(reason) > 500:
        raise ValueError("revocation_reason_invalid")
    row = _key_row(c, issuer_id, key_id)
    if not row:
        raise ValueError("issuer_key_not_found")
    if row["status"] == "revoked":
        return _safe_key_record(row)
    now = int(time.time())
    c.execute(
        """UPDATE evidence_issuer_keys
           SET status='revoked',valid_until=COALESCE(valid_until,?),revoked_at=?,revoked_reason=?
           WHERE issuer_id=? AND key_id=?""",
        (now, now, reason, issuer_id, key_id),
    )
    return _safe_key_record(_key_row(c, issuer_id, key_id))


def issuer_document(c, issuer_id=None):
    issuer_id = str(issuer_id or _issuer_id()).strip()
    rows = [
        dict(r)
        for r in c.execute(
            """SELECT issuer_id,key_id,alg,public_key_b64,status,valid_from,valid_until,
                      rotated_from_key_id,created_at,created_by,retired_at,revoked_at,revoked_reason
               FROM evidence_issuer_keys WHERE issuer_id=?
               ORDER BY valid_from,key_id""",
            (issuer_id,),
        )
    ]
    active = [r["key_id"] for r in rows if r["status"] == "active"]
    return {
        "schemaVersion": ISSUER_DOCUMENT_VERSION,
        "issuerId": issuer_id,
        "checkpointVersion": CHECKPOINT_VERSION,
        "keys": [_safe_key_record(r) for r in rows],
        "activeKeyIds": active,
        "medicalEfficacyCertified": False,
    }


def public_key_document(c):
    doc = issuer_document(c)
    active = [k for k in doc["keys"] if k["status"] == "active"]
    if not active:
        raise ValueError("evidence_checkpoint_issuer_not_registered")
    key = active[-1]
    return {
        "issuer_id": doc["issuerId"],
        "key_id": key["keyId"],
        "alg": key["alg"],
        "public_key_b64": key["publicKeyB64"],
        "checkpoint_version": CHECKPOINT_VERSION,
        "status": key["status"],
        "valid_from": key["validFrom"],
        "valid_until": key["validUntil"],
    }


def _record_issuance(c, envelope):
    payload = envelope["payload"]
    artifact = payload["artifact"]
    c.execute(
        """INSERT INTO evidence_checkpoint_issuance(
             checkpoint_sha256,issuer_id,key_id,artifact_kind,artifact_ref,issued_at,seal_sha256,
             payload_json,signature_b64
           ) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(checkpoint_sha256) DO NOTHING""",
        (
            envelope["checkpointSha256"],
            payload["issuerId"],
            payload["keyId"],
            artifact["kind"],
            artifact["ref"],
            payload["issuedAt"],
            payload["sealSha256"],
            json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")),
            envelope["signature"],
        ),
    )


def checkpoint_document(c, checkpoint_sha256):
    checkpoint_sha256=str(checkpoint_sha256 or "").strip().lower()
    if len(checkpoint_sha256)!=64 or any(ch not in "0123456789abcdef" for ch in checkpoint_sha256):
        raise ValueError("checkpoint_sha256_invalid")
    row=c.execute(
        """SELECT checkpoint_sha256,payload_json,signature_b64
           FROM evidence_checkpoint_issuance WHERE checkpoint_sha256=?""",
        (checkpoint_sha256,),
    ).fetchone()
    if not row:
        raise ValueError("checkpoint_not_found")
    return {
        "payload": json.loads(row["payload_json"]),
        "signature": row["signature_b64"],
        "checkpointSha256": row["checkpoint_sha256"],
    }


def issue(c, artifact_kind, artifact_ref):
    seal = evidence_seal.build(c, artifact_kind=artifact_kind, artifact_ref=artifact_ref)
    if not seal.get("validForProcess"):
        raise ValueError("evidence_seal_not_process_valid")
    if change_impact.is_held(c, artifact_kind, artifact_ref):
        raise ValueError("artifact_publication_held")

    key = ensure_current_key_registered(c)
    payload = {
        "checkpointVersion": CHECKPOINT_VERSION,
        "issuerId": key["issuer_id"],
        "keyId": key["key_id"],
        "alg": "Ed25519",
        "issuedAt": int(time.time()),
        "artifact": {"kind": artifact_kind, "ref": artifact_ref},
        "sealState": seal.get("state"),
        "sealSha256": seal.get("evidencePackageSha256"),
        "medicalEfficacyCertified": False,
    }
    signature = _private_key().sign(_canonical(payload))
    envelope = {"payload": payload, "signature": _b64u(signature)}
    envelope["checkpointSha256"] = _sha(envelope)
    _record_issuance(c, envelope)
    return envelope


def _verify_with_public_key(envelope, key_record):
    try:
        from cryptography.exceptions import InvalidSignature

        payload = envelope["payload"]
        if payload.get("checkpointVersion") != CHECKPOINT_VERSION:
            return False, "checkpoint_version_mismatch"
        if payload.get("issuerId") != key_record.get("issuerId") or payload.get("keyId") != key_record.get("keyId"):
            return False, "issuer_mismatch"
        if payload.get("alg") != "Ed25519" or key_record.get("alg") != "Ed25519":
            return False, "algorithm_mismatch"
        _public_key_from_b64(key_record.get("publicKeyB64")).verify(
            _ub64u(envelope["signature"]),
            _canonical(payload),
        )
        expected = _sha({"payload": payload, "signature": envelope["signature"]})
        if expected != str(envelope.get("checkpointSha256") or ""):
            return False, "envelope_hash_mismatch"
        return True, None
    except InvalidSignature:
        return False, "invalid_signature"
    except (KeyError, TypeError, ValueError, ModuleNotFoundError):
        return False, "invalid_signature"


def status_list(c, issuer_id=None):
    issuer_id = str(issuer_id or _issuer_id()).strip()
    key_rows = [
        dict(r)
        for r in c.execute(
            """SELECT issuer_id,key_id,alg,public_key_b64,status,valid_from,valid_until,
                      rotated_from_key_id,created_at,created_by,retired_at,revoked_at,revoked_reason
               FROM evidence_issuer_keys WHERE issuer_id=?
               ORDER BY valid_from,key_id""",
            (issuer_id,),
        )
    ]
    revoked = [
        dict(r)
        for r in c.execute(
            """SELECT r.checkpoint_sha256,r.artifact_kind,r.artifact_ref,r.reason,r.revoked_at,
                      i.key_id,i.issued_at
               FROM evidence_checkpoint_revocations r
               JOIN evidence_checkpoint_issuance i ON i.checkpoint_sha256=r.checkpoint_sha256
               WHERE i.issuer_id=?
               ORDER BY r.revoked_at,r.checkpoint_sha256""",
            (issuer_id,),
        )
    ]
    return {
        "schemaVersion": STATUS_LIST_VERSION,
        "issuerId": issuer_id,
        "generatedAt": int(time.time()),
        "keys": [_safe_key_record(r) for r in key_rows],
        "revokedCheckpoints": [
            {
                "checkpointSha256": r["checkpoint_sha256"],
                "keyId": r["key_id"],
                "issuedAt": r["issued_at"],
                "artifact": {"kind": r["artifact_kind"], "ref": r["artifact_ref"]},
                "revokedAt": r["revoked_at"],
                "reason": r["reason"],
            }
            for r in revoked
        ],
        "medicalEfficacyCertified": False,
    }


def verify_portable(envelope, issuer_doc, status_doc=None):
    try:
        payload = envelope["payload"]
        issuer_id = str(payload.get("issuerId") or "")
        key_id = str(payload.get("keyId") or "")
        if not issuer_id or not key_id:
            return {"status": "INVALID_ENVELOPE", "signature_valid": False, "revoked": False}
        if str((issuer_doc or {}).get("issuerId") or "") != issuer_id:
            return {"status": "UNKNOWN_ISSUER_KEY", "signature_valid": False, "revoked": False}
        keys = (issuer_doc or {}).get("keys") or []
        key = next((k for k in keys if k.get("keyId") == key_id), None)
        if not key:
            return {"status": "UNKNOWN_ISSUER_KEY", "signature_valid": False, "revoked": False}

        valid, reason = _verify_with_public_key(envelope, key)
        if not valid:
            return {
                "status": "INVALID_ENVELOPE_HASH" if reason == "envelope_hash_mismatch" else "INVALID_SIGNATURE",
                "signature_valid": False,
                "revoked": False,
                "reason": reason,
            }

        issued_at = int(payload.get("issuedAt"))
        valid_from = int(key.get("validFrom") or 0)
        valid_until = key.get("validUntil")
        if issued_at < valid_from or (valid_until is not None and issued_at > int(valid_until)):
            return {
                "status": "KEY_NOT_VALID_AT_ISSUANCE",
                "signature_valid": True,
                "revoked": False,
            }
        if key.get("status") == "revoked":
            return {
                "status": "ISSUER_KEY_REVOKED",
                "signature_valid": True,
                "revoked": True,
                "keyRevoked": True,
            }

        checkpoint_sha = str(envelope.get("checkpointSha256") or "")
        if status_doc and str(status_doc.get("issuerId") or "") != issuer_id:
            return {
                "status": "STATUS_LIST_ISSUER_MISMATCH",
                "signature_valid": True,
                "revoked": False,
            }
        revoked_rows = (status_doc or {}).get("revokedCheckpoints") or []
        revoked = next((r for r in revoked_rows if r.get("checkpointSha256") == checkpoint_sha), None)
        if revoked:
            return {
                "status": "REVOKED",
                "signature_valid": True,
                "revoked": True,
                "revocation": revoked,
            }
        return {
            "status": "VALID_PORTABLE",
            "signature_valid": True,
            "revoked": False,
            "checkpointSha256": checkpoint_sha,
            "issuerId": issuer_id,
            "keyId": key_id,
            "medicalEfficacyCertified": False,
            "currentCanonicalStateVerified": False,
        }
    except (KeyError, TypeError, ValueError):
        return {"status": "INVALID_ENVELOPE", "signature_valid": False, "revoked": False}


def revoke(c, checkpoint_sha256, artifact_kind, artifact_ref, reason, actor):
    checkpoint_sha256 = str(checkpoint_sha256 or "").strip().lower()
    if len(checkpoint_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in checkpoint_sha256):
        raise ValueError("checkpoint_sha256_invalid")
    reason = str(reason or "").strip()
    if len(reason) < 3 or len(reason) > 500:
        raise ValueError("revocation_reason_invalid")
    issued = c.execute(
        """SELECT artifact_kind,artifact_ref FROM evidence_checkpoint_issuance
           WHERE checkpoint_sha256=?""",
        (checkpoint_sha256,),
    ).fetchone()
    if issued and (issued["artifact_kind"] != artifact_kind or issued["artifact_ref"] != artifact_ref):
        raise ValueError("checkpoint_artifact_mismatch")
    now = int(time.time())
    c.execute(
        """INSERT INTO evidence_checkpoint_revocations(
             checkpoint_sha256,artifact_kind,artifact_ref,reason,revoked_by,revoked_at
           ) VALUES(?,?,?,?,?,?) ON CONFLICT(checkpoint_sha256) DO NOTHING""",
        (checkpoint_sha256, artifact_kind, artifact_ref, reason, actor, now),
    )
    row = c.execute(
        """SELECT checkpoint_sha256,artifact_kind,artifact_ref,reason,revoked_by,revoked_at
           FROM evidence_checkpoint_revocations WHERE checkpoint_sha256=?""",
        (checkpoint_sha256,),
    ).fetchone()
    return dict(row) if row else {"checkpoint_sha256": checkpoint_sha256}


def verify(c, envelope):
    try:
        payload = envelope["payload"]
        issuer_id = str(payload.get("issuerId") or "")
    except (KeyError, TypeError):
        return {"status": "INVALID_ENVELOPE", "signature_valid": False, "current": False, "revoked": False}

    portable = verify_portable(envelope, issuer_document(c, issuer_id), status_list(c, issuer_id))
    if portable["status"] != "VALID_PORTABLE":
        return {**portable, "current": False}

    artifact = payload.get("artifact") or {}
    kind = str(artifact.get("kind") or "")
    ref = str(artifact.get("ref") or "")
    if not kind or not ref:
        return {
            "status": "INVALID_ENVELOPE",
            "signature_valid": False,
            "current": False,
            "revoked": False,
            "reason": "artifact_missing",
        }

    if change_impact.is_held(c, kind, ref):
        return {
            "status": "STALE_OR_HELD",
            "signature_valid": True,
            "current": False,
            "revoked": False,
            "publication_hold": True,
        }

    current = evidence_seal.build(c, artifact_kind=kind, artifact_ref=ref)
    if not current.get("validForProcess"):
        return {
            "status": "STALE_OR_HELD",
            "signature_valid": True,
            "current": False,
            "revoked": False,
            "publication_hold": False,
            "seal_state": current.get("state"),
        }
    if current.get("evidencePackageSha256") != payload.get("sealSha256"):
        return {
            "status": "STALE_OR_HELD",
            "signature_valid": True,
            "current": False,
            "revoked": False,
            "publication_hold": False,
            "currentSealSha256": current.get("evidencePackageSha256"),
        }
    return {
        "status": "VALID",
        "signature_valid": True,
        "current": True,
        "revoked": False,
        "checkpointSha256": envelope.get("checkpointSha256"),
        "sealSha256": current.get("evidencePackageSha256"),
        "issuerId": payload.get("issuerId"),
        "keyId": payload.get("keyId"),
        "medicalEfficacyCertified": False,
    }
