from app import capital_execution, intervention_engine, portfolio_control


def _portfolio_state(portfolio):
    t = portfolio["totals"]
    return {
        "paid_rub": int(t["paid"]),
        "eligible_rub": int(t["eligible"]),
        "blocked_rub": int(t["blocked"]),
        "at_risk_rub": int(t["at_risk"]),
        "evidence_confidence": float(t["evidence_confidence"]),
        "overdue_obligations": int(t["overdue_obligations"]),
    }


def _recovery_s2(execution, portfolio):
    packages = {x["package_id"]: x for x in execution["packages"]}
    s2 = packages["s2"]
    remaining_commitment = max(0, int(s2["committed_rub"]) - int(s2["actual_rub"]))
    assumed_additional_spend = min(1_000_000, remaining_commitment)
    projected_actual = int(s2["actual_rub"]) + assumed_additional_spend

    state = _portfolio_state(portfolio)
    state["evidence_confidence"] = round(min(100.0, state["evidence_confidence"] + 2.0), 1)

    return {
        "id": "A_RECOVER_S2",
        "title": "A · Recover S2 and continue Security path",
        "recommended": True,
        "days_to_decision": 3,
        "additional_actual_spend_rub": assumed_additional_spend,
        "new_commitment_rub": 0,
        "evidence_expected": [
            "Isolated PostgreSQL production binding",
            "/ready production_ready=true",
            "Authenticated production smoke",
            "Backup/restore proof",
        ],
        "capital_freeze": ["S3 remaining commitment", "S4 commitment"],
        "reallocation_candidate_rub": 0,
        "next_unlock_rub": 10_000_000,
        "next_unlock_condition": "S2 accepted, then S3 accepted, then S4 final Security acceptance.",
        "projected_execution": {
            "s2_actual_rub": projected_actual,
            "s2_committed_rub": int(s2["committed_rub"]),
            "s2_evidence_status": "accepted_if_recovery_succeeds",
        },
        "projected_portfolio": state,
        "expected_payback_status": "NOT_CALCULATED_UNTIL_FINANCE_ACCEPTS_VALUE",
        "decision": "RECOVER_FIRST",
        "reason": "S2 is the earliest actionable root cause and still has committed capacity available; no new capital is required for the recovery sprint in this demo model.",
    }


def _reallocate_if_s2_fails(execution, portfolio, engine):
    packages = {x["package_id"]: x for x in execution["packages"]}
    s3 = packages["s3"]
    s4 = packages["s4"]

    s3_uncommitted = max(0, int(s3["planned_rub"]) - int(s3["committed_rub"]))
    s4_uncommitted = max(0, int(s4["planned_rub"]) - int(s4["committed_rub"]))
    reallocation_candidate = s3_uncommitted + s4_uncommitted

    state = _portfolio_state(portfolio)
    state["blocked_rub"] = int(state["blocked_rub"])
    state["at_risk_rub"] = int(state["at_risk_rub"])
    state["evidence_confidence"] = round(max(0.0, state["evidence_confidence"] - 1.0), 1)

    proposal = [
        {
            "target": "Finance reconciliation acceleration",
            "amount_rub": min(2_000_000, reallocation_candidate),
            "purpose": "Close baseline/actual reconciliation and evidence pack faster.",
            "unlock_dependency": "Finance acceptance still required; funding alone does not create accepted value.",
        },
        {
            "target": "Medical / Legal governance workplan",
            "amount_rub": max(0, reallocation_candidate - min(2_000_000, reallocation_candidate)),
            "purpose": "Fund named review capacity, policy work and approval preparation.",
            "unlock_dependency": "Approval authority remains independent; funding does not guarantee approval.",
        },
    ]

    return {
        "id": "B_REALLOCATE_AFTER_S2_FAILURE",
        "title": "B · Freeze Security downstream and prepare reallocation",
        "recommended": False,
        "days_to_decision": 2,
        "additional_actual_spend_rub": 0,
        "new_commitment_rub": 0,
        "evidence_expected": [
            "Documented S2 recovery failure / stop decision",
            "Commitment freeze record",
            "Finance confirmation of uncommitted capacity",
            "Approved reallocation proposal",
        ],
        "capital_freeze": ["S3 new commitment", "S4 all commitment"],
        "reallocation_candidate_rub": reallocation_candidate,
        "reallocation_proposal": proposal,
        "next_unlock_rub": 0,
        "next_unlock_condition": "No Security unlock until a new approved remediation path exists.",
        "projected_portfolio": state,
        "expected_payback_status": "NOT_CALCULATED_UNTIL_FINANCE_ACCEPTS_VALUE",
        "decision": "FREEZE_AND_REVIEW",
        "reason": "Only genuinely uncommitted S3/S4 capacity is proposed for reallocation. Committed-but-unspent S2 capital remains ring-fenced until an explicit release decision.",
        "intervention_reference": engine["summary"]["primary_intervention"],
    }


def snapshot(c):
    execution = capital_execution.snapshot(c)
    portfolio = portfolio_control.snapshot(c)
    engine = intervention_engine.snapshot(c)

    a = _recovery_s2(execution, portfolio)
    b = _reallocate_if_s2_fails(execution, portfolio, engine)

    return {
        "version": "capital-recovery-reforecast-v1",
        "current": {
            "execution_actual_rub": execution["totals"]["actual_rub"],
            "execution_committed_rub": execution["totals"]["committed_rub"],
            "execution_uncommitted_rub": execution["totals"]["uncommitted_rub"],
            "programme_decision": portfolio["programme"]["decision"],
            "primary_intervention": engine["summary"]["primary_intervention"],
        },
        "scenarios": [a, b],
        "recommendation": {
            "primary": a["id"],
            "secondary": b["id"],
            "decision": "RECOVER_S2_BEFORE_REALLOCATION",
            "why": "Recovery uses already committed capacity and attacks the earliest actionable root cause. Reallocation is a fallback only after an explicit stop decision.",
        },
        "approval_simulation": {
            "recovery_requires": [
                "Product / Engineering acceptance of recovery scope",
                "IT / Security acceptance of production evidence",
                "Executive acknowledgement that downstream commitments remain frozen until evidence passes",
            ],
            "reallocation_requires": [
                "Documented S2 stop decision",
                "Finance confirmation of uncommitted capacity",
                "Business owner proposal",
                "Investment Committee approval",
            ],
            "automatic_actions": False,
        },
        "truth_boundary": {
            "demo_reforecast": True,
            "actual_forecast": False,
            "approved_reallocation": False,
            "expected_payback_validated": False,
            "automatic_money_movement": False,
            "note": "Scenario timing and spend are explicit demo assumptions. Payback is not forecast because finance-accepted value is not yet available.",
        },
    }
