"""Two-actor, versioned commercial binding decisions.

This is commercial entitlement governance only, NOT a transfer of historical
participant consents, a contract, a general collaboration grant, or evidence of
CRM deletion. Reassignment is intentionally unsupported: create a new tenant.
"""
import hashlib
import json
import re
import time
from urllib.parse import parse_qs, urlparse

from app import db, partner_org_scope
from app.commanding import custom, error

ROUTE="/api/institution/partner-binding/v1"
KEY=re.compile(r"^[0-9a-f]{32}$")
TTL_SECONDS=48*3600


def _actor(c,role,email):
    if role!="governance" or not isinstance(email,str) or not email:
        return False
    if not db.demo_seed_enabled() and email.lower().endswith("@demo.ru"):
        return False
    return bool(c.execute(
        "SELECT 1 FROM accounts WHERE email=? AND role='governance' "
        "AND status='active'",(email,),
    ).fetchone())


def _org(c,organization_id,*,lock=False):
    if lock and db.backend_name()=="sqlite" and not c.in_transaction:
        c.execute("BEGIN IMMEDIATE")
    sql=(
        "SELECT id,partner_id,demo_only,status,name "
        "FROM institutional_organizations WHERE id=?"
    )
    if lock and db.backend_name()=="postgres":
        sql+=" FOR UPDATE"
    row=c.execute(sql,(organization_id,)).fetchone()
    if not row or row["status"]!="active":
        return None
    if not db.demo_seed_enabled() and int(row["demo_only"])!=0:
        return None
    return row


def _version(c,organization_id):
    row=c.execute(
        "SELECT version FROM institutional_partner_binding_revisions_v1 "
        "WHERE organization_id=?",(organization_id,),
    ).fetchone()
    return int(row["version"]) if row else 0


def _history(c,organization_id):
    """Prevent a newly bound partner from inheriting old contacts/appointments."""
    if _version(c,organization_id)>0:
        return True
    # Never activate a dormant, pre-existing operator membership as an
    # accidental commercial entitlement for a newly assigned partner.
    if c.execute(
        "SELECT 1 FROM institutional_memberships "
        "WHERE organization_id=? AND status='active' LIMIT 1",
        (organization_id,),
    ).fetchone():
        return True
    for table in (
        "partner_commercial_placements_v1",
        "participant_partner_leads_v1",
        "partner_appointment_slots_v1",
    ):
        if c.execute(
            "SELECT 1 FROM "+table+" WHERE organization_id=? LIMIT 1",
            (organization_id,),
        ).fetchone():
            return True
    return False


def _target_valid(c,partner_id):
    return bool(c.execute(
        "SELECT 1 FROM partners WHERE id=? AND status='active'",(partner_id,),
    ).fetchone())


def _receipt(c,request_id,organization_id,action,actor,version_before,
             version_after,now):
    previous=c.execute(
        "SELECT event_no,receipt_sha256 FROM institutional_partner_binding_events_v1 "
        "WHERE organization_id=? ORDER BY event_no DESC LIMIT 1",
        (organization_id,),
    ).fetchone()
    prior=previous["receipt_sha256"] if previous else None
    event_no=int(previous["event_no"])+1 if previous else 1
    document={
        "requestId":request_id,"organizationId":organization_id,
        "action":action,"actor":actor,"at":now,
        "versionBefore":version_before,"versionAfter":version_after,
        "eventNo":event_no,"previousReceipt":prior,
    }
    digest=hashlib.sha256(json.dumps(
        document,sort_keys=True,separators=(",",":"),ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    c.execute(
        "INSERT INTO institutional_partner_binding_events_v1("
        "id,request_id,organization_id,event_no,action,actor,recorded_at,"
        "version_before,version_after,receipt_sha256,previous_receipt_sha256) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (request_id[:16]+digest[:16],request_id,organization_id,event_no,
         action,actor,now,version_before,version_after,digest,prior),
    )
    return digest


def _public(row,now=None):
    data=dict(row)
    if data["status"]=="pending" and int(data["expires_at"])<=(
        int(time.time()) if now is None else int(now)
    ):
        data["effective_status"]="expired"
    else:
        data["effective_status"]=data["status"]
    data["scope"]="commercial_only"
    return data


def _propose(c,email,data):
    fields={
        "action","request_id","organization_id","expected_version",
        "expected_partner_id","new_partner_id","reason","evidence_ref",
    }
    if set(data)!=fields:
        return error("invalid_request",422)
    request_id=data.get("request_id")
    organization_id=partner_org_scope.org_id(data.get("organization_id"))
    expected_version=data.get("expected_version")
    old=data.get("expected_partner_id")
    new=data.get("new_partner_id")
    reason=data.get("reason")
    evidence=data.get("evidence_ref")
    if (
        not isinstance(request_id,str) or not KEY.fullmatch(request_id)
        or not organization_id
        or type(expected_version) is not int or expected_version<0
        or (old is not None and (
            not isinstance(old,str) or not old.strip() or len(old)>100))
        or (new is not None and (
            not isinstance(new,str) or not new.strip() or len(new)>100))
        or not isinstance(reason,str) or not 12<=len(reason.strip())<=500
        or not isinstance(evidence,str) or not 8<=len(evidence.strip())<=200
    ):
        return error("invalid_request",422)
    old=old.strip() if old is not None else None
    new=new.strip() if new is not None else None
    if (old is None)==(new is None):
        # Neither no-op nor direct transfer from one partner to another.
        return error("reassignment_not_supported",409)

    org=_org(c,organization_id,lock=True)
    if org is None:
        return error("organization_not_found",404)
    existing=c.execute(
        "SELECT * FROM institutional_partner_binding_requests_v1 WHERE id=?",
        (request_id,),
    ).fetchone()
    if existing:
        match=(
            existing["organization_id"]==organization_id
            and existing["requested_by"]==email
            and existing["expected_partner_id"]==old
            and existing["new_partner_id"]==new
            and int(existing["expected_version"])==expected_version
            and existing["reason"]==reason.strip()
            and existing["evidence_ref"]==evidence.strip()
        )
        return (custom({"request":_public(existing),"replayed":True})
                if match else error("idempotency_conflict",409))
    if org["partner_id"]!=old or _version(c,organization_id)!=expected_version:
        return error("version_conflict",409)
    if new is not None:
        if not _target_valid(c,new):
            return error("partner_not_active",409)
        if _history(c,organization_id):
            return error("prior_commercial_history_requires_new_organization",409)
    now=int(time.time())
    pending=c.execute(
        "SELECT 1 FROM institutional_partner_binding_requests_v1 "
        "WHERE organization_id=? AND status='pending' AND expires_at>? LIMIT 1",
        (organization_id,now),
    ).fetchone()
    if pending:
        return error("request_already_pending",409)
    inserted=c.execute(
        "INSERT INTO institutional_partner_binding_requests_v1("
        "id,organization_id,expected_partner_id,new_partner_id,expected_version,"
        "reason,evidence_ref,requested_by,requested_at,expires_at,status,"
        "demo_only) VALUES(?,?,?,?,?,?,?,?,?,?,'pending',?) "
        "ON CONFLICT(id) DO NOTHING",
        (request_id,organization_id,old,new,expected_version,reason.strip(),
         evidence.strip(),email,now,now+TTL_SECONDS,int(org["demo_only"])),
    )
    if inserted.rowcount!=1:
        return error("idempotency_conflict",409)
    _receipt(c,request_id,organization_id,"proposed",email,
             expected_version,expected_version,now)
    row=c.execute(
        "SELECT * FROM institutional_partner_binding_requests_v1 WHERE id=?",
        (request_id,),
    ).fetchone()
    return custom({"request":_public(row),"replayed":False,
                   "requiresIndependentReviewer":True},201)


def _review(c,email,data):
    if set(data)!={"action","request_id","decision_id","decision","review_reason"}:
        return error("invalid_request",422)
    request_id=data.get("request_id")
    decision_id=data.get("decision_id")
    decision=data.get("decision")
    reason=data.get("review_reason")
    if (
        not isinstance(request_id,str) or not KEY.fullmatch(request_id)
        or not isinstance(decision_id,str) or not KEY.fullmatch(decision_id)
        or decision not in ("approve","reject")
        or not isinstance(reason,str) or not 12<=len(reason.strip())<=500
    ):
        return error("invalid_request",422)
    reason=reason.strip()
    if db.backend_name()=="sqlite" and not c.in_transaction:
        c.execute("BEGIN IMMEDIATE")
    lookup=c.execute(
        "SELECT organization_id FROM institutional_partner_binding_requests_v1 "
        "WHERE id=?",(request_id,),
    ).fetchone()
    if not lookup:
        return error("request_not_found",404)
    org=_org(c,lookup["organization_id"],lock=True)
    if not org:
        return error("organization_not_found",404)
    sql="SELECT * FROM institutional_partner_binding_requests_v1 WHERE id=?"
    if db.backend_name()=="postgres":
        sql+=" FOR UPDATE"
    row=c.execute(sql,(request_id,)).fetchone()
    if not row or row["organization_id"]!=org["id"]:
        return error("request_not_found",404)
    if row["requested_by"]==email:
        return error("independent_review_required",403)
    if row["status"]!="pending":
        if (
            row["decision_id"]==decision_id
            and row["reviewed_by"]==email
            and row["review_reason"]==reason
            and ((decision=="approve" and row["status"]=="applied")
                 or (decision=="reject" and row["status"]=="rejected"))
        ):
            return custom({"request":_public(row),"replayed":True})
        return error("decision_already_recorded",409)
    # A decision id is globally unique, not just unique for one request.
    # Reject reuse cleanly rather than leaking a SQL UNIQUE error to HTTP.
    reused=c.execute(
        "SELECT 1 FROM institutional_partner_binding_requests_v1 "
        "WHERE decision_id=? AND id<>? LIMIT 1",
        (decision_id,request_id),
    ).fetchone()
    if reused:
        return error("idempotency_conflict",409)
    now=int(time.time())
    if int(row["expires_at"])<=now:
        return error("request_expired",409)
    if int(row["demo_only"])!=int(org["demo_only"]):
        return error("organization_boundary_changed",409)
    if decision=="approve":
        version=int(row["expected_version"])
        if _version(c,org["id"])!=version or org["partner_id"]!=row["expected_partner_id"]:
            return error("version_conflict",409)
        target=row["new_partner_id"]
        if target is not None:
            if not _target_valid(c,target):
                return error("partner_not_active",409)
            if _history(c,org["id"]):
                return error("prior_commercial_history_requires_new_organization",409)
        # PostgreSQL cannot infer the type of an untyped "? IS NULL"
        # parameter. Choose one of two fixed SQL predicates instead.
        # No untrusted string is interpolated into the SQL structure.
        if row["expected_partner_id"] is None:
            predicate="partner_id IS NULL"
            params=(target,org["id"],int(org["demo_only"]))
        else:
            predicate="partner_id=?"
            params=(target,org["id"],int(org["demo_only"]),
                    row["expected_partner_id"])
        changed=c.execute(
            "UPDATE institutional_organizations SET partner_id=? "
            "WHERE id=? AND status='active' AND demo_only=? AND "+predicate,
            params,
        )
        if changed.rowcount!=1:
            return error("version_conflict",409)
        if version==0:
            cas=c.execute(
                "INSERT INTO institutional_partner_binding_revisions_v1("
                "organization_id,version,updated_at,updated_by) VALUES(?,1,?,?) "
                "ON CONFLICT(organization_id) DO NOTHING",
                (org["id"],now,email),
            )
        else:
            cas=c.execute(
                "UPDATE institutional_partner_binding_revisions_v1 "
                "SET version=version+1,updated_at=?,updated_by=? "
                "WHERE organization_id=? AND version=?",
                (now,email,org["id"],version),
            )
        if cas.rowcount!=1:
            return error("version_conflict",409)
        if target is None:
            # Existing consent/booking history is retained for the owner;
            # no new partner may inherit it via this API.
            c.execute(
                "UPDATE partner_commercial_placements_v1 "
                "SET status='paused',version=version+1,updated_at=?,updated_by=? "
                "WHERE organization_id=? AND status IN ('planned','enabled')",
                (now,email,org["id"]),
            )
            c.execute(
                "UPDATE partner_appointment_slots_v1 "
                "SET status='closed',version=version+1,updated_at=? "
                "WHERE organization_id=? AND status='open'",
                (now,org["id"]),
            )
        state="applied"
        action="applied"
        next_version=version+1
    else:
        state="rejected"
        action="rejected"
        next_version=int(row["expected_version"])
    try:
        updated=c.execute(
            "UPDATE institutional_partner_binding_requests_v1 "
            "SET status=?,decision_id=?,reviewed_by=?,reviewed_at=?,review_reason=? "
            "WHERE id=? AND status='pending'",
            (state,decision_id,email,now,reason,request_id),
        )
    except db.INTEGRITY_ERRORS:
        # A different organization may have committed the same decision key
        # after our pre-read. Roll back ALL earlier binding/placement writes.
        c.rollback()
        return error("idempotency_conflict",409)
    if updated.rowcount!=1:
        return error("decision_already_recorded",409)
    _receipt(c,request_id,org["id"],action,email,
             int(row["expected_version"]),next_version,now)
    fresh=c.execute(
        "SELECT * FROM institutional_partner_binding_requests_v1 WHERE id=?",
        (request_id,),
    ).fetchone()
    return custom({
        "request":_public(fresh),"replayed":False,
        "commercialAccessChanged":decision=="approve",
        "externalDataDeletionClaimed":False,
        "externalRevocationAcknowledged":False,
        "collaborationScopeAutomaticallyChanged":False,
    })


def handle_command(c,route,role,email,data):
    if route!=ROUTE:
        return None
    if not _actor(c,role,email):
        return error("forbidden",403)
    if not isinstance(data,dict):
        return error("invalid_request",422)
    action=data.get("action")
    if action=="propose":
        return _propose(c,email,data)
    if action=="review":
        return _review(c,email,data)
    return error("bad_action",400)


def read(c,raw_path,role,email):
    parsed=urlparse(raw_path)
    if parsed.path!=ROUTE:
        return None
    if not _actor(c,role,email):
        return {"error":"forbidden"},403
    args=parse_qs(parsed.query,keep_blank_values=True)
    if parsed.fragment or set(args)!={"organization_id"} or len(args["organization_id"])!=1:
        return {"error":"unsupported_query"},422
    org_id=partner_org_scope.org_id(args["organization_id"][0])
    if not org_id:
        return {"error":"invalid_request"},422
    org=_org(c,org_id)
    if org is None:
        return {"error":"organization_not_found"},404
    now=int(time.time())
    requests=[_public(row,now) for row in c.execute(
        "SELECT * FROM institutional_partner_binding_requests_v1 "
        "WHERE organization_id=? ORDER BY requested_at DESC,id DESC LIMIT 100",
        (org_id,),
    )]
    events=[dict(row) for row in c.execute(
        "SELECT request_id,event_no,action,actor,recorded_at,version_before,"
        "version_after,receipt_sha256,previous_receipt_sha256 "
        "FROM institutional_partner_binding_events_v1 "
        "WHERE organization_id=? ORDER BY event_no DESC LIMIT 200",
        (org_id,),
    )]
    return {
        "version":"institution-partner-binding-governance-v1",
        "organizationId":org_id,
        "organizationName":org["name"],
        "currentPartnerId":org["partner_id"],
        "bindingVersion":_version(c,org_id),
        "requests":requests,
        "events":events,
        "truthBoundary":{
            "twoDistinctActiveGovernanceAccounts":True,
            "commercialAccessOnly":True,
            "historicalContactTransfer":False,
            "externalDeletionClaimed":False,
            "independentExternalApprovalVerified":False,
            "collaborationScopeUnchanged":True,
            "reassignmentSupported":False,
        },
    },200


def serve(actor,raw_path):
    if not actor:
        return {"error":"unauthorized"},401
    c=db.connect()
    try:
        return read(c,raw_path,actor[0],actor[2])
    finally:
        c.close()
