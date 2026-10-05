import time

from app import db


CHARTER_ID = "PILOT-01"


def seed_demo(c):
    now = int(time.time())
    c.execute(
        """INSERT OR IGNORE INTO pilot_charters(
               id,version,status,title,objective,decision_owner_role,sponsor_role,
               operations_owner_role,created_by,created_at,updated_at
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (
            CHARTER_ID, 1, "draft", "СОСТОЯНИЕ · Controlled Pilot",
            "Доказать управляемый year-round health relationship platform через реальное событие, partner evidence и post-event return.",
            "sales", "sales", "organizer", "system-demo", now, now,
        ),
    )
    kpis = [
        ("KPI01", "Attendance conversion", "verified attendance / registered participants", "registration + check-in authority"),
        ("KPI02", "Operational recovery", "critical scenarios with verified recovery / critical scenarios", "incident + venue + live audit trail"),
        ("KPI03", "Partner delivery completion", "accepted contractual deliverables / contracted deliverables", "pilot deliverable authority"),
        ("KPI04", "Consented continuation", "explicit follow-up actions / eligible participants", "consent + partner/community actions"),
        ("KPI05", "Post-event return", "returning participants / attended participants", "journey + replay + follow-up"),
        ("KPI06", "Actual delivery cost", "verified direct pilot delivery cost", "finance-approved pilot cost ledger"),
        ("KPI07", "Contribution vs actual", "recognized pilot value - verified direct delivery cost", "finance-approved actuals"),
    ]
    for kid, name, formula, source in kpis:
        c.execute(
            """INSERT OR IGNORE INTO pilot_kpis(
                   id,charter_id,name,formula,source,target,status,required,baseline_version
               ) VALUES(?,?,?,?,?,'TO_AGREE','target_required',1,1)""",
            (kid, CHARTER_ID, name, formula, source),
        )
    deliverables = [
        ("DEL01", "Participant experience", "Participant can complete the agreed core journey without a critical dead end.", "Browser/runtime evidence", "organizer", "sales"),
        ("DEL02", "Live operations & recovery", "Agreed critical event scenarios have an evidenced recovery path.", "Incident + venue + live audit trail", "organizer", "sales"),
        ("DEL03", "Partner activation", "Contracted partner placement/appointment/action is executed and evidenced.", "Partner delivery evidence", "partner", "sales"),
        ("DEL04", "Consent-first continuation", "Continuation is recorded only after explicit allowed action.", "Consent/action audit trail", "organizer", "sales"),
        ("DEL05", "Post-event measurement", "Return/replay/follow-up evidence is available for the agreed window.", "Journey/replay/follow-up evidence", "organizer", "sales"),
        ("DEL06", "Pilot actuals pack", "Direct delivery cost and recognized commercial actuals are finance-approved.", "Finance-approved close pack", "sales", "organizer"),
    ]
    for row in deliverables:
        c.execute(
            """INSERT OR IGNORE INTO pilot_deliverables(
                   id,charter_id,label,acceptance_criterion,evidence_required,owner_role,acceptor_role,status
               ) VALUES(?,?,?,?,?,?,?,'planned')""",
            (row[0], CHARTER_ID, *row[1:]),
        )
    for role in ("sales", "organizer"):
        c.execute(
            "INSERT OR IGNORE INTO pilot_signoffs(id,charter_id,role,status) VALUES(?,?,?,'pending')",
            (f"SIGN-{role.upper()}", CHARTER_ID, role),
        )
    c.commit()


def _charter(c):
    row = c.execute(
        "SELECT * FROM pilot_charters WHERE id=?",
        (CHARTER_ID,),
    ).fetchone()
    return dict(row) if row else None


def snapshot(c):
    charter = _charter(c)
    if not charter:
        return {
            "charter": None,
            "kpis": [],
            "deliverables": [],
            "signoffs": [],
            "changes": [],
            "decisions": [],
            "gates": {"baseline_ready": False, "decision_ready": False, "go_allowed": False},
        }

    kpis = [dict(r) for r in c.execute(
        "SELECT * FROM pilot_kpis WHERE charter_id=? ORDER BY id", (CHARTER_ID,)
    )]
    deliverables = [dict(r) for r in c.execute(
        "SELECT * FROM pilot_deliverables WHERE charter_id=? ORDER BY id", (CHARTER_ID,)
    )]
    signoffs = [dict(r) for r in c.execute(
        "SELECT * FROM pilot_signoffs WHERE charter_id=? ORDER BY role", (CHARTER_ID,)
    )]
    changes = [dict(r) for r in c.execute(
        "SELECT * FROM pilot_changes WHERE charter_id=? ORDER BY created_at DESC,id DESC LIMIT 20", (CHARTER_ID,)
    )]
    decisions = [dict(r) for r in c.execute(
        "SELECT * FROM pilot_decisions WHERE charter_id=? ORDER BY created_at DESC,id DESC LIMIT 20", (CHARTER_ID,)
    )]

    targets_ready = all(
        (not int(k["required"])) or (
            str(k["target"]).strip()
            and str(k["target"]).strip().upper() != "TO_AGREE"
            and k["status"] in ("target_set", "approved")
        )
        for k in kpis
    )
    signoffs_ready = all(x["status"] == "signed" for x in signoffs)
    locked = charter["status"] == "approved" and charter["locked_at"] is not None
    actuals_complete = all(
        (not int(k["required"])) or (
            k["actual_value"] is not None
            and str(k["actual_value"]).strip() != ""
            and k["actual_source"] is not None
            and str(k["actual_source"]).strip() != ""
        )
        for k in kpis
    )
    deliverables_accepted = all(x["status"] == "accepted" for x in deliverables)
    readiness = db.readiness()
    production = bool(readiness.get("production_ready"))

    gates = {
        "targets_ready": targets_ready,
        "signoffs_ready": signoffs_ready,
        "baseline_ready": targets_ready and signoffs_ready and not locked,
        "baseline_locked": locked,
        "actuals_complete": actuals_complete,
        "deliverables_accepted": deliverables_accepted,
        "decision_ready": locked and actuals_complete,
        "go_allowed": locked and actuals_complete and deliverables_accepted and production,
        "production_ready": production,
    }

    decision_rights = [
        {"decision": "Set KPI target before baseline lock", "roles": "sales / organizer", "rule": "Target must be explicit; TO_AGREE cannot be locked."},
        {"decision": "Baseline sign-off", "roles": "sales + organizer", "rule": "Both sign-offs are required."},
        {"decision": "Change after baseline", "roles": "sales / organizer / partner", "rule": "Only via change request; baseline is not silently rewritten."},
        {"decision": "Submit deliverable evidence", "roles": "declared owner role", "rule": "Evidence is required before acceptance."},
        {"decision": "Accept deliverable", "roles": "declared acceptor role", "rule": "Owner cannot self-accept unless roles intentionally match."},
        {"decision": "GO", "roles": "sales / organizer", "rule": "Requires locked baseline, complete actuals, accepted deliverables and production readiness."},
        {"decision": "ITERATE / STOP", "roles": "sales / organizer", "rule": "Requires locked baseline and explicit rationale."},
    ]

    return {
        "charter": charter,
        "kpis": kpis,
        "deliverables": deliverables,
        "signoffs": signoffs,
        "changes": changes,
        "decisions": decisions,
        "gates": gates,
        "decision_rights": decision_rights,
        "truth_boundary": {
            "demo_or_preproduction": not production,
            "targets_are_user_approved": locked,
            "actuals_are_user_supplied_or_integrated_evidence": actuals_complete,
            "go_is_currently_allowed": gates["go_allowed"],
            "medical_governance_in_scope": False,
        },
    }
