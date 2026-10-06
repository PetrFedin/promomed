from app import portfolio_control


SCENARIO_ASSUMPTIONS = [
    {
        "id": "security",
        "title": "Allocate 10m to Security / Production",
        "allocation_rub": 10_000_000,
        "capital_dependency": "direct",
        "target_milestone": "security_acceptance",
        "nominal_unlock_rub": 10_000_000,
        "success_confidence_pct": 80,
        "capital_attribution_pct": 100,
        "days_to_decision": 3,
        "overdue_resolved": 2,
        "evidence_confidence_delta_pp": 7.0,
        "risk_reduction_rub": 10_000_000,
        "dependency": "Approved production security checklist / hosting / continuity acceptance.",
        "owner": "IT / Security",
        "alternative": "No cheaper non-capital remediation is assumed for the demo scenario.",
    },
    {
        "id": "operations",
        "title": "Allocate 10m to Operations",
        "allocation_rub": 10_000_000,
        "capital_dependency": "not_required",
        "target_milestone": "pilot_delivery",
        "nominal_unlock_rub": 12_500_000,
        "success_confidence_pct": 95,
        "capital_attribution_pct": 0,
        "days_to_decision": 3,
        "overdue_resolved": 0,
        "evidence_confidence_delta_pp": 5.0,
        "risk_reduction_rub": 12_500_000,
        "dependency": "Missing partner delivery acceptance in the live Pilot Deal Room.",
        "owner": "Commercial Director",
        "alternative": "Close the missing evidence/acceptance without incremental capital.",
    },
    {
        "id": "governance",
        "title": "Allocate 10m to Governance / Scale",
        "allocation_rub": 10_000_000,
        "capital_dependency": "partial",
        "target_milestone": "governed_scale",
        "nominal_unlock_rub": 15_000_000,
        "success_confidence_pct": 55,
        "capital_attribution_pct": 60,
        "days_to_decision": 30,
        "overdue_resolved": 1,
        "evidence_confidence_delta_pp": 10.0,
        "risk_reduction_rub": 15_000_000,
        "dependency": "Medical/editorial authority, RACI and board scale acceptance.",
        "owner": "Medical / Legal / Executive Sponsor",
        "alternative": "Funding can accelerate governance work, but cannot substitute for approval authority.",
    },
]


WEIGHTS = {
    "risk_adjusted_unlock": 0.40,
    "speed": 0.25,
    "evidence_confidence": 0.20,
    "overdue_resolution": 0.15,
}


def _risk_adjusted_unlock(s):
    return round(
        s["nominal_unlock_rub"]
        * s["success_confidence_pct"] / 100.0
        * s["capital_attribution_pct"] / 100.0
    )


def _score(rows):
    max_unlock = max([x["risk_adjusted_unlock_rub"] for x in rows] + [1])
    max_delta = max([x["evidence_confidence_delta_pp"] for x in rows] + [1])
    max_overdue = max([x["overdue_resolved"] for x in rows] + [1])
    for x in rows:
        unlock_score = x["risk_adjusted_unlock_rub"] / max_unlock
        speed_score = max(0.0, min(1.0, 1.0 - (x["days_to_decision"] - 1) / 30.0))
        confidence_score = x["evidence_confidence_delta_pp"] / max_delta
        overdue_score = x["overdue_resolved"] / max_overdue
        raw = (
            unlock_score * WEIGHTS["risk_adjusted_unlock"]
            + speed_score * WEIGHTS["speed"]
            + confidence_score * WEIGHTS["evidence_confidence"]
            + overdue_score * WEIGHTS["overdue_resolution"]
        )
        x["decision_score"] = round(raw * 100.0, 1)
    return rows


def snapshot(c):
    portfolio = portfolio_control.snapshot(c)
    current = portfolio["totals"]
    rows = []
    for source in SCENARIO_ASSUMPTIONS:
        s = dict(source)
        s["risk_adjusted_unlock_rub"] = _risk_adjusted_unlock(s)
        s["unlock_per_allocated_ruble"] = round(
            s["risk_adjusted_unlock_rub"] / s["allocation_rub"], 3
        ) if s["allocation_rub"] else None

        projected = {
            "paid": current["paid"],
            "eligible": current["eligible"],
            "blocked": current["blocked"],
            "at_risk": current["at_risk"],
        }
        if s["id"] == "security":
            moved = min(s["nominal_unlock_rub"], projected["blocked"])
            projected["blocked"] -= moved
            projected["eligible"] += moved
        elif s["id"] == "operations":
            moved = min(s["nominal_unlock_rub"], projected["at_risk"])
            projected["at_risk"] -= moved
            projected["eligible"] += moved
        elif s["id"] == "governance":
            moved = min(s["nominal_unlock_rub"], projected["blocked"])
            projected["blocked"] -= moved
            projected["eligible"] += moved

        s["projected_portfolio_if_successful"] = {
            **projected,
            "committed": sum(projected.values()),
            "evidence_confidence": round(
                min(100.0, current["evidence_confidence"] + s["evidence_confidence_delta_pp"]),
                1,
            ),
            "overdue_obligations": max(
                0, current["overdue_obligations"] - s["overdue_resolved"]
            ),
        }
        if s["capital_dependency"] == "not_required":
            s["capital_recommendation"] = "DO_NOT_ALLOCATE_INCREMENTAL_CAPITAL"
            s["management_action"] = s["alternative"]
        elif s["capital_dependency"] == "partial":
            s["capital_recommendation"] = "FUND_ONLY_WITH_APPROVAL_WORKPLAN"
            s["management_action"] = "Tie capital release to named governance deliverables and approval SLA."
        else:
            s["capital_recommendation"] = "CAPITAL_CANDIDATE"
            s["management_action"] = "Fund only against security acceptance deliverables and exact evidence gates."
        rows.append(s)

    rows = _score(rows)
    ranked_capital = sorted(
        [x for x in rows if x["capital_dependency"] != "not_required"],
        key=lambda x: x["decision_score"],
        reverse=True,
    )
    best = ranked_capital[0]
    operations = next(x for x in rows if x["id"] == "operations")

    recommendation = {
        "primary": best["id"],
        "title": best["title"],
        "decision": "ALLOCATE_CONDITIONALLY",
        "allocation_rub": best["allocation_rub"],
        "why": (
            f'{best["title"]} has the strongest demo decision score among capital-dependent options '
            f'({best["decision_score"]}/100) with {best["days_to_decision"]}-day target timing.'
        ),
        "before_spending": {
            "action": operations["management_action"],
            "capital_required_rub": 0,
            "potential_unlock_rub": operations["nominal_unlock_rub"],
            "reason": "The current Operations blocker is evidence/acceptance dependent, not cash dependent.",
        },
        "sequence": [
            "1 · Close Operations partner acceptance without new capital.",
            "2 · Allocate the next 10m conditionally to Security / Production acceptance.",
            "3 · Release Governance funding only against a named approval workplan and SLA.",
        ],
    }

    frontier = sorted(
        rows,
        key=lambda x: (
            0 if x["capital_dependency"] == "not_required" else 1,
            -x["decision_score"],
        ),
    )

    return {
        "version": "capital-allocation-optimizer-v1",
        "portfolio_now": current,
        "scenario_budget_rub": 10_000_000,
        "scenarios": rows,
        "frontier": frontier,
        "recommendation": recommendation,
        "weights": WEIGHTS,
        "method": {
            "score_formula": (
                "40% risk-adjusted capital unlock + 25% speed + "
                "20% evidence-confidence uplift + 15% overdue-resolution"
            ),
            "risk_adjusted_unlock_formula": (
                "nominal unlock × success confidence × capital attribution"
            ),
            "capital_attribution_rule": (
                "A blocker that can be removed without incremental capital receives 0% capital attribution."
            ),
        },
        "truth_boundary": {
            "demo_optimizer": True,
            "approved_capital_plan": False,
            "forecast": False,
            "scenario_assumptions_are_actuals": False,
            "note": (
                "Scenario values are explicit demo assumptions for decision mechanics. "
                "A real recommendation requires approved budgets, delivery estimates, owners, dependencies and probability inputs."
            ),
        },
    }
