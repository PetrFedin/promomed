from app.commanding import error, ok
from app.core import audit
from app.evidence_governance import record_review

ROUTES = {"/api/evidence/review"}

def handle_command(c, route, role, email, data):
    if route not in ROUTES:
        return None
    if role != "editor":
        return error("forbidden", 403)
    try:
        manifest = record_review(
            c,
            content_id=data.get("content_id"),
            source_type=data.get("source_type"),
            source_ref=data.get("source_ref"),
            source_date=data.get("source_date"),
            reviewer_email=email,
            reviewer_role=data.get("reviewer_role") or "medical_editor",
            disclosure=data.get("disclosure"),
            decision=data.get("decision"),
            valid_until=data.get("valid_until"),
        )
    except ValueError as exc:
        return error(str(exc), 422)
    audit(c, "evidence_review_recorded", email, {
        "content_id": manifest["content"]["id"],
        "content_version": manifest["content"]["version"],
        "seal_status": manifest["seal"]["status"],
        "evidence_package_sha256": manifest["evidencePackageSha256"],
    })
    return ok({"data": manifest})
