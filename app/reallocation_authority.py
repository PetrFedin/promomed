import time
from app import recovery_reforecast

REQUIRED_ROLES=["Finance","Business Owner","Investment Committee"]

def _proposals(c):
    try:return [dict(r) for r in c.execute("SELECT id,scenario_id,source_capacity_rub,finance_target_rub,governance_target_rub,status,reason,proposed_by,proposed_at,demo_only FROM capital_reallocation_proposals ORDER BY proposed_at,id")]
    except Exception:return []

def _approvals(c):
    try:return [dict(r) for r in c.execute("SELECT id,proposal_id,approval_role,status,actor,accepted_at,note,demo_only FROM capital_reallocation_approvals ORDER BY approval_role")]
    except Exception:return []

def create_demo_proposal(c,actor):
    d=recovery_reforecast.snapshot(c)
    b=next(x for x in d["scenarios"] if x["id"]=="B_REALLOCATE_AFTER_S2_FAILURE")
    total=int(b["reallocation_candidate_rub"])
    finance=min(2_000_000,total); governance=total-finance
    now=int(time.time()); pid="realloc:security:s2-failure"
    c.execute("INSERT INTO capital_reallocation_proposals(id,scenario_id,source_capacity_rub,finance_target_rub,governance_target_rub,status,reason,proposed_by,proposed_at,demo_only) VALUES(?,?,?,?,?,'approval_pending',?,?,?,1) ON CONFLICT(id) DO UPDATE SET source_capacity_rub=excluded.source_capacity_rub,finance_target_rub=excluded.finance_target_rub,governance_target_rub=excluded.governance_target_rub,status='approval_pending',reason=excluded.reason,proposed_by=excluded.proposed_by,proposed_at=excluded.proposed_at,demo_only=1",(pid,b["id"],total,finance,governance,b["reason"],actor,now))
    for role in REQUIRED_ROLES:
        c.execute("INSERT INTO capital_reallocation_approvals(id,proposal_id,approval_role,status,actor,accepted_at,note,demo_only) VALUES(?,?,?,'awaiting',NULL,NULL,'',1) ON CONFLICT(proposal_id,approval_role) DO NOTHING",(f"{pid}:{role}",pid,role))

def accept_demo(c,role,actor):
    if role not in REQUIRED_ROLES: raise ValueError("unknown_approval_role")
    ps=_proposals(c)
    if not ps: raise ValueError("proposal_missing")
    pid=ps[-1]["id"]; now=int(time.time())
    c.execute("UPDATE capital_reallocation_approvals SET status='accepted_demo',actor=?,accepted_at=?,note='Presentation approval simulation' WHERE proposal_id=? AND approval_role=?",(actor,now,pid,role))
    approvals=[x for x in _approvals(c) if x["proposal_id"]==pid]
    if approvals and all(x["status"]=="accepted_demo" for x in approvals):
        c.execute("UPDATE capital_reallocation_proposals SET status='approved_demo_preview' WHERE id=?",(pid,))

def reset_demo(c):
    c.execute("DELETE FROM capital_reallocation_approvals WHERE demo_only=1")
    c.execute("DELETE FROM capital_reallocation_proposals WHERE demo_only=1")

def snapshot(c):
    ps=_proposals(c); p=ps[-1] if ps else None
    approvals=[x for x in _approvals(c) if p and x["proposal_id"]==p["id"]]
    return {"version":"reallocation-approval-v1","proposal":p,"approvals":approvals,"required_roles":REQUIRED_ROLES,"all_demo_approved":bool(p and approvals and all(x["status"]=="accepted_demo" for x in approvals)),"capital_moved":False,"truth_boundary":{"demo_only":True,"approved_reallocation":False,"automatic_money_movement":False,"note":"APPROVED_DEMO_PREVIEW is not a binding capital movement."}}
