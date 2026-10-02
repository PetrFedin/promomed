from app.analytics import commercial
from app.commanding import error, ok
from app.core import sval
from app.demo import DEMO_STEPS, reset_demo, run_demo_step

ROUTES = {"/api/demo/reset", "/api/demo/next"}


def handle_command(c, route, role, email, data):
    if route not in ROUTES:
        return None
    if role not in ("sales", "organizer"):
        return error("forbidden", 403)
    if route == "/api/demo/reset":
        reset_demo(c, email)
        return ok()
    current = int(sval(c, "demo_step", "0"))
    nxt = current + 1
    if nxt >= len(DEMO_STEPS):
        return error("demo_complete", 409, dashboard=commercial(c))
    run_demo_step(c, nxt, email)
    return ok()
