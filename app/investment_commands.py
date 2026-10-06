from app.commanding import custom, error
from app import investment_proof

ROUTES = {
    "/api/investment-proof/accept-demo",
    "/api/investment-proof/reset-demo",
}


def handle_command(c, route, role, email, data):
    if route not in ROUTES:
        return None
    if role not in ("sales", "organizer"):
        return error("forbidden", 403)

    if route == "/api/investment-proof/reset-demo":
        tranche_id = str(data.get("tranche_id") or "").strip() or None
        investment_proof.reset_demo_acceptances(c, tranche_id)
        return custom(investment_proof.snapshot(c))

    tranche_id = str(data.get("tranche_id") or "").strip()
    acceptance_key = str(data.get("acceptance_key") or "").strip()
    if not tranche_id or not acceptance_key:
        return error("missing_acceptance_target", 400)
    try:
        record_hash = investment_proof.record_demo_acceptance(
            c,
            tranche_id,
            acceptance_key,
            email,
            note=str(data.get("note") or "").strip(),
            evidence_ref=str(data.get("evidence_ref") or "").strip(),
        )
    except ValueError:
        return error("unknown_acceptance_requirement", 404)

    payload = investment_proof.snapshot(c)
    payload["accepted_record_hash"] = record_hash
    return custom(payload)
