"""Organization-scoped partner commercial operations.

This replaces legacy singleton placement/lead writes with verified institutional
membership and explicit participant consent. It does not assert a contract,
revenue, attendance, medical consent, or marketing opt-in.
"""
import re
import secrets
import time
from urllib.parse import parse_qs, urlparse

from app import db, partner_org_scope
from app.commanding import custom, error

ROUTE="/api/partner-commercial/v1"
ACTIONS=frozenset(("placement_update","lead_submit","lead_withdraw"))
PLACEMENT_STATES=frozenset(("planned","enabled","paused","ended"))
KEY=re.compile(r"^[a-f0-9]{32}$")


def _text(value,limit):
    if not isinstance(value,str):
        return ""
    value=value.strip()
    return value if 0 < len(value) <= limit else ""


def _participant(c,email):
    if not isinstance(email,str) or not email:
        return None
    return c.execute(
        "SELECT email FROM accounts WHERE email=? "
        "AND role='participant' AND status='active'",
        (email,),
    ).fetchone()


def _target_org(c,organization_id):
    row=c.execute(
        "SELECT id,name,demo_only,partner_id FROM institutional_organizations "
        "WHERE id=? AND status='active'",
        (organization_id,),
    ).fetchone()
    if not row or not row["partner_id"]:
        return None
    if not db.demo_seed_enabled() and int(row["demo_only"] or 0)!=0:
        return None
    return row


def _placement(c,organization_id):
    return c.execute(
        "SELECT organization_id,status,version,updated_at,updated_by,demo_only "
        "FROM partner_commercial_placements_v1 WHERE organization_id=?",
        (organization_id,),
    ).fetchone()


def _partner_snapshot(c,email):
    now=int(time.time())
    memberships=c.execute(
        """SELECT o.id,o.name,o.demo_only,m.member_role
           FROM institutional_organizations o
           JOIN institutional_memberships m ON m.organization_id=o.id
           JOIN accounts a ON a.email=m.account_email
           WHERE m.account_email=? AND a.status='active' AND a.role='partner'
             AND o.status='active' AND m.status='active'
             AND m.member_role IN ('operator','administrator')
             AND m.effective_at<=?
             AND (m.expires_at IS NULL OR m.expires_at>?)
             AND m.demo_only=o.demo_only
             AND LENGTH(TRIM(m.verification_ref))>0
             AND (o.demo_only=1 OR m.account_email NOT LIKE ?)
           ORDER BY o.name,o.id""",
        (email,now,now,"%@demo.ru"),
    )
    organizations=[]
    for row in memberships:
        if not db.demo_seed_enabled() and int(row["demo_only"] or 0)!=0:
            continue
        placement=_placement(c,row["id"])
        leads=[dict(x) for x in c.execute(
            "SELECT id,email,kind,consent_at,created_at "
            "FROM participant_partner_leads_v1 "
            "WHERE organization_id=? AND status='submitted' "
            "ORDER BY created_at,id LIMIT 200",
            (row["id"],),
        )]
        organizations.append({
            "organizationId":row["id"],
            "organizationName":row["name"],
            "memberRole":row["member_role"],
            "placement":dict(placement) if placement else None,
            "leads":leads,
        })
    return {
        "version":"partner-commercial-v1",
        "organizations":organizations,
        "truthBoundary":{
            "operationalPlacementNotContract":True,
            "leadRequiresExplicitParticipantConsent":True,
            "leadWithdrawalRemovesPartnerVisibility":True,
            "revenueClaimed":False,
            "medicalConsent":False,
        },
    }


def _participant_snapshot(c,email):
    leads=[dict(x) for x in c.execute(
        "SELECT id,organization_id,kind,status,consent_at,created_at,withdrawn_at "
        "FROM participant_partner_leads_v1 "
        "WHERE email=? ORDER BY created_at DESC,id DESC LIMIT 200",
        (email,),
    )]
    return {
        "version":"partner-commercial-v1",
        "myLeads":leads,
        "truthBoundary":{
            "explicitContactSharingOnly":True,
            "marketingConsent":False,
            "medicalConsent":False,
            "partnerLeadIsNotSale":True,
        },
    }


def read(c,raw_path,role,email):
    parsed=urlparse(raw_path)
    if parsed.path!=ROUTE:
        return None
    if parsed.fragment:
        return {"error":"unsupported_query"},422
    args=parse_qs(parsed.query,keep_blank_values=True)
    if args:
        return {"error":"unsupported_query"},422
    if role=="partner":
        return _partner_snapshot(c,email),200
    if role=="participant" and _participant(c,email):
        return _participant_snapshot(c,email),200
    return {"error":"forbidden"},403


def serve(actor,raw_path):
    if not actor:
        return {"error":"unauthorized"},401
    c=db.connect()
    try:
        return read(c,raw_path,actor[0],actor[2])
    finally:
        c.close()


def handle_command(c,route,role,email,data):
    if route!=ROUTE:
        return None
    if not isinstance(data,dict):
        return error("invalid_request",422)
    action=data.get("action")
    if action not in ACTIONS:
        return error("bad_action",400)

    now=int(time.time())
    if action=="placement_update":
        if role!="partner":
            return error("forbidden",403)
        organization_id=partner_org_scope.org_id(data.get("organization_id"))
        state=data.get("status")
        expected=data.get("expected_version")
        if not organization_id or state not in PLACEMENT_STATES or type(expected) is not int or expected<0:
            return error("invalid_request",422)
        admission=partner_org_scope.member(c,organization_id,email)
        if admission is None:
            return error("organization_not_found",404)
        existing=_placement(c,organization_id)
        if existing is None:
            if expected!=0:
                return error("version_conflict",409)
            version=1
            c.execute(
                "INSERT INTO partner_commercial_placements_v1("
                "organization_id,status,version,updated_at,updated_by,demo_only"
                ") VALUES(?,?,?,?,?,?)",
                (organization_id,state,version,now,email,int(admission["demo_only"])),
            )
        else:
            if int(existing["version"])!=expected:
                return error("version_conflict",409)
            if existing["status"]=="ended":
                return error("placement_ended",409)
            version=expected+1
            c.execute(
                "UPDATE partner_commercial_placements_v1 "
                "SET status=?,version=?,updated_at=?,updated_by=? "
                "WHERE organization_id=? AND version=?",
                (state,version,now,email,organization_id,expected),
            )
        row=_placement(c,organization_id)
        return custom({
            "placement":dict(row),
            "truthBoundary":"operational_status_not_contract",
        },201 if expected==0 else 200)

    if role!="participant" or _participant(c,email) is None:
        return error("forbidden",403)

    if action=="lead_submit":
        organization_id=partner_org_scope.org_id(data.get("organization_id"))
        request_key=data.get("request_id")
        kind=_text(data.get("kind"),80)
        if not organization_id or not isinstance(request_key,str) or not KEY.fullmatch(request_key) or not kind:
            return error("invalid_request",422)
        if data.get("consent") is not True:
            return error("consent_required",422)
        org=_target_org(c,organization_id)
        placement=_placement(c,organization_id) if org else None
        if not org or not placement or placement["status"]!="enabled":
            return error("organization_not_found",404)

        prior=c.execute(
            "SELECT id,organization_id,kind,status,consent_at,created_at,withdrawn_at "
            "FROM participant_partner_leads_v1 WHERE email=? AND request_key=?",
            (email,request_key),
        ).fetchone()
        if prior:
            if prior["organization_id"]!=organization_id or prior["kind"]!=kind:
                return error("idempotency_conflict",409)
            return custom({"lead":dict(prior),"replayed":True})

        lead_id=secrets.token_hex(16)
        c.execute(
            "INSERT INTO participant_partner_leads_v1("
            "id,organization_id,email,request_key,kind,status,consent_at,created_at,"
            "withdrawn_at,demo_only) VALUES(?,?,?,?,?,'submitted',?,?,NULL,?)",
            (
                lead_id,organization_id,email,request_key,kind,now,now,
                int(org["demo_only"]),
            ),
        )
        row=c.execute(
            "SELECT id,organization_id,kind,status,consent_at,created_at,withdrawn_at "
            "FROM participant_partner_leads_v1 WHERE id=?",
            (lead_id,),
        ).fetchone()
        return custom({"lead":dict(row),"replayed":False},201)

    if set(data)!={"action","lead_id"}:
        return error("invalid_request",422)
    lead_id=data.get("lead_id")
    if not isinstance(lead_id,str) or not KEY.fullmatch(lead_id):
        return error("invalid_request",422)
    row=c.execute(
        "SELECT id,status FROM participant_partner_leads_v1 "
        "WHERE id=? AND email=?",
        (lead_id,email),
    ).fetchone()
    if not row:
        return error("lead_not_found",404)
    if row["status"]=="withdrawn":
        return custom({"leadId":lead_id,"status":"withdrawn","replayed":True})
    c.execute(
        "UPDATE participant_partner_leads_v1 "
        "SET status='withdrawn',withdrawn_at=? WHERE id=? AND email=? "
        "AND status='submitted'",
        (now,lead_id,email),
    )
    return custom({"leadId":lead_id,"status":"withdrawn","replayed":False})
