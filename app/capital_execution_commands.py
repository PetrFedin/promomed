from app.commanding import custom, error
from app import capital_execution

ROUTES = {
    "/api/capital-plan-execution/update-demo",
    "/api/capital-plan-execution/reset-demo",
}


def handle_command(c, route, role, email, data):
    if route not in ROUTES:
        return None
    if role not in ("sales", "organizer"):
        return error("forbidden", 403)

    if route == "/api/capital-plan-execution/reset-demo":
        capital_execution.reset_demo(c, email)
        return custom(capital_execution.snapshot(c))

    package_id = str(data.get("package_id") or "").strip()
    if not package_id:
        return error("missing_package_id", 400)
    try:
        capital_execution.update_demo(
            c,
            package_id,
            email,
            status=data.get("status"),
            committed_rub=data.get("committed_rub"),
            actual_rub=data.get("actual_rub"),
            evidence_status=data.get("evidence_status"),
            evidence_ref=data.get("evidence_ref"),
            note=data.get("note"),
        )
    except ValueError as e:
        return error(str(e), 409)
    return custom(capital_execution.snapshot(c))
