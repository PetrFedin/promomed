"""Partner collaboration board: internal planning only, identity-bound and fail-closed."""
import hashlib
import json
import secrets
import time

from app.commanding import custom, error
from app import partner_execution, partner_org_scope
from app.core import audit

ROUTES={"/api/partner-collaboration/create","/api/partner-collaboration/project","/api/partner-collaboration/task","/api/partner-collaboration/execute"}
FORMATS={"event","studio","content","learning","experience"}
STATES={"draft","review_requested","changes_requested","internally_reviewed","archived"}
TASK_STATES={"todo","in_progress","submitted","changes_requested","accepted"}

def _hash(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

def _text(value,limit):
    if not isinstance(value,str):return ""
    value=value.strip()
    return value if 0<len(value)<=limit else ""

def _events(c,pid,email,role,kind,detail):
    c.execute("INSERT INTO partner_collab_events(id,project_id,actor_email,actor_role,kind,detail,created_at) VALUES(?,?,?,?,?,?,?)",
              (secrets.token_hex(12),pid,email,role,kind,detail,int(time.time())))

def _project(c,pid,role,email):
    row=c.execute("SELECT * FROM partner_collab_projects WHERE id=?",(pid,)).fetchone()
    if not partner_org_scope.accessible_project(c,row,role,email):return None
    result=dict(row)
    scope=c.execute("SELECT organization_id FROM partner_collab_project_scopes WHERE project_id=?",(pid,)).fetchone()
    result["organization_id"]=scope["organization_id"] if scope else None
    return result

def snapshot(c,role,email,project_id=None):
    if role not in ("partner","organizer"):raise PermissionError("forbidden")
    if project_id:
        p=_project(c,project_id,role,email)
        if p is None:raise LookupError("project_not_found")
        tasks=[dict(x) for x in c.execute("""SELECT t.id,t.title,t.lane,
              COALESCE(x.status,t.status) status,t.version,t.updated_at,
              x.submitted_role,x.evidence_ref,x.evidence_ref_sha256,
              x.reviewed_role,x.decision_note
           FROM partner_collab_tasks t
           LEFT JOIN partner_collab_task_execution x ON x.task_id=t.id
           WHERE t.project_id=? ORDER BY t.created_at,t.id""",(project_id,))]
        history=[dict(x) for x in c.execute("SELECT kind,actor_role,created_at FROM partner_collab_events WHERE project_id=? ORDER BY created_at,id",(project_id,))]
        receipts=[dict(x) for x in c.execute("""SELECT id,task_id,action,actor_role,
                 previous_status,next_status,task_version,evidence_ref_sha256,
                 decision_note,created_at FROM partner_collab_task_receipts
                 WHERE project_id=? ORDER BY created_at,task_id,task_version,id""",(project_id,))]
        return {"project":p,"tasks":tasks,"events":history,"receipts":receipts,"truthBoundary":"internal_task_review_only","contractAccepted":False,"revenueClaimed":False,"artifactIntegrityIndependentlyVerified":False}
    if role=="organizer":
        rows=c.execute("""SELECT p.id,p.owner_email,p.title,p.objective,p.format,p.status,
                    p.version,p.demo_only,p.created_at,p.updated_at,s.organization_id
                  FROM partner_collab_projects p
                  LEFT JOIN partner_collab_project_scopes s ON s.project_id=p.id
                  WHERE (s.project_id IS NULL AND ?=1 AND p.demo_only=1)
                     OR (s.project_id IS NOT NULL AND s.demo_only=p.demo_only
                         AND EXISTS(
                           SELECT 1 FROM institutional_organizations o
                           WHERE o.id=s.organization_id AND o.status='active'
                             AND o.demo_only=s.demo_only)
                         AND EXISTS(
                           SELECT 1 FROM accounts a
                           WHERE a.email=? AND a.role='organizer' AND a.status='active'))
                  ORDER BY p.updated_at DESC,p.id LIMIT 100""",
                  (int(partner_org_scope.legacy_demo_allowed()),email))
    else:
        now=int(time.time())
        rows=c.execute("""SELECT p.id,p.owner_email,p.title,p.objective,p.format,p.status,
                    p.version,p.demo_only,p.created_at,p.updated_at,s.organization_id
                  FROM partner_collab_projects p
                  LEFT JOIN partner_collab_project_scopes s ON s.project_id=p.id
                  WHERE (s.project_id IS NULL AND ?=1 AND p.demo_only=1
                         AND p.owner_email=?)
                  OR (s.project_id IS NOT NULL AND s.demo_only=p.demo_only
                      AND EXISTS(
                        SELECT 1 FROM institutional_organizations o
                        JOIN institutional_memberships m ON m.organization_id=o.id
                        JOIN accounts a ON a.email=m.account_email
                        WHERE o.id=s.organization_id AND o.status='active'
                          AND o.demo_only=s.demo_only AND m.demo_only=o.demo_only
                          AND m.account_email=? AND a.status='active' AND a.role='partner'
                          AND m.status='active'
                          AND m.member_role IN ('operator','administrator')
                          AND m.effective_at<=?
                          AND (m.expires_at IS NULL OR m.expires_at>?)
                          AND LENGTH(TRIM(m.verification_ref))>0
                          AND (o.demo_only=1 OR m.account_email NOT LIKE ?)
                       ))
                  ORDER BY p.updated_at DESC,p.id LIMIT 100""",
                  (int(partner_org_scope.legacy_demo_allowed()),email,email,now,now,"%@demo.ru"))
    return {"projects":[dict(x) for x in rows],"truthBoundary":"internal_planning_only","contractAccepted":False}

def handle_command(c,route,role,email,data):
    if route not in ROUTES:return None
    if role not in ("partner","organizer"):return error("forbidden",403)
    if not isinstance(data,dict):return error("bad_payload",400)
    operation=_text(data.get("operation_id"),100)
    if not operation:return error("operation_id_required",422)
    digest=_hash({"route":route,"data":{k:v for k,v in data.items() if k!="operation_id"}})
    prior=c.execute("SELECT route,request_sha256,result_json FROM partner_collab_operations WHERE actor_email=? AND operation_id=?",(email,operation)).fetchone()
    if prior:
        # Idempotent replay must not bypass revoked institutional access.
        if route=="/api/partner-collaboration/create":
            requested_org=partner_org_scope.org_id(data.get("organization_id"))
            if "organization_id" in data and not requested_org:
                return error("invalid_organization_id",422)
            if requested_org:
                if not partner_org_scope.member(c,requested_org,email):
                    return error("organization_not_found",404)
            elif not partner_org_scope.legacy_demo_allowed():
                return error("organization_required",422)
        elif not _project(c,_text(data.get("project_id"),100),role,email):
            return error("project_not_found",404)
        if prior["route"]!=route or prior["request_sha256"]!=digest:return error("idempotency_conflict",409)
        return custom(json.loads(prior["result_json"]))
    now=int(time.time())
    if route=="/api/partner-collaboration/execute":
        result=partner_execution.transition(c,role,email,data,operation,now)
        if not isinstance(result,dict):return result
    elif route=="/api/partner-collaboration/create":
        if role!="partner":return error("forbidden",403)
        title=_text(data.get("title"),140);objective=_text(data.get("objective"),1200)
        fmt=data.get("format")
        if not title or not isinstance(fmt,str) or fmt not in FORMATS:return error("invalid_project",422)
        wants_scope="organization_id" in data
        organization=partner_org_scope.org_id(data.get("organization_id"))
        if wants_scope and not organization:return error("invalid_organization_id",422)
        if organization:
            admission=partner_org_scope.member(c,organization,email)
            if admission is None:return error("organization_not_found",404)
            # No non-demo pilot may be created until independent production admission.
            if int(admission["demo_only"])!=1:return error("non_demo_partner_pilot_not_admitted",409)
        elif not partner_org_scope.legacy_demo_allowed():
            return error("organization_required",422)
        pid=secrets.token_hex(12)
        c.execute("INSERT INTO partner_collab_projects(id,owner_email,title,objective,format,status,version,demo_only,created_at,updated_at) VALUES(?,?,?,?,?,'draft',1,1,?,?)",(pid,email,title,objective,fmt,now,now))
        if organization:
            c.execute("INSERT INTO partner_collab_project_scopes(project_id,organization_id,demo_only,linked_by,created_at) VALUES(?,?,1,?,?)",(pid,organization,email,now))
        _events(c,pid,email,role,"project_created","draft")
        result={"project_id":pid,"status":"draft","version":1,"truthBoundary":"internal_planning_only"}
    else:
        pid=_text(data.get("project_id"),100)
        p=_project(c,pid,role,email)
        if not p:return error("project_not_found",404)
        if p["status"]=="archived":return error("project_archived",409)
        if route=="/api/partner-collaboration/project":
            action=data.get("action")
            target={"request_review":"review_requested","request_changes":"changes_requested","review":"internally_reviewed","archive":"archived"}.get(action)
            if not isinstance(action,str) or target is None:return error("bad_action",422)
            allowed={"draft":{"request_review","archive"},"changes_requested":{"request_review","archive"},"review_requested":{"request_changes","review","archive"},"internally_reviewed":{"request_changes","archive"}}
            if action not in allowed.get(p["status"],set()):return error("invalid_transition",409)
            if action in ("request_review",) and role!="partner":return error("forbidden",403)
            if action in ("review","request_changes") and role!="organizer":return error("forbidden",403)
            version=data.get("expected_version")
            if type(version) is not int or version!=p["version"]:return error("version_conflict",409)
            c.execute("UPDATE partner_collab_projects SET status=?,version=version+1,updated_at=? WHERE id=? AND version=?",(target,now,pid,version))
            _events(c,pid,email,role,"status_"+target,target)
            result={"project_id":pid,"status":target,"version":version+1,"truthBoundary":"internal_planning_only"}
        else:
            if p["status"] not in ("draft","changes_requested"):return error("project_not_editable",409)
            if role!="partner":return error("forbidden",403)
            title=_text(data.get("title"),180);lane=data.get("lane")
            if not title or not isinstance(lane,str) or lane not in ("partner","platform"):return error("invalid_task",422)
            tid=secrets.token_hex(12)
            c.execute("INSERT INTO partner_collab_tasks(id,project_id,title,lane,status,version,created_by,updated_by,created_at,updated_at) VALUES(?,?,?,?,'todo',1,?,?,?,?)",(tid,pid,title,lane,email,email,now,now))
            _events(c,pid,email,role,"task_created",tid)
            result={"task_id":tid,"project_id":pid,"status":"todo","truthBoundary":"internal_planning_only"}
    c.execute("INSERT INTO partner_collab_operations(actor_email,operation_id,route,request_sha256,result_json,created_at) VALUES(?,?,?,?,?,?)",(email,operation,route,digest,json.dumps(result,sort_keys=True),now))
    audit(c,"partner_collaboration",email,{"route":route,"project_id":result.get("project_id"),"operation_id":operation})
    return custom(result,201 if route.endswith(("/create","/task")) else 200)

def read_result(query, actor, connect):
    """Read-only authenticated projection; never reveal a foreign project."""
    from urllib.parse import parse_qs
    if not actor:
        return {"error": "unauthorized"}, 401
    args = parse_qs(query, keep_blank_values=True)
    project_ids = args.get("project_id", [])
    org_view = args.get("view",[])==["organizations"]
    if len(project_ids)>1 or (org_view and project_ids):
        return {"error": "invalid_project_id"}, 422
    pid = project_ids[0] if project_ids else None
    if pid is not None and (not pid or len(pid) > 100):
        return {"error": "invalid_project_id"}, 422
    c = connect()
    try:
        try:
            if org_view:
                if actor[0]!="partner":return {"error":"forbidden"},403
                return {"organizations":partner_org_scope.partner_organizations(c,actor[2]),
                        "legacyDemoAllowed":partner_org_scope.legacy_demo_allowed(),
                        "truthBoundary":"verified_demo_memberships_only"},200
            return snapshot(c, actor[0], actor[2], pid), 200
        except PermissionError:
            return {"error": "forbidden"}, 403
        except LookupError:
            return {"error": "project_not_found"}, 404
    finally:
        c.close()
