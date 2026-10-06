from app import capital_optimizer, contract_builder, deal_room, investment_proof, portfolio_control


ROUTES = {
    "/api/capital-allocation-optimizer",
    "/api/portfolio-capital-control",
    "/api/deal-room",
    "/api/contract-builder",
    "/api/investment-proof-system",
}


def read(c, path, role):
    if path not in ROUTES:
        return None
    if role not in ("organizer", "partner", "sales"):
        return {"error": "forbidden"}, 403

    projections = {
        "/api/capital-allocation-optimizer": capital_optimizer.snapshot,
        "/api/portfolio-capital-control": portfolio_control.snapshot,
        "/api/deal-room": deal_room.snapshot,
        "/api/contract-builder": contract_builder.snapshot,
        "/api/investment-proof-system": investment_proof.snapshot,
    }
    return projections[path](c), 200
