from app.commanding import custom, error
from app import db, evidence_checkpoint

ROUTES={"/api/evidence-checkpoint/issue","/api/evidence-checkpoint/revoke"}

def handle_command(c,route,role,email,data):
    if route not in ROUTES:
        return None
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
    if route!="/api/evidence-checkpoint/verify":
        return None
    c=db.connect()
    try:
        return {"data":evidence_checkpoint.verify(c,data.get("envelope") or {})},200
    finally:
        c.close()
