import time

from app.commanding import error, ok
from app.core import audit

ROUTES = {"/api/question", "/api/cms"}


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

    if role != "editor":
        return error("forbidden", 403)
    status = str(data.get("status", "approved"))
    c.execute(
        "UPDATE cms SET status=?,version=version+1,updated=? WHERE id='A-014'",
        (status, int(time.time())),
    )
    audit(c, "cms_status", email, {"status": status})
    return ok()
