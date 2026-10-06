from app import capital_optimizer, portfolio_control


SECURITY_PACKAGES = [
    {
        "id": "s1",
        "order": 1,
        "title": "Security baseline & control register",
        "allocation_rub": 1_500_000,
        "owner": "IT / Security + Product",
        "deadline": "T+3 days",
        "deliverables": [
            "Approved security control register",
            "Data-flow / trust-boundary map",
            "Named risk owners and remediation backlog",
        ],
        "evidence_gate": "Security owner accepts control register and architecture evidence.",
        "stop_rule": "STOP if critical data/security scope remains undefined.",
        "confidence_uplift_pp": 2.0,
        "overdue_resolved": 1,
    },
    {
        "id": "s2",
        "order": 2,
        "title": "Durable production & recovery proof",
        "allocation_rub": 3_000_000,
        "owner": "Platform Engineering",
        "deadline": "T+5 days",
        "deliverables": [
            "Isolated PostgreSQL production binding",
            "/ready production_ready=true",
            "Authenticated production smoke",
            "Backup/restore proof",
        ],
        "evidence_gate": "Exact production evidence pack accepted by Product + IT/Security.",
        "stop_rule": "STOP if durable persistence or recovery proof fails.",
        "confidence_uplift_pp": 2.0,
        "overdue_resolved": 0,
    },
    {
        "id": "s3",
        "order": 3,
        "title": "Identity, secrets, observability hardening",
        "allocation_rub": 2_500_000,
        "owner": "Platform Engineering + IT / Security",
        "deadline": "T+7 days",
        "deliverables": [
            "Production identity / access review",
            "Secrets and rotation evidence",
            "Operational logging / alerting proof",
            "Incident response runbook",
        ],
        "evidence_gate": "Security checklist has no unresolved critical control gaps.",
        "stop_rule": "ITERATE if medium gaps remain; STOP for unresolved critical gaps.",
        "confidence_uplift_pp": 1.0,
        "overdue_resolved": 0,
    },
    {
        "id": "s4",
        "order": 4,
        "title": "Security acceptance & remediation reserve",
        "allocation_rub": 3_000_000,
        "owner": "IT / Security + Executive Sponsor",
        "deadline": "T+10 days",
        "deliverables": [
            "Final remediation closure",
            "Production security acceptance pack",
            "Signed decision / exception register",
        ],
        "evidence_gate": "Security acceptance recorded with named approver and accepted evidence.",
        "stop_rule": "Do not unlock the 10m Security milestone without final acceptance.",
        "confidence_uplift_pp": 2.0,
        "overdue_resolved": 1,
    },
]


def _apply_free_operations_step(current):
    out = dict(current)
    moved = min(12_500_000, int(out["at_risk"]))
    out["at_risk"] -= moved
    out["eligible"] += moved
    out["evidence_confidence"] = round(min(100.0, float(out["evidence_confidence"]) + 5.0), 1)
    return out, moved


def _decision(state):
    committed = int(state["committed"])
    blocked_share = int(state["blocked"]) / committed if committed else 0
    overdue = int(state["overdue_obligations"])
    confidence = float(state["evidence_confidence"])
    if overdue >= 3 or blocked_share >= 0.40 or confidence < 70:
        return "ITERATE"
    if int(state["blocked"]) > 0 or int(state["at_risk"]) > 0 or overdue > 0:
        return "HOLD"
    return "GO"


def snapshot(c):
    optimizer = capital_optimizer.snapshot(c)
    portfolio = portfolio_control.snapshot(c)
    now = dict(portfolio["totals"])
    now["decision"] = portfolio["programme"]["decision"]

    trajectory = [
        {
            "step": "CURRENT",
            "title": "Current 75m portfolio",
            "capital_used_rub": 0,
            "state": dict(now),
            "effect": "Baseline before remediation.",
        }
    ]

    after_free, free_unlock = _apply_free_operations_step(now)
    after_free["overdue_obligations"] = now["overdue_obligations"]
    after_free["decision"] = _decision(after_free)
    trajectory.append({
        "step": "STEP 0",
        "title": "Close Operations partner acceptance",
        "capital_used_rub": 0,
        "state": dict(after_free),
        "effect": f"Moves {free_unlock} RUB from at-risk to eligible without incremental capital.",
    })

    running = dict(after_free)
    cumulative = 0
    security_block_remaining = 10_000_000
    packages = []
    for source in SECURITY_PACKAGES:
        p = dict(source)
        cumulative += int(p["allocation_rub"])
        running["evidence_confidence"] = round(
            min(100.0, float(running["evidence_confidence"]) + float(p["confidence_uplift_pp"])),
            1,
        )
        running["overdue_obligations"] = max(
            0, int(running["overdue_obligations"]) - int(p["overdue_resolved"])
        )
        unlock = 0
        if p["id"] == "s4":
            unlock = min(security_block_remaining, int(running["blocked"]))
            running["blocked"] -= unlock
            running["eligible"] += unlock
            security_block_remaining -= unlock
        running["decision"] = _decision(running)
        p["cumulative_allocation_rub"] = cumulative
        p["unlock_rub_at_step"] = unlock
        p["projected_portfolio"] = dict(running)
        p["commercial_state"] = "illustrative_security_plan_not_quote"
        packages.append(p)
        trajectory.append({
            "step": p["id"].upper(),
            "title": p["title"],
            "capital_used_rub": cumulative,
            "state": dict(running),
            "effect": (
                f"Final acceptance moves {unlock} RUB from blocked to eligible."
                if unlock else
                "Builds evidence and reduces control risk; capital remains blocked until final Security acceptance."
            ),
        })

    total = sum(int(x["allocation_rub"]) for x in packages)
    final = trajectory[-1]["state"]
    return {
        "version": "capital-allocation-plan-v1",
        "selected_scenario": "security",
        "scenario_source": optimizer["recommendation"],
        "plan": {
            "title": "Security / Production · Conditional 10m Capital Allocation Plan",
            "allocation_rub": total,
            "capital_release_mode": "milestone_gated",
            "commercial_state": "illustrative_plan_not_quote",
            "precondition": {
                "title": "STEP 0 · Operations remediation first",
                "capital_required_rub": 0,
                "owner": "Commercial Director",
                "deadline": "T+3 days",
                "deliverable": "Signed partner delivery acceptance registered in Evidence Registry.",
                "evidence_gate": "Pilot Deal Room partner_delivery == accepted.",
                "potential_unlock_rub": 12_500_000,
            },
            "packages": packages,
        },
        "trajectory": trajectory,
        "final_projection": {
            "paid_rub": final["paid"],
            "eligible_rub": final["eligible"],
            "blocked_rub": final["blocked"],
            "at_risk_rub": final["at_risk"],
            "evidence_confidence": final["evidence_confidence"],
            "overdue_obligations": final["overdue_obligations"],
            "programme_decision": final["decision"],
        },
        "release_rules": [
            "No Security package unlocks the 10m blocked milestone before S4 final acceptance.",
            "Unused/remediation reserve is not automatically spent; it remains subject to accepted evidence.",
            "If a STOP condition is triggered, subsequent package release is paused.",
            "Operations remediation is executed before new Security capital because its blocker is non-capital.",
        ],
        "truth_boundary": {
            "demo_plan": True,
            "approved_budget": False,
            "commercial_quote": False,
            "forecast_commitment": False,
            "automatic_payment": False,
            "note": "Amounts and deadlines are an illustrative execution-control template. Real use requires approved scope, estimates, procurement, owners and contractual evidence gates.",
        },
    }
