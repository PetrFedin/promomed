import base64
import hashlib
import json
import os
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app import change_impact, evidence_seal


CHECKPOINT_VERSION="promomed-evidence-checkpoint-v1"
ISSUER_ID=os.environ.get("PROMOMED_EVIDENCE_ISSUER_ID","sostoyanie-evidence-authority").strip() or "sostoyanie-evidence-authority"
KEY_ID=os.environ.get("PROMOMED_EVIDENCE_KEY_ID","sostoyanie-evidence-v1").strip() or "sostoyanie-evidence-v1"


def _canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str).encode("utf-8")


def _sha(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _b64u(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _ub64u(value):
    value=str(value or "")
    return base64.urlsafe_b64decode(value+"="*((-len(value))%4))


def _private_key():
    raw=os.environ.get("PROMOMED_EVIDENCE_SIGNING_PRIVATE_KEY_B64","").strip()
    if not raw:
        raise ValueError("evidence_checkpoint_issuer_not_configured")
    decoded=_ub64u(raw)
    if len(decoded)!=32:
        raise ValueError("evidence_checkpoint_key_invalid")
    return Ed25519PrivateKey.from_private_bytes(decoded)


def public_key_document():
    public=_private_key().public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {
        "issuer_id":ISSUER_ID,
        "key_id":KEY_ID,
        "alg":"Ed25519",
        "public_key_b64":_b64u(public),
        "checkpoint_version":CHECKPOINT_VERSION,
    }


def issue(c,artifact_kind,artifact_ref):
    seal=evidence_seal.build(c,artifact_kind=artifact_kind,artifact_ref=artifact_ref)
    if not seal.get("validForProcess"):
        raise ValueError("evidence_seal_not_process_valid")
    if change_impact.is_held(c,artifact_kind,artifact_ref):
        raise ValueError("artifact_publication_held")
    payload={
        "checkpointVersion":CHECKPOINT_VERSION,
        "issuerId":ISSUER_ID,
        "keyId":KEY_ID,
        "alg":"Ed25519",
        "issuedAt":int(time.time()),
        "artifact":{"kind":artifact_kind,"ref":artifact_ref},
        "sealState":seal.get("state"),
        "sealSha256":seal.get("evidencePackageSha256"),
        "medicalEfficacyCertified":False,
    }
    signature=_private_key().sign(_canonical(payload))
    envelope={"payload":payload,"signature":_b64u(signature)}
    envelope["checkpointSha256"]=_sha(envelope)
    return envelope


def _verify_signature(envelope):
    try:
        payload=envelope["payload"]
        if payload.get("checkpointVersion")!=CHECKPOINT_VERSION:
            return False,"checkpoint_version_mismatch"
        if payload.get("issuerId")!=ISSUER_ID or payload.get("keyId")!=KEY_ID or payload.get("alg")!="Ed25519":
            return False,"issuer_mismatch"
        private=_private_key()
        private.public_key().verify(_ub64u(envelope["signature"]),_canonical(payload))
        expected=_sha({"payload":payload,"signature":envelope["signature"]})
        if expected!=str(envelope.get("checkpointSha256") or ""):
            return False,"envelope_hash_mismatch"
        return True,None
    except InvalidSignature:
        return False,"invalid_signature"
    except (KeyError,TypeError,ValueError):
        return False,"invalid_signature"


def revoke(c,checkpoint_sha256,artifact_kind,artifact_ref,reason,actor):
    checkpoint_sha256=str(checkpoint_sha256 or "").strip().lower()
    if len(checkpoint_sha256)!=64 or any(ch not in "0123456789abcdef" for ch in checkpoint_sha256):
        raise ValueError("checkpoint_sha256_invalid")
    reason=str(reason or "").strip()
    if len(reason)<3 or len(reason)>500:
        raise ValueError("revocation_reason_invalid")
    now=int(time.time())
    c.execute(
        "INSERT INTO evidence_checkpoint_revocations(checkpoint_sha256,artifact_kind,artifact_ref,reason,revoked_by,revoked_at) VALUES(?,?,?,?,?,?) ON CONFLICT(checkpoint_sha256) DO NOTHING",
        (checkpoint_sha256,artifact_kind,artifact_ref,reason,actor,now),
    )
    row=c.execute(
        "SELECT checkpoint_sha256,artifact_kind,artifact_ref,reason,revoked_by,revoked_at FROM evidence_checkpoint_revocations WHERE checkpoint_sha256=?",
        (checkpoint_sha256,),
    ).fetchone()
    return dict(row) if row else {"checkpoint_sha256":checkpoint_sha256}


def verify(c,envelope):
    try:
        _private_key()
    except ValueError:
        return {"status":"ISSUER_NOT_CONFIGURED","signature_valid":False,"current":False,"revoked":False}

    valid,reason=_verify_signature(envelope)
    if not valid:
        return {
            "status":"INVALID_ENVELOPE_HASH" if reason=="envelope_hash_mismatch" else "INVALID_SIGNATURE",
            "signature_valid":False,"current":False,"revoked":False,"reason":reason,
        }

    sha=str(envelope.get("checkpointSha256") or "")
    row=c.execute(
        "SELECT reason,revoked_by,revoked_at FROM evidence_checkpoint_revocations WHERE checkpoint_sha256=?",
        (sha,),
    ).fetchone()
    if row:
        return {"status":"REVOKED","signature_valid":True,"current":False,"revoked":True,"revocation":dict(row)}

    artifact=envelope["payload"].get("artifact") or {}
    kind=str(artifact.get("kind") or "")
    ref=str(artifact.get("ref") or "")
    if not kind or not ref:
        return {"status":"INVALID_SIGNATURE","signature_valid":False,"current":False,"revoked":False,"reason":"artifact_missing"}

    if change_impact.is_held(c,kind,ref):
        return {"status":"STALE_OR_HELD","signature_valid":True,"current":False,"revoked":False,"publication_hold":True}

    current=evidence_seal.build(c,artifact_kind=kind,artifact_ref=ref)
    if not current.get("validForProcess"):
        return {"status":"STALE_OR_HELD","signature_valid":True,"current":False,"revoked":False,"publication_hold":False,"seal_state":current.get("state")}
    if current.get("evidencePackageSha256")!=envelope["payload"].get("sealSha256"):
        return {
            "status":"STALE_OR_HELD","signature_valid":True,"current":False,"revoked":False,
            "publication_hold":False,"currentSealSha256":current.get("evidencePackageSha256"),
        }
    return {
        "status":"VALID","signature_valid":True,"current":True,"revoked":False,
        "checkpointSha256":sha,"sealSha256":current.get("evidencePackageSha256"),
        "medicalEfficacyCertified":False,
    }
