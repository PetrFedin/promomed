from urllib.parse import unquote

from app import capital_optimizer, capital_plan, capital_execution, intervention_engine, recovery_reforecast, reallocation_authority, contract_builder, deal_room, investment_proof, portfolio_control, institutional_command_center, institutional_pilot_proposal, institutional_buyer_fit, institutional_outreach_pack


ROUTES = {
    "/api/capital-allocation-optimizer",
    "/api/capital-allocation-plan",
    "/api/capital-plan-execution",
    "/api/intervention-engine",
    "/api/recovery-reforecast",
    "/api/reallocation-authority",
    "/api/portfolio-capital-control",
    "/api/deal-room",
    "/api/contract-builder",
    "/api/investment-proof-system",
}
COMMAND_CENTER_PREFIX = "/api/institutional-command-center/"
PILOT_PROPOSAL_PREFIX = "/api/institutional-pilot-proposal/"
BUYER_FIT_ROUTE = "/api/institutional-buyer-fit-matrix"
OUTREACH_PREFIX = "/api/institutional-outreach-pack/"


def read(c, path, role):
    if path.startswith(OUTREACH_PREFIX):
        if role not in ("organizer", "partner", "sales"):
            return {"error": "forbidden"}, 403
        archetype=unquote(path[len(OUTREACH_PREFIX):]).strip()[:80]
        if not archetype:
            return {"error": "archetype_required"}, 422
        try:
            return institutional_outreach_pack.snapshot(c, archetype), 200
        except ValueError as exc:
            return {"error": str(exc)}, 422

    if path == BUYER_FIT_ROUTE:
        if role not in ("organizer", "partner", "sales"):
            return {"error": "forbidden"}, 403
        return institutional_buyer_fit.snapshot(c), 200

    if path.startswith(PILOT_PROPOSAL_PREFIX):
        if role not in ("organizer", "partner", "sales"):
            return {"error": "forbidden"}, 403
        archetype = unquote(path[len(PILOT_PROPOSAL_PREFIX):]).strip()[:80]
        if not archetype:
            return {"error": "archetype_required"}, 422
        try:
            return institutional_pilot_proposal.snapshot(c, archetype), 200
        except ValueError as exc:
            return {"error": str(exc)}, 422

    if path.startswith(COMMAND_CENTER_PREFIX):
        if role not in ("organizer", "partner", "sales"):
            return {"error": "forbidden"}, 403
        organization_id = unquote(path[len(COMMAND_CENTER_PREFIX):]).strip()[:100]
        if not organization_id:
            return {"error": "organization_id_required"}, 422
        try:
            return institutional_command_center.snapshot(c, organization_id), 200
        except ValueError as exc:
            return {"error": str(exc)}, 404 if str(exc) == "organization_not_found" else 422

    if path not in ROUTES:
        return None
    if role not in ("organizer", "partner", "sales"):
        return {"error": "forbidden"}, 403

    projections = {
        "/api/capital-allocation-optimizer": capital_optimizer.snapshot,
        "/api/capital-allocation-plan": capital_plan.snapshot,
        "/api/capital-plan-execution": capital_execution.snapshot,
        "/api/intervention-engine": intervention_engine.snapshot,
        "/api/recovery-reforecast": recovery_reforecast.snapshot,
        "/api/reallocation-authority": reallocation_authority.snapshot,
        "/api/portfolio-capital-control": portfolio_control.snapshot,
        "/api/deal-room": deal_room.snapshot,
        "/api/contract-builder": contract_builder.snapshot,
        "/api/investment-proof-system": investment_proof.snapshot,
    }
    return projections[path](c), 200
