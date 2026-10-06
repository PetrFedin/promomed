from app.commanding import custom, error
from app import intervention_engine

ROUTES = {
    "/api/intervention-engine/create-demo",
    "/api/intervention-engine/reset-demo",
}


def handle_command(c, route, role, email, data):
    if route not in ROUTES:
        return None
    if role not in ("sales", "organizer"):
        return error("forbidden", 403)

    if route == "/api/intervention-engine/reset-demo":
        intervention_engine.reset_demo(c)
        return custom(intervention_engine.snapshot(c))

    package_id = str(data.get("package_id") or "").strip()
    if not package_id:
        return error("missing_package_id", 400)
    try:
        intervention_engine.create_demo_intervention(c, package_id, email)
    except ValueError as e:
        return error(str(e), 404)
    return custom(intervention_engine.snapshot(c))
