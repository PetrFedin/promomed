import time

from app.commanding import error, ok
from app.core import audit
from app import transcript_intelligence

ROUTES = {"/api/question", "/api/cms", "/api/transcript-takeaway-review"}


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
