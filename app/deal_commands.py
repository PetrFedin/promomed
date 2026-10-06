from app.commanding import custom, error
from app import deal_room

ROUTES = {
    "/api/deal-room/accept-demo",
    "/api/deal-room/reset-demo",
}


def handle_command(c, route, role, email, data):
    if route not in ROUTES:
        return None
    if role not in ("sales", "organizer"):
        return error("forbidden", 403)

    if route == "/api/deal-room/reset-demo":
        deal_room.reset_demo(c, email)
        return custom(deal_room.snapshot(c))

    tranche_id = str(data.get("tranche_id") or "").strip()
    milestone_id = str(data.get("milestone_id") or "").strip()
    obligation_id = str(data.get("obligation_id") or "").strip()
    evidence_ref = str(data.get("evidence_ref") or "").strip()
    note = str(data.get("note") or "").strip()
    if not tranche_id or not milestone_id or not obligation_id:
        return error("missing_deal_target", 400)
    try:
        deal_room.attach_and_accept_demo(
            c,
            tranche_id,
            milestone_id,
            obligation_id,
            email,
            evidence_ref,
            note=note,
        )
    except ValueError as e:
        return error(str(e), 400)
    return custom(deal_room.snapshot(c))
