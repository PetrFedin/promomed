"""Two-party internal task execution, without commercial/medical acceptance authority."""
import re
import secrets

from app.commanding import error
from app import partner_org_scope

ACTIONS = {
    "start": ("todo", "changes_requested"),
    "submit": ("in_progress",),
    "accept": ("submitted",),
    "request_changes": ("submitted",),
}
NEXT = {
    "start": "in_progress",
    "submit": "submitted",
    "accept": "accepted",
    "request_changes": "changes_requested",
}
HEX64 = re.compile(r"^[a-fA-F0-9]{64}$")


def _field(value, limit):
    return value.strip() if isinstance(value, str) and 0 < len(value.strip()) <= limit else ""


def transition(c, role, email, data, operation_id, now):
    """Return a new authoritative result dict or a CommandOutcome error.

    Caller holds its transaction and records the idempotency response in the
    same transaction, so failed commands cannot leave partial receipts.
    """
    pid = _field(data.get("project_id"), 100)
    tid = _field(data.get("task_id"), 100)
    action = data.get("action")
    version = data.get("expected_version")
    if not isinstance(action, str) or action not in ACTIONS or not pid or not tid or type(version) is not int or version < 1:
        return error("invalid_execution_request", 422)

    project = c.execute(
        "SELECT id,owner_email,status,demo_only FROM partner_collab_projects WHERE id=?",
        (pid,),
    ).fetchone()
    if not partner_org_scope.accessible_project(c,project,role,email):
        return error("project_not_found", 404)
    if project["status"] != "internally_reviewed":
        return error("project_not_reviewed_for_execution", 409)

    task = c.execute(
        "SELECT id,lane,status,version FROM partner_collab_tasks WHERE project_id=? AND id=?",
        (pid, tid),
    ).fetchone()
    if not task:
        return error("task_not_found", 404)
    assigned_role = "partner" if task["lane"] == "partner" else "organizer"
    reviewer_role = "organizer" if assigned_role == "partner" else "partner"
    if role != (reviewer_role if action in ("accept", "request_changes") else assigned_role):
        return error("forbidden", 403)

    execution = c.execute(
        """SELECT status,version,submitted_by,submitted_role,
                  evidence_ref,evidence_ref_sha256,reviewed_by,reviewed_role,decision_note
           FROM partner_collab_task_execution WHERE task_id=?""", (tid,),
    ).fetchone()
    current_status = execution["status"] if execution else task["status"]
    if current_status not in ACTIONS[action]:
        return error("invalid_task_transition", 409)
    if version != task["version"] or (execution and execution["version"] != version):
        return error("version_conflict", 409)

    prior_submitter = execution["submitted_by"] if execution else None
    if action in ("accept", "request_changes") and (
        not prior_submitter or prior_submitter == email
    ):
        return error("independent_reviewer_required", 403)

    evidence_ref = execution["evidence_ref"] if execution else None
    evidence_sha = execution["evidence_ref_sha256"] if execution else None
    reviewed_by = None
    reviewed_role = None
    decision_note = None
    submitted_by = prior_submitter
    submitted_role = execution["submitted_role"] if execution else None

    if action == "start":
        # New execution after an amendment must submit a fresh artifact.
        submitted_by = submitted_role = evidence_ref = evidence_sha = None
    elif action == "submit":
        evidence_ref = _field(data.get("evidence_ref"), 240)
        evidence_sha = _field(data.get("evidence_sha256"), 64).lower()
        if not evidence_ref or not HEX64.fullmatch(evidence_sha):
            return error("artifact_reference_and_sha256_required", 422)
        if any(ord(ch) < 32 for ch in evidence_ref):
            return error("invalid_artifact_reference", 422)
        submitted_by, submitted_role = email, role
    else:
        decision_note = _field(data.get("decision_note"), 600) or None
        if action == "request_changes" and not decision_note:
            return error("review_note_required", 422)
        reviewed_by, reviewed_role = email, role

    native_status = {"todo": "todo", "in_progress": "in_progress", "submitted": "in_progress",
                     "changes_requested": "in_progress", "accepted": "done"}[NEXT[action]]
    updated = c.execute(
        """UPDATE partner_collab_tasks
           SET status=?,version=version+1,updated_by=?,updated_at=?
           WHERE id=? AND project_id=? AND version=?""",
        (native_status, email, now, tid, pid, version),
    )
    if updated.rowcount != 1:
        return error("version_conflict", 409)
    new_version = version + 1
    c.execute(
        """INSERT INTO partner_collab_task_execution
           (task_id,status,version,submitted_by,submitted_role,evidence_ref,
            evidence_ref_sha256,reviewed_by,reviewed_role,decision_note,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(task_id) DO UPDATE SET
             status=excluded.status,version=excluded.version,
             submitted_by=excluded.submitted_by,submitted_role=excluded.submitted_role,
             evidence_ref=excluded.evidence_ref,
             evidence_ref_sha256=excluded.evidence_ref_sha256,
             reviewed_by=excluded.reviewed_by,reviewed_role=excluded.reviewed_role,
             decision_note=excluded.decision_note,updated_at=excluded.updated_at""",
        (tid, NEXT[action], new_version, submitted_by, submitted_role, evidence_ref,
         evidence_sha, reviewed_by, reviewed_role, decision_note, now),
    )
    receipt_id = secrets.token_hex(12)
    c.execute(
        """INSERT INTO partner_collab_task_receipts
           (id,task_id,project_id,operation_id,actor_email,actor_role,action,
            previous_status,next_status,task_version,evidence_ref,
            evidence_ref_sha256,decision_note,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (receipt_id, tid, pid, operation_id, email, role, action, current_status,
         NEXT[action], new_version, evidence_ref, evidence_sha, decision_note, now),
    )
    return {
        "task_id": tid, "project_id": pid, "status": NEXT[action],
        "version": new_version, "receipt_id": receipt_id,
        "truthBoundary": "internal_task_review_only",
        "contractAccepted": False, "invoiceAccepted": False,
        "artifactIntegrityIndependentlyVerified": False,
    }
