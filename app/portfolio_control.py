from app import deal_room


DEMO_PORTFOLIO = {
    "programme_id": "sostoyanie-controlled-75",
    "programme_name": "СОСТОЯНИЕ · Controlled 75m Programme",
    "committed_rub": 75_000_000,
    "commercial_state": "demo_control_portfolio_not_actual_budget",
    "workstreams": [
        {
            "id": "platform_core",
            "title": "Platform Core & Security",
            "owner": "Product / Engineering + IT / Security",
            "milestones": [
                {
                    "id": "core_foundation",
                    "title": "Core platform foundation",
                    "amount_rub": 10_000_000,
                    "state": "paid",
                    "evidence_confidence": 100,
                    "reason": "Demo portfolio treats architecture/release foundation as a completed reference milestone.",
                },
                {
                    "id": "security_acceptance",
                    "title": "Security / production acceptance",
                    "amount_rub": 10_000_000,
                    "state": "blocked",
                    "evidence_confidence": 65,
                    "reason": "Release waits for production security acceptance and durable Phase 0 evidence.",
                },
            ],
        },
        {
            "id": "pilot_operations",
            "title": "Pilot Operations",
            "owner": "Event Operations + Product",
            "milestones": [
                {
                    "id": "launch_readiness",
                    "title": "Pilot launch readiness",
                    "amount_rub": 10_000_000,
                    "state": "eligible",
                    "evidence_confidence": 92,
                    "reason": "Demo readiness evidence is available; real payment still requires contractual acceptance.",
                },
                {
                    "id": "pilot_delivery",
                    "title": "Pilot delivery acceptance",
                    "amount_rub": 12_500_000,
                    "state": "deal_room",
                    "evidence_confidence": None,
                    "reason": "State is derived from the live Pilot Deal Room.",
                },
            ],
        },
        {
            "id": "commercial_value",
            "title": "Commercial & Finance Value",
            "owner": "Commercial + Finance",
            "milestones": [
                {
                    "id": "partner_activation",
                    "title": "Partner inventory activation",
                    "amount_rub": 10_000_000,
                    "state": "eligible",
                    "evidence_confidence": 88,
                    "reason": "Demo contract/delivery evidence is sufficient for portfolio illustration only.",
                },
                {
                    "id": "finance_acceptance",
                    "title": "Finance value acceptance",
                    "amount_rub": 7_500_000,
                    "state": "blocked",
                    "evidence_confidence": 40,
                    "reason": "Paid-pilot actuals and Finance reconciliation are not yet available.",
                },
            ],
        },
        {
            "id": "governance_scale",
            "title": "Governance & Scale",
            "owner": "Medical / Legal / Executive Sponsor",
            "milestones": [
                {
                    "id": "governed_scale",
                    "title": "Medical governance + scale decision",
                    "amount_rub": 15_000_000,
                    "state": "blocked",
                    "evidence_confidence": 35,
                    "reason": "PROMO-INT-02+ and board scale acceptance remain gated.",
                },
            ],
        },
    ],
}


OVERDUE_OBLIGATIONS = [
    {
        "id": "security_dpa",
        "title": "Production security acceptance pack",
        "owner": "IT / Security",
        "days_overdue": 2,
        "blocks_milestone": "security_acceptance",
        "required_evidence": "Approved production security checklist / hosting / continuity acceptance.",
    },
    {
        "id": "privacy_schedule",
        "title": "Data-processing responsibility schedule",
        "owner": "Legal / Privacy",
        "days_overdue": 1,
        "blocks_milestone": "security_acceptance",
        "required_evidence": "Approved processing / controller-processor responsibility schedule.",
    },
    {
        "id": "medical_raci",
        "title": "Medical / editorial approval RACI",
        "owner": "Medical / Legal / Editorial",
        "days_overdue": 4,
        "blocks_milestone": "governed_scale",
        "required_evidence": "Named approval authority, SLA and escalation matrix.",
    },
]


def _portfolio_rows(deal):
    rows = []
    for ws in DEMO_PORTFOLIO["workstreams"]:
        for m in ws["milestones"]:
            row = dict(m)
            row["workstream_id"] = ws["id"]
            row["workstream"] = ws["title"]
            row["owner"] = ws["owner"]
            if row["state"] == "deal_room":
                eligible = bool(deal["readiness"]["demo_payment_eligible"])
                row["state"] = "eligible" if eligible else "at_risk"
                accepted = float(deal["readiness"]["accepted_count"])
                required = float(deal["readiness"]["required_count"] or 1)
                base = accepted / required * 100.0
                issue_penalty = min(30.0, float(deal["readiness"]["open_issue_count"]) * 10.0)
                row["evidence_confidence"] = round(max(0.0, base - issue_penalty), 1)
                row["reason"] = deal["readiness"]["reason"]
                row["source"] = "pilot_deal_room"
            else:
                row["source"] = "portfolio_demo_template"
            rows.append(row)
    return rows


def _totals(rows):
    states = {"paid": 0, "eligible": 0, "blocked": 0, "at_risk": 0}
    for row in rows:
        states[row["state"]] += int(row["amount_rub"])
    states["committed"] = sum(states.values())
    return states


def _weighted_confidence(rows):
    committed = sum(int(x["amount_rub"]) for x in rows) or 1
    weighted = sum(float(x["evidence_confidence"]) * int(x["amount_rub"]) for x in rows)
    return round(weighted / committed, 1)


def snapshot(c):
    deal = deal_room.snapshot(c)
    rows = _portfolio_rows(deal)
    totals = _totals(rows)
    confidence = _weighted_confidence(rows)
    blocked_share = totals["blocked"] / totals["committed"] if totals["committed"] else 0.0
    overdue = list(OVERDUE_OBLIGATIONS)

    if len(overdue) >= 3 or blocked_share >= 0.40 or confidence < 70:
        programme_decision = "ITERATE"
        decision_reason = "Blocked capital / overdue obligations / evidence confidence require remediation before scale."
    elif totals["at_risk"] > 0:
        programme_decision = "HOLD"
        decision_reason = "At-risk milestones remain unresolved."
    else:
        programme_decision = "GO"
        decision_reason = "No portfolio-level stop condition is active in the demo control model."

    forecast = [
        {
            "order": 1,
            "amount_rub": totals["eligible"],
            "timing": "NOW · subject to Finance/contract acceptance",
            "dependency": "Eligible milestone close packs",
            "confidence": 90,
        },
        {
            "order": 2,
            "amount_rub": 10_000_000,
            "timing": "T+3 days target",
            "dependency": "Security acceptance",
            "confidence": 65,
        },
        {
            "order": 3,
            "amount_rub": totals["at_risk"],
            "timing": "T+3 days target",
            "dependency": "Pilot Deal Room blocker remediation",
            "confidence": round(next((x["evidence_confidence"] for x in rows if x["id"] == "pilot_delivery"), 0), 1),
        },
        {
            "order": 4,
            "amount_rub": 7_500_000,
            "timing": "T+14 days target",
            "dependency": "Finance value reconciliation",
            "confidence": 40,
        },
        {
            "order": 5,
            "amount_rub": 15_000_000,
            "timing": "T+30 days target",
            "dependency": "Medical governance + board scale acceptance",
            "confidence": 35,
        },
    ]

    next_expected_release = {
        "amount_rub": 10_000_000,
        "dependency": "Security acceptance",
        "owner": "IT / Security",
        "target": "T+3 days",
        "evidence_required": "Approved production security checklist / hosting / continuity acceptance.",
        "payment_authorized": False,
    }

    workstreams = []
    for ws in DEMO_PORTFOLIO["workstreams"]:
        ms = [x for x in rows if x["workstream_id"] == ws["id"]]
        subtotal = _totals(ms)
        workstreams.append({
            "id": ws["id"],
            "title": ws["title"],
            "owner": ws["owner"],
            "committed_rub": subtotal["committed"],
            "paid_rub": subtotal["paid"],
            "eligible_rub": subtotal["eligible"],
            "blocked_rub": subtotal["blocked"],
            "at_risk_rub": subtotal["at_risk"],
            "evidence_confidence": _weighted_confidence(ms),
            "milestones": ms,
        })

    return {
        "version": "portfolio-capital-control-v1",
        "programme": {
            "id": DEMO_PORTFOLIO["programme_id"],
            "name": DEMO_PORTFOLIO["programme_name"],
            "commercial_state": DEMO_PORTFOLIO["commercial_state"],
            "decision": programme_decision,
            "decision_reason": decision_reason,
        },
        "totals": {
            **totals,
            "evidence_confidence": confidence,
            "blocked_share_pct": round(blocked_share * 100.0, 1),
            "overdue_obligations": len(overdue),
        },
        "workstreams": workstreams,
        "overdue_obligations": overdue,
        "forecast_cash_release": forecast,
        "next_expected_release": next_expected_release,
        "control_rules": {
            "decision_logic": [
                "ITERATE when overdue obligations >= 3, blocked capital >= 40% of committed, or evidence confidence < 70.",
                "HOLD when no ITERATE rule is active but at-risk capital remains.",
                "GO only when no portfolio-level stop condition is active.",
            ],
            "evidence_confidence_formula": "amount-weighted average of milestone evidence-confidence scores",
            "deal_room_link": "Pilot delivery milestone state/confidence is derived from live Pilot Deal Room readiness.",
        },
        "truth_boundary": {
            "demo_portfolio": True,
            "actual_budget": False,
            "actual_payment_authority": False,
            "forecast_is_commitment": False,
            "note": "All portfolio amounts and timing are a control-model demonstration until approved against a real contract, budget, evidence and authorized payment process.",
        },
    }
