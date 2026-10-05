import secrets
import time

from app import db, pilot_governance
from app.commanding import custom, error
from app.core import audit


def _now():
    return int(time.time())


def _id(prefix):
    return prefix + "-" + secrets.token_hex(6)


def _charter(c):
    row = c.execute(
        "SELECT * FROM pilot_charters WHERE id=?",
        (pilot_governance.CHARTER_ID,),
    ).fetchone()
    return dict(row) if row else None


def _snapshot(c):
    return custom(pilot_governance.snapshot(c))


def _locked(charter):
    return bool(charter and charter["status"] == "approved" and charter["locked_at"] is not None)


def handle_command(c, path, role, email, data):
    if not path.startswith("/api/pilot/"):
        return None

    charter = _charter(c)
    if not charter:
        return error("pilot_charter_not_found", 404)

    if path == "/api/pilot/kpi-target":
        if role not in ("sales", "organizer"):
            return error("forbidden", 403)
        if _locked(charter):
            return error("baseline_locked", 409)
        kid = str(data.get("kpi_id", "")).strip()
        target = str(data.get("target", "")).strip()
        if not kid or not target or target.upper() == "TO_AGREE":
            return error("explicit_target_required", 422)
        row = c.execute(
            "SELECT id FROM pilot_kpis WHERE id=? AND charter_id=?",
            (kid, pilot_governance.CHARTER_ID),
        ).fetchone()
        if not row:
            return error("kpi_not_found", 404)
        c.execute(
            "UPDATE pilot_kpis SET target=?,status='target_set',approved_by=NULL,approved_at=NULL WHERE id=?",
            (target, kid),
        )
        c.execute(
            "UPDATE pilot_charters SET updated_at=? WHERE id=?",
            (_now(), pilot_governance.CHARTER_ID),
        )
        audit(c, "pilot_kpi_target_set", email, {"kpi_id": kid, "target": target})
        return _snapshot(c)

    if path == "/api/pilot/signoff":
        if role not in ("sales", "organizer"):
            return error("forbidden", 403)
        if _locked(charter):
            return error("baseline_locked", 409)
        row = c.execute(
            "SELECT id,status FROM pilot_signoffs WHERE charter_id=? AND role=?",
            (pilot_governance.CHARTER_ID, role),
        ).fetchone()
        if not row:
            return error("signoff_not_required_for_role", 403)
        c.execute(
            "UPDATE pilot_signoffs SET status='signed',actor=?,signed_at=? WHERE id=?",
            (email, _now(), row["id"]),
        )
        audit(c, "pilot_signoff", email, {"role": role})
        return _snapshot(c)

    if path == "/api/pilot/lock-baseline":
        if role not in ("sales", "organizer"):
            return error("forbidden", 403)
        if _locked(charter):
            return error("baseline_locked", 409)
        proof = pilot_governance.snapshot(c)
        if not proof["gates"]["targets_ready"]:
            return error("kpi_targets_incomplete", 409)
        if not proof["gates"]["signoffs_ready"]:
            return error("required_signoffs_incomplete", 409)
        now = _now()
        c.execute(
            """UPDATE pilot_charters
               SET status='approved',approved_by=?,approved_at=?,locked_at=?,updated_at=?
               WHERE id=?""",
            (email, now, now, now, pilot_governance.CHARTER_ID),
        )
        c.execute(
            """UPDATE pilot_kpis
               SET status='approved',approved_by=?,approved_at=?,baseline_version=?
               WHERE charter_id=?""",
            (email, now, int(charter["version"]), pilot_governance.CHARTER_ID),
        )
        audit(
            c,
            "pilot_baseline_locked",
            email,
            {"charter_id": pilot_governance.CHARTER_ID, "version": int(charter["version"])},
        )
        return _snapshot(c)

    if path == "/api/pilot/kpi-actual":
        if role not in ("sales", "organizer"):
            return error("forbidden", 403)
        if not _locked(charter):
            return error("baseline_not_locked", 409)
        kid = str(data.get("kpi_id", "")).strip()
        value = str(data.get("actual_value", "")).strip()
        source = str(data.get("actual_source", "")).strip()
        if not kid or not value or not source:
            return error("actual_value_and_source_required", 422)
        row = c.execute(
            "SELECT id FROM pilot_kpis WHERE id=? AND charter_id=?",
            (kid, pilot_governance.CHARTER_ID),
        ).fetchone()
        if not row:
            return error("kpi_not_found", 404)
        c.execute(
            "UPDATE pilot_kpis SET actual_value=?,actual_source=?,actual_updated_at=? WHERE id=?",
            (value, source, _now(), kid),
        )
        audit(c, "pilot_kpi_actual_recorded", email, {"kpi_id": kid, "source": source})
        return _snapshot(c)

    if path == "/api/pilot/deliverable-evidence":
        did = str(data.get("deliverable_id", "")).strip()
        evidence = str(data.get("evidence", "")).strip()
        if not did or not evidence:
            return error("deliverable_and_evidence_required", 422)
        row = c.execute(
            "SELECT id,owner_role,status FROM pilot_deliverables WHERE id=? AND charter_id=?",
            (did, pilot_governance.CHARTER_ID),
        ).fetchone()
        if not row:
            return error("deliverable_not_found", 404)
        if role != row["owner_role"] and role != "sales":
            return error("forbidden", 403)
        if row["status"] == "accepted":
            return error("deliverable_already_accepted", 409)
        c.execute(
            "UPDATE pilot_deliverables SET evidence=?,status='evidence_submitted' WHERE id=?",
            (evidence, did),
        )
        audit(c, "pilot_deliverable_evidence", email, {"deliverable_id": did})
        return _snapshot(c)

    if path == "/api/pilot/deliverable-accept":
        did = str(data.get("deliverable_id", "")).strip()
        row = c.execute(
            "SELECT id,acceptor_role,status,evidence FROM pilot_deliverables WHERE id=? AND charter_id=?",
            (did, pilot_governance.CHARTER_ID),
        ).fetchone()
        if not row:
            return error("deliverable_not_found", 404)
        if role != row["acceptor_role"]:
            return error("forbidden", 403)
        if not row["evidence"]:
            return error("deliverable_evidence_required", 409)
        if row["status"] == "accepted":
            return _snapshot(c)
        c.execute(
            "UPDATE pilot_deliverables SET status='accepted',accepted_by=?,accepted_at=? WHERE id=?",
            (email, _now(), did),
        )
        audit(c, "pilot_deliverable_accepted", email, {"deliverable_id": did})
        return _snapshot(c)

    if path == "/api/pilot/change-request":
        if role not in ("sales", "organizer", "partner"):
            return error("forbidden", 403)
        if not _locked(charter):
            return error("baseline_not_locked", 409)
        item_type = str(data.get("item_type", "")).strip()
        item_id = str(data.get("item_id", "")).strip()
        field_name = str(data.get("field_name", "")).strip()
        new_value = str(data.get("new_value", "")).strip()
        rationale = str(data.get("rationale", "")).strip()
        if item_type not in ("kpi", "deliverable", "charter") or not item_id or not field_name or not new_value or not rationale:
            return error("invalid_change_request", 422)
        old_value = ""
        if item_type == "kpi":
            row = c.execute("SELECT * FROM pilot_kpis WHERE id=?", (item_id,)).fetchone()
        elif item_type == "deliverable":
            row = c.execute("SELECT * FROM pilot_deliverables WHERE id=?", (item_id,)).fetchone()
        else:
            row = c.execute("SELECT * FROM pilot_charters WHERE id=?", (item_id,)).fetchone()
        if not row:
            return error("change_item_not_found", 404)
        if field_name not in row.keys():
            return error("change_field_not_found", 422)
        old_value = "" if row[field_name] is None else str(row[field_name])
        change_id = _id("CHG")
        c.execute(
            """INSERT INTO pilot_changes(
                   id,charter_id,item_type,item_id,field_name,old_value,new_value,rationale,actor,status,created_at
               ) VALUES(?,?,?,?,?,?,?,?,?,'proposed',?)""",
            (
                change_id, pilot_governance.CHARTER_ID, item_type, item_id, field_name,
                old_value, new_value, rationale, email, _now(),
            ),
        )
        audit(c, "pilot_change_requested", email, {"change_id": change_id, "item_id": item_id, "field_name": field_name})
        return _snapshot(c)

    if path == "/api/pilot/decision":
        if role not in ("sales", "organizer"):
            return error("forbidden", 403)
        if not _locked(charter):
            return error("baseline_not_locked", 409)
        decision = str(data.get("decision", "")).strip().upper()
        rationale = str(data.get("rationale", "")).strip()
        if decision not in ("GO", "ITERATE", "STOP") or not rationale:
            return error("decision_and_rationale_required", 422)
        proof = pilot_governance.snapshot(c)
        if decision == "GO" and not proof["gates"]["go_allowed"]:
            blockers = [k for k, v in proof["gates"].items() if k in ("actuals_complete", "deliverables_accepted", "production_ready") and not v]
            return error("go_gate_not_satisfied", 409, blockers=blockers)
        decision_id = _id("DEC")
        c.execute(
            "INSERT INTO pilot_decisions(id,charter_id,decision,rationale,actor,created_at) VALUES(?,?,?,?,?,?)",
            (decision_id, pilot_governance.CHARTER_ID, decision, rationale, email, _now()),
        )
        audit(c, "pilot_decision", email, {"decision_id": decision_id, "decision": decision})
        return _snapshot(c)

    return None
