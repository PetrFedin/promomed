from app.commanding import custom, error
from app import deal_room

ROUTES = {
    "/api/deal-room/accept-demo",
    "/api/deal-room/reset-demo",
    "/api/deal-room/register-evidence-demo",
    "/api/deal-room/create-payment-request-demo",
}


def handle_command(c, route, role, email, data):
    if route not in ROUTES:
        return None
    if role not in ("sales", "organizer"):
        return error("forbidden", 403)

    if route == "/api/deal-room/reset-demo":
        deal_room.reset_demo(c, email)
        return custom(deal_room.snapshot(c))

    if route == "/api/deal-room/register-evidence-demo":
        tranche_id = str(data.get("tranche_id") or "").strip()
        milestone_id = str(data.get("milestone_id") or "").strip()
        obligation_id = str(data.get("obligation_id") or "").strip()
        storage_ref = str(data.get("storage_ref") or "").strip()
        if not tranche_id or not milestone_id or not obligation_id:
            return error("missing_deal_target", 400)
        try:
            doc = deal_room.register_demo_evidence(
                c,
                tranche_id,
                milestone_id,
                obligation_id,
                email,
                str(data.get("title") or "").strip(),
                str(data.get("document_type") or "").strip(),
                storage_ref,
            )
        except ValueError as e:
            return error(str(e), 400)
        payload = deal_room.snapshot(c)
        payload["registered_document"] = doc
        return custom(payload)

    if route == "/api/deal-room/create-payment-request-demo":
        try:
            request_id = deal_room.create_demo_payment_request(c, email)
        except ValueError as e:
            return error(str(e), 409)
        payload = deal_room.snapshot(c)
        payload["created_payment_request_id"] = request_id
        return custom(payload)

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
