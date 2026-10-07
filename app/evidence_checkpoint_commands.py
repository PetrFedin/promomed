from app.commanding import custom, error
from app import db, evidence_checkpoint

ROUTES={
    "/api/evidence-checkpoint/issue",
    "/api/evidence-checkpoint/revoke",
    "/api/evidence-checkpoint/key/activate",
    "/api/evidence-checkpoint/key/retire",
    "/api/evidence-checkpoint/key/revoke",
}


def handle_command(c,route,role,email,data):
    if route not in ROUTES:
        return None

    if route in (
        "/api/evidence-checkpoint/key/activate",
        "/api/evidence-checkpoint/key/retire",
        "/api/evidence-checkpoint/key/revoke",
    ):
        if role not in ("editor","governance"):
            return error("forbidden",403)
        try:
            if route=="/api/evidence-checkpoint/key/activate":
                return custom({"data":evidence_checkpoint.activate_current_key(c,email)})
            issuer_id=str(data.get("issuer_id") or "")[:120].strip()
            key_id=str(data.get("key_id") or "")[:120].strip()
            if not issuer_id or not key_id:
                return error("issuer_key_required",422)
            if route=="/api/evidence-checkpoint/key/retire":
                return custom({"data":evidence_checkpoint.retire_key(c,issuer_id,key_id,email)})
            reason=str(data.get("reason") or "")
            return custom({"data":evidence_checkpoint.revoke_key(c,issuer_id,key_id,reason,email)})
        except ValueError as exc:
            return error(str(exc),409)

    if role!="editor":
        return error("forbidden",403)

    if route=="/api/evidence-checkpoint/issue":
        kind=str(data.get("artifact_kind") or "")[:30]
        ref=str(data.get("artifact_ref") or "")[:80]
        if not kind or not ref:
            return error("artifact_required",422)
        try:
            return custom({"data":evidence_checkpoint.issue(c,kind,ref)})
        except ValueError as exc:
            return error(str(exc),409)

    sha=str(data.get("checkpoint_sha256") or "")
    kind=str(data.get("artifact_kind") or "")[:30]
    ref=str(data.get("artifact_ref") or "")[:80]
    reason=str(data.get("reason") or "")
    if not kind or not ref:
        return error("artifact_required",422)
    try:
        row=evidence_checkpoint.revoke(c,sha,kind,ref,reason,email)
        return custom({"data":row})
    except ValueError as exc:
        return error(str(exc),422)


def handle_public(route,data):
    if route not in (
        "/api/evidence-checkpoint/verify",
        "/api/evidence-checkpoint/verify-portable",
    ):
        return None
    c=db.connect()
    try:
        if route=="/api/evidence-checkpoint/verify-portable":
            return {
                "data":evidence_checkpoint.verify_portable(
                    data.get("envelope") or {},
                    data.get("issuer_document") or {},
                    data.get("status_list") or {},
                )
            },200
        return {"data":evidence_checkpoint.verify(c,data.get("envelope") or {})},200
    finally:
        c.close()
