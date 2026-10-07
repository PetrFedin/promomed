from urllib.parse import parse_qs, urlparse

from app import db, evidence_checkpoint, evidence_seal


def _conn():
    return db.connect()


def serve_get(path, full_path):
    if path in ("/api/evidence-seal", "/api/evidence-bundle"):
        q=parse_qs(urlparse(full_path).query)
        kind=(q.get("artifact_kind") or [""])[0][:30]
        ref=(q.get("artifact_ref") or [""])[0][:80]
        if not kind or not ref:
            return {"error":"artifact_required"},422
        c=_conn()
        try:
            data=evidence_seal.build(c,artifact_kind=kind,artifact_ref=ref) if path=="/api/evidence-seal" else evidence_seal.portable_bundle(c,artifact_kind=kind,artifact_ref=ref)
        finally:
            c.close()
        return {"data":data},200

    if path=="/api/evidence-checkpoint/public-key":
        try:
            return {"data":evidence_checkpoint.public_key_document()},200
        except (ValueError, ModuleNotFoundError) as exc:
            return {"error":str(exc)},503
    return None


def serve_public_post(path, data):
    if path!="/api/evidence-checkpoint/verify":
        return None
    c=_conn()
    try:
        return {"data":evidence_checkpoint.verify(c,data.get("envelope") or {})},200
    finally:
        c.close()
