import time

from app import capital_execution


RISK_WEIGHTS = {
    "schedule": 0.30,
    "budget": 0.25,
    "evidence": 0.30,
    "dependency": 0.15,
}


def _rows(c):
    try:
        return [dict(r) for r in c.execute(
            "SELECT id,scenario_id,package_id,intervention_type,status,owner,reason,freeze_new_commitments,reallocation_candidate_rub,capital_at_risk_rub,downstream_value_at_risk_rub,note,created_by,created_at,resolved_by,resolved_at,demo_only "
            "FROM capital_interventions ORDER BY created_at,id"
        )]
    except Exception:
        return []


def _risk_score(package):
    planned = float(package["planned_rub"] or 0)
    committed = float(package["committed_rub"] or 0)
    actual = float(package["actual_rub"] or 0)

    schedule_risk = 100.0 if package["status"] in ("blocked", "not_started") else 55.0 if package["status"] == "in_progress" else 0.0
    budget_ratio = (actual / planned) if planned else 0.0
    budget_risk = 100.0 if budget_ratio > 1.0 else max(0.0, (budget_ratio - 0.70) / 0.30 * 100.0)
    evidence_risk = 0.0 if package["evidence_status"] == "accepted_demo" else 60.0 if package["evidence_status"] == "partial" else 100.0
    dependency_risk = 100.0 if package["package_id"] == "s4" and package["status"] == "blocked" else 40.0 if package["package_id"] in ("s2","s3") else 0.0

    score = (
        schedule_risk * RISK_WEIGHTS["schedule"]
        + budget_risk * RISK_WEIGHTS["budget"]
        + evidence_risk * RISK_WEIGHTS["evidence"]
        + dependency_risk * RISK_WEIGHTS["dependency"]
    )
    return round(min(100.0, score), 1)


def _classify(package):
    score = _risk_score(package)
    if package["status"] == "blocked":
        severity = "critical"
    elif score >= 65:
        severity = "high"
    elif score >= 35:
        severity = "medium"
    else:
        severity = "low"

    capital_at_risk = max(0, int(package["committed_rub"]) - int(package["actual_rub"]))
    downstream = 10_000_000 if package["package_id"] in ("s2","s3","s4") and package["evidence_status"] != "accepted_demo" else 0

    if package["package_id"] == "s2" and package["evidence_status"] != "accepted_demo":
        action = "RECOVERY_SPRINT"
        recommendation = "Freeze new S3/S4 commitments; finish durable production, authenticated smoke and restore evidence."
        freeze = True
        reallocation = 0
    elif package["package_id"] == "s3" and package["status"] == "not_started":
        action = "HOLD_COMMITMENT"
        recommendation = "Do not release remaining S3 commitment until S2 evidence is accepted."
        freeze = True
        reallocation = max(0, int(package["planned_rub"]) - int(package["committed_rub"]))
    elif package["package_id"] == "s4" and package["status"] == "blocked":
        action = "HOLD_FINAL_GATE"
        recommendation = "Keep S4 uncommitted; final Security acceptance remains blocked by prerequisite evidence."
        freeze = True
        reallocation = int(package["planned_rub"])
    else:
        action = "CONTINUE_CONTROLLED"
        recommendation = "Continue within current commitment; keep evidence gate and variance monitoring active."
        freeze = False
        reallocation = 0

    return {
        "package_id": package["package_id"],
        "title": package["title"],
        "owner": package["owner"],
        "risk_score": score,
        "severity": severity,
        "capital_at_risk_rub": capital_at_risk,
        "downstream_value_at_risk_rub": downstream,
        "intervention_type": action,
        "recommendation": recommendation,
        "freeze_new_commitments": freeze,
        "reallocation_candidate_rub": reallocation,
    }


def create_demo_intervention(c, package_id, actor):
    execution = capital_execution.snapshot(c)
    package = next((x for x in execution["packages"] if x["package_id"] == package_id), None)
    if not package:
        raise ValueError("unknown_package")
    intervention = _classify(package)
    now = int(time.time())
    rec_id = f"security:{package_id}:{intervention['intervention_type']}"
    c.execute(
        "INSERT INTO capital_interventions(id,scenario_id,package_id,intervention_type,status,owner,reason,freeze_new_commitments,reallocation_candidate_rub,capital_at_risk_rub,downstream_value_at_risk_rub,note,created_by,created_at,demo_only) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1) "
        "ON CONFLICT(scenario_id,package_id,intervention_type,status) DO NOTHING",
        (
            rec_id,
            "security",
            package_id,
            intervention["intervention_type"],
            "open_demo",
            intervention["owner"],
            intervention["recommendation"],
            1 if intervention["freeze_new_commitments"] else 0,
            intervention["reallocation_candidate_rub"],
            intervention["capital_at_risk_rub"],
            intervention["downstream_value_at_risk_rub"],
            "Presentation-only intervention record.",
            actor,
            now,
        ),
    )


def reset_demo(c):
    c.execute("DELETE FROM capital_interventions WHERE demo_only=1")


def snapshot(c):
    execution = capital_execution.snapshot(c)
    diagnostics = [_classify(x) for x in execution["packages"]]

    open_rows = [x for x in _rows(c) if x["scenario_id"] == "security" and x["status"] == "open_demo"]
    open_by_package = {x["package_id"]: x for x in open_rows}

    for d in diagnostics:
        d["intervention_record"] = open_by_package.get(d["package_id"])

    total_capital_at_risk = sum(x["capital_at_risk_rub"] for x in diagnostics if x["severity"] in ("high","critical"))
    downstream_value_at_risk = max((x["downstream_value_at_risk_rub"] for x in diagnostics), default=0)
    reallocation_candidates = sum(x["reallocation_candidate_rub"] for x in diagnostics)
    freeze_recommended = any(x["freeze_new_commitments"] for x in diagnostics)

    intervention_priority = {
        "RECOVERY_SPRINT": 4,
        "HOLD_COMMITMENT": 3,
        "HOLD_FINAL_GATE": 2,
        "CONTINUE_CONTROLLED": 1,
    }
    primary = sorted(
        diagnostics,
        key=lambda x: (
            intervention_priority.get(x["intervention_type"], 0),
            x["risk_score"],
            x["downstream_value_at_risk_rub"],
            x["capital_at_risk_rub"],
        ),
        reverse=True,
    )[0]

    return {
        "version": "capital-intervention-engine-v1",
        "summary": {
            "primary_package": primary["package_id"],
            "primary_intervention": primary["intervention_type"],
            "freeze_next_commitment": freeze_recommended,
            "capital_at_risk_rub": total_capital_at_risk,
            "downstream_value_at_risk_rub": downstream_value_at_risk,
            "reallocation_candidate_rub": reallocation_candidates,
            "programme_action": "ITERATE",
            "reason": primary["recommendation"],
        },
        "diagnostics": diagnostics,
        "open_interventions": open_rows,
        "control_logic": {
            "risk_score_formula": "30% schedule + 25% budget + 30% evidence + 15% dependency risk",
            "freeze_rule": "Freeze new downstream commitments when prerequisite evidence is incomplete or a package is blocked.",
            "reallocation_rule": "Only uncommitted package capacity may be proposed as a reallocation candidate; committed-but-unspent capital is not automatically free.",
            "automation_boundary": "The engine recommends interventions; it does not move money, amend contracts or authorize payments.",
        },
        "truth_boundary": {
            "demo_engine": True,
            "actual_forecast": False,
            "automatic_reallocation": False,
            "automatic_commitment_freeze": False,
            "actual_payment_authority": False,
        },
    }
