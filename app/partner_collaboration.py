"""Partner collaboration board: internal planning only, identity-bound and fail-closed."""
import hashlib
import json
import secrets
import time

from app.commanding import custom, error
from app.core import audit

ROUTES={"/api/partner-collaboration/create","/api/partner-collaboration/project","/api/partner-collaboration/task"}
FORMATS={"event","studio","content","learning","experience"}
STATES={"draft","review_requested","changes_requested","internally_reviewed","archived"}
TASK_STATES={"todo","in_progress","done"}

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
    if not row or (role!="organizer" and row["owner_email"]!=email):return None
    return dict(row)

def snapshot(c,role,email,project_id=None):
    if role not in ("partner","organizer"):raise PermissionError("forbidden")
    if project_id:
        p=_project(c,project_id,role,email)
        if p is None:raise LookupError("project_not_found")
        tasks=[dict(x) for x in c.execute("SELECT id,title,lane,status,version,updated_at FROM partner_collab_tasks WHERE project_id=? ORDER BY created_at,id",(project_id,))]
        history=[dict(x) for x in c.execute("SELECT kind,actor_role,created_at FROM partner_collab_events WHERE project_id=? ORDER BY created_at,id",(project_id,))]
        return {"project":p,"tasks":tasks,"events":history,"truthBoundary":"internal_planning_only","contractAccepted":False,"revenueClaimed":False}
    if role=="organizer":rows=c.execute("SELECT id,owner_email,title,objective,format,status,version,demo_only,created_at,updated_at FROM partner_collab_projects ORDER BY updated_at DESC LIMIT 100")
    else:rows=c.execute("SELECT id,owner_email,title,objective,format,status,version,demo_only,created_at,updated_at FROM partner_collab_projects WHERE owner_email=? ORDER BY updated_at DESC LIMIT 100",(email,))
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
        if prior["route"]!=route or prior["request_sha256"]!=digest:return error("idempotency_conflict",409)
        return custom(json.loads(prior["result_json"]))
    now=int(time.time())
    if route=="/api/partner-collaboration/create":
        if role!="partner":return error("forbidden",403)
        title=_text(data.get("title"),140);objective=_text(data.get("objective"),1200)
        fmt=data.get("format")
        if not title or fmt not in FORMATS:return error("invalid_project",422)
        pid=secrets.token_hex(12)
        c.execute("INSERT INTO partner_collab_projects(id,owner_email,title,objective,format,status,version,demo_only,created_at,updated_at) VALUES(?,?,?,?,?,'draft',1,1,?,?)",(pid,email,title,objective,fmt,now,now))
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
            if target is None:return error("bad_action",422)
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
            if not title or lane not in ("partner","platform"):return error("invalid_task",422)
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
    if len(project_ids) > 1:
        return {"error": "invalid_project_id"}, 422
    pid = project_ids[0] if project_ids else None
    if pid is not None and (not pid or len(pid) > 100):
        return {"error": "invalid_project_id"}, 422
    c = connect()
    try:
        try:
            return snapshot(c, actor[0], actor[2], pid), 200
        except PermissionError:
            return {"error": "forbidden"}, 403
        except LookupError:
            return {"error": "project_not_found"}, 404
    finally:
        c.close()
