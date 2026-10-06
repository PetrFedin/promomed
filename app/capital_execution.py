import time

from app import capital_plan


DEMO_EXECUTION = {
    "s1": {
        "status": "accepted_demo",
        "committed_rub": 1_500_000,
        "actual_rub": 1_420_000,
        "evidence_status": "accepted_demo",
        "evidence_ref": "demo://security-control-register",
        "unlocked_value_rub": 0,
        "note": "Control register accepted. Underspend remains uncommitted.",
    },
    "s2": {
        "status": "in_progress",
        "committed_rub": 3_000_000,
        "actual_rub": 1_850_000,
        "evidence_status": "partial",
        "evidence_ref": "demo://postgres-ready-partial",
        "unlocked_value_rub": 0,
        "note": "Production binding work in progress; restore proof not yet accepted.",
    },
    "s3": {
        "status": "not_started",
        "committed_rub": 1_000_000,
        "actual_rub": 0,
        "evidence_status": "awaiting",
        "evidence_ref": "",
        "unlocked_value_rub": 0,
        "note": "Initial capacity reserved; work not started.",
    },
    "s4": {
        "status": "blocked",
        "committed_rub": 0,
        "actual_rub": 0,
        "evidence_status": "awaiting",
        "evidence_ref": "",
        "unlocked_value_rub": 0,
        "note": "Final Security acceptance cannot start before S1-S3 gates are accepted.",
    },
}


def _rows(c):
    try:
        return [dict(r) for r in c.execute(
            "SELECT id,scenario_id,package_id,owner,status,planned_rub,committed_rub,actual_rub,evidence_status,evidence_ref,unlocked_value_rub,note,updated_by,updated_at,demo_only "
            "FROM capital_plan_execution ORDER BY package_id"
        )]
    except Exception:
        return []


def seed_demo(c, actor="system"):
    plan = capital_plan.snapshot(c)
    packages = {x["id"]: x for x in plan["plan"]["packages"]}
    now = int(time.time())
    for package_id, defaults in DEMO_EXECUTION.items():
        p = packages[package_id]
        rec_id = f"security:{package_id}"
        c.execute(
            "INSERT INTO capital_plan_execution(id,scenario_id,package_id,owner,status,planned_rub,committed_rub,actual_rub,evidence_status,evidence_ref,unlocked_value_rub,note,updated_by,updated_at,demo_only) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1) "
            "ON CONFLICT(scenario_id,package_id) DO NOTHING",
            (
                rec_id,
                "security",
                package_id,
                p["owner"],
                defaults["status"],
                p["allocation_rub"],
                defaults["committed_rub"],
                defaults["actual_rub"],
                defaults["evidence_status"],
                defaults["evidence_ref"],
                defaults["unlocked_value_rub"],
                defaults["note"],
                actor,
                now,
            ),
        )


def update_demo(c, package_id, actor, *, status=None, committed_rub=None, actual_rub=None, evidence_status=None, evidence_ref=None, note=None):
    seed_demo(c, actor)
    rows = {r["package_id"]: r for r in _rows(c) if r["scenario_id"] == "security"}
    if package_id not in rows:
        raise ValueError("unknown_package")
    current = rows[package_id]
    plan = capital_plan.snapshot(c)
    package = next(x for x in plan["plan"]["packages"] if x["id"] == package_id)
    new_status = status or current["status"]
    new_committed = int(current["committed_rub"] if committed_rub is None else committed_rub)
    new_actual = int(current["actual_rub"] if actual_rub is None else actual_rub)
    new_evidence_status = evidence_status or current["evidence_status"]
    new_evidence_ref = current["evidence_ref"] if evidence_ref is None else str(evidence_ref)
    new_note = current["note"] if note is None else str(note)

    if new_committed < 0 or new_actual < 0:
        raise ValueError("negative_spend")
    if new_committed > int(package["allocation_rub"]):
        raise ValueError("committed_exceeds_plan")
    if new_actual > new_committed:
        raise ValueError("actual_exceeds_committed")

    unlocked = 0
    if package_id == "s4" and new_status == "accepted_demo" and new_evidence_status == "accepted_demo":
        prereq = [x for x in rows.values() if x["package_id"] in ("s1","s2","s3")]
        if not all(x["evidence_status"] == "accepted_demo" for x in prereq):
            raise ValueError("security_prerequisites_not_accepted")
        unlocked = 10_000_000

    now = int(time.time())
    c.execute(
        "UPDATE capital_plan_execution SET status=?,committed_rub=?,actual_rub=?,evidence_status=?,evidence_ref=?,unlocked_value_rub=?,note=?,updated_by=?,updated_at=? "
        "WHERE scenario_id='security' AND package_id=?",
        (new_status,new_committed,new_actual,new_evidence_status,new_evidence_ref,unlocked,new_note,actor,now,package_id),
    )


def reset_demo(c, actor="system"):
    c.execute("DELETE FROM capital_plan_execution WHERE demo_only=1")
    seed_demo(c, actor)


def snapshot(c):
    seed_demo(c)
    plan = capital_plan.snapshot(c)
    packages = {x["id"]: x for x in plan["plan"]["packages"]}
    rows = [r for r in _rows(c) if r["scenario_id"] == "security"]
    projected = []
    for r in rows:
        p = packages[r["package_id"]]
        planned = int(r["planned_rub"])
        committed = int(r["committed_rub"])
        actual = int(r["actual_rub"])
        projected.append({
            **r,
            "title": p["title"],
            "deadline": p["deadline"],
            "deliverables": p["deliverables"],
            "evidence_gate": p["evidence_gate"],
            "stop_rule": p["stop_rule"],
            "commitment_variance_rub": committed - planned,
            "actual_vs_plan_variance_rub": actual - planned,
            "actual_vs_commitment_variance_rub": actual - committed,
            "plan_consumed_pct": round(actual / planned * 100.0, 1) if planned else 0.0,
            "evidence_accepted": r["evidence_status"] == "accepted_demo",
        })

    totals = {
        "planned_rub": sum(x["planned_rub"] for x in projected),
        "committed_rub": sum(x["committed_rub"] for x in projected),
        "actual_rub": sum(x["actual_rub"] for x in projected),
        "unlocked_value_rub": sum(x["unlocked_value_rub"] for x in projected),
    }
    totals["uncommitted_rub"] = totals["planned_rub"] - totals["committed_rub"]
    totals["committed_unspent_rub"] = totals["committed_rub"] - totals["actual_rub"]
    totals["actual_vs_plan_variance_rub"] = totals["actual_rub"] - totals["planned_rub"]
    totals["evidence_accepted_count"] = sum(1 for x in projected if x["evidence_accepted"])
    totals["package_count"] = len(projected)

    blocked = [x for x in projected if x["status"] == "blocked"]
    in_progress = [x for x in projected if x["status"] == "in_progress"]
    next_action = (
        "Complete S2 durable production / restore evidence before releasing further Security capital."
        if in_progress else
        "Resolve blocked package prerequisites."
        if blocked else
        "Prepare final acceptance."
    )

    return {
        "version": "capital-plan-execution-v1",
        "scenario_id": "security",
        "plan_reference": {
            "allocation_rub": plan["plan"]["allocation_rub"],
            "commercial_state": plan["plan"]["commercial_state"],
        },
        "totals": totals,
        "packages": projected,
        "next_action": next_action,
        "control_rules": [
            "Actual spend cannot exceed commercial commitment.",
            "Commercial commitment cannot exceed planned package allocation.",
            "Spend does not unlock value; accepted evidence does.",
            "S4 cannot unlock the 10m Security milestone until S1-S3 evidence gates are accepted.",
            "Unspent committed capital is not the same as uncommitted capital.",
        ],
        "truth_boundary": {
            "demo_execution": True,
            "actual_erp_spend": False,
            "actual_purchase_orders": False,
            "actual_payment_authority": False,
            "note": "Execution figures are illustrative demo records until connected to approved procurement/ERP/finance sources.",
        },
    }
