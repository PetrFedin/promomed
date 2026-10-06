import time

from app.commanding import error, ok
from app.core import audit
from app import transcript_intelligence, evidence_graph

ROUTES = {"/api/question", "/api/cms", "/api/transcript-takeaway-review", "/api/evidence-claim-correct", "/api/evidence-claim-retract"}


def handle_command(c, route, role, email, data):
    if route not in ROUTES:
        return None

    if route == "/api/question":
        if role != "participant":
            return error("forbidden", 403)
        text = str(data.get("text", "Как отличать корреляцию от причинности?"))[:500]
        c.execute("INSERT INTO questions(text,status,ts) VALUES(?,'review',?)", (text, int(time.time())))
        audit(c, "question_submitted", email, {})
        return ok()

    if route in ("/api/evidence-claim-correct", "/api/evidence-claim-retract"):
        if role != "editor":
            return error("forbidden", 403)
        claim_id = str(data.get("claim_id", ""))[:80].strip()
        if not claim_id:
            return error("claim_id_required", 422)
        try:
            if route == "/api/evidence-claim-correct":
                new_text = str(data.get("claim_text", "")).strip()
                if not new_text:
                    return error("claim_text_required", 422)
                new_id = evidence_graph.correct_demo_claim(c, claim_id, new_text, email)
                audit(c, "evidence_claim_corrected", email, {"claim_id": claim_id, "new_claim_id": new_id})
            else:
                evidence_graph.retract_demo_claim(c, claim_id, str(data.get("note", "")), email)
                audit(c, "evidence_claim_retracted", email, {"claim_id": claim_id})
        except ValueError as e:
            return error(str(e), 404 if str(e) == "claim_not_found" else 409)
        return ok()

    if route == "/api/transcript-takeaway-review":
        if role != "editor":
            return error("forbidden", 403)
        takeaway_id = str(data.get("takeaway_id", ""))[:80].strip()
        action = str(data.get("action", "approve_demo"))
        try:
            transcript_intelligence.review_takeaway(c, takeaway_id, action, email)
        except ValueError as e:
            return error(str(e), 404 if str(e) == "takeaway_not_found" else 400)
        audit(c, "transcript_takeaway_reviewed", email, {"takeaway_id": takeaway_id, "action": action})
        return ok()

    if role != "editor":
        return error("forbidden", 403)
    status = str(data.get("status", "approved"))
    c.execute(
        "UPDATE cms SET status=?,version=version+1,updated=? WHERE id='A-014'",
        (status, int(time.time())),
    )
    audit(c, "cms_status", email, {"status": status})
    return ok()
