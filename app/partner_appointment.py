"""Organization-scoped partner appointment authority v1.

Legacy appointment tables remain demo-only. This module creates a separate,
versioned authority with verified organization membership, exact public event
admission, participant-owned booking predicates and capacity serialization.
"""
import hashlib
import json
import re
import secrets
import time

from app import db, partner_org_scope
from app.commanding import custom, error
from app.core import audit
from app.public_state import exact_artifact_admitted

SLOT_ROUTE="/api/partner-appointment-slot/v1"
BOOKING_ROUTE="/api/partner-appointment-booking/v1"
ROUTES=frozenset((SLOT_ROUTE,BOOKING_ROUTE))
REQUEST_ID=re.compile(r"^[a-f0-9]{32}$")
SLOT_ID=re.compile(r"^[a-f0-9]{24}$")
ITEM_ID=re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_-]{0,63}$")
TIME=re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")


def _digest(route,data):
    payload={k:v for k,v in data.items() if k!="request_id"}
    raw=json.dumps(
        {"route":route,"data":payload},
        sort_keys=True,separators=(",",":"),ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _minutes(value):
    if not isinstance(value,str) or not TIME.fullmatch(value):
        return None
    h,m=value.split(":")
    return int(h)*60+int(m)


def _runtime_demo_value():
    return 1 if db.demo_seed_enabled() else 0


def _member(c,organization_id,email):
    m=partner_org_scope.member(c,organization_id,email)
    if m is None or int(m["demo_only"])!=_runtime_demo_value():
        return None
    org=c.execute(
        "SELECT organization_type FROM institutional_organizations WHERE id=?",
        (organization_id,),
    ).fetchone()
    if org is None or org["organization_type"]!="strategic_partner":
        return None
    return m


def _lock_partner_actor(c,email):
    if db.backend_name()=="sqlite" and not getattr(c,"in_transaction",False):
        c.execute("BEGIN IMMEDIATE")
    sql=(
        "SELECT email FROM accounts WHERE email=? "
        "AND role='partner' AND status='active'"
    )
    if db.backend_name()=="postgres":
        sql+=" FOR UPDATE"
    return c.execute(sql,(email,)).fetchone()


def _participant(c,email):
    return c.execute(
        "SELECT 1 FROM accounts WHERE email=? "
        "AND role='participant' AND status='active'",
        (email,),
    ).fetchone()


def _item(c,item_id):
    return c.execute(
        'SELECT id,start,"end",venue,track,format,title,audience,capacity,'
        "stream,replay,partner FROM program_items WHERE id=?",
        (item_id,),
    ).fetchone()


def _valid_window(item,start,end):
    start_m=_minutes(start)
    end_m=_minutes(end)
    item_start=_minutes(item["start"]) if item is not None else None
    item_end=_minutes(item["end"]) if item is not None else None
    return (
        start_m is not None
        and end_m is not None
        and item_start is not None
        and item_end is not None
        and start_m<end_m
        and item_start<=start_m
        and end_m<=item_end
    )


def _slot(c,slot_id,*,lock=False):
    if lock and db.backend_name()=="sqlite" and not getattr(c,"in_transaction",False):
        c.execute("BEGIN IMMEDIATE")
    sql=(
        "SELECT s.id,s.organization_id,s.item_id,s.start,s.\"end\",s.capacity,"
        "s.status,s.version,s.demo_only,s.created_by,s.created_at,s.updated_at,"
        "o.name organization_name,o.status organization_status,o.demo_only organization_demo_only "
        "FROM partner_appointment_slots_v1 s "
        "JOIN institutional_organizations o ON o.id=s.organization_id "
        "WHERE s.id=?"
    )
    if lock and db.backend_name()=="postgres":
        sql+=" FOR UPDATE OF s"
    return c.execute(sql,(slot_id,)).fetchone()


def _slot_visible(row):
    return (
        row is not None
        and row["organization_status"]=="active"
        and int(row["demo_only"])==_runtime_demo_value()
        and int(row["organization_demo_only"])==int(row["demo_only"])
    )


def _booking_projection(slot,row):
    return {
        "slotId":slot["id"],
        "organizationName":slot["organization_name"],
        "itemId":slot["item_id"],
        "start":slot["start"],
        "end":slot["end"],
        "status":row["status"],
        "requestedAt":row["requested_at"],
        "updatedAt":row["updated_at"],
        "verifiedAttendance":False,
        "marketingConsent":False,
        "partnerLead":False,
    }


def _slot_projection(slot):
    return {
        "slotId":slot["id"],
        "organizationId":slot["organization_id"],
        "organizationName":slot["organization_name"],
        "itemId":slot["item_id"],
        "start":slot["start"],
        "end":slot["end"],
        "capacity":slot["capacity"],
        "status":slot["status"],
        "version":slot["version"],
        "demoOnly":bool(slot["demo_only"]),
    }


def _operation(c,email,request_id):
    return c.execute(
        "SELECT route,request_sha256,result_json "
        "FROM partner_appointment_operations_v1 "
        "WHERE actor_email=? AND request_id=?",
        (email,request_id),
    ).fetchone()


def _store_operation(c,email,request_id,route,digest,result):
    c.execute(
        "INSERT INTO partner_appointment_operations_v1("
        "actor_email,request_id,route,request_sha256,result_json,created_at"
        ") VALUES(?,?,?,?,?,?)",
        (
            email,request_id,route,digest,
            json.dumps(result,sort_keys=True,separators=(",",":"),ensure_ascii=False),
            int(time.time()),
        ),
    )


def _replay(prior,route,digest):
    if prior is None:
        return None
    if prior["route"]!=route or prior["request_sha256"]!=digest:
        return error("idempotency_conflict",409)
    return custom(json.loads(prior["result_json"]))


def _partner_slot(c,role,email,data):
    if role!="partner":
        return error("forbidden",403)
    if _lock_partner_actor(c,email) is None:
        return error("forbidden",403)
    if not isinstance(data,dict):
        return error("invalid_request",422)
    action=data.get("action")
    request_id=data.get("request_id")
    if (
        action not in ("create","update","close","cancel")
        or not isinstance(request_id,str)
        or not REQUEST_ID.fullmatch(request_id)
    ):
        return error("invalid_request",422)

    digest=_digest(SLOT_ROUTE,data)

    if action=="create":
        expected={"action","organization_id","item_id","start","end","capacity","request_id"}
        if set(data)!=expected:
            return error("invalid_request",422)
        organization_id=partner_org_scope.org_id(data.get("organization_id"))
        item_id=data.get("item_id")
        capacity=data.get("capacity")
        if (
            not organization_id
            or not isinstance(item_id,str)
            or not ITEM_ID.fullmatch(item_id)
            or type(capacity) is not int
            or not 1<=capacity<=1000
        ):
            return error("invalid_request",422)
        member=_member(c,organization_id,email)
        if member is None:
            return error("organization_not_found",404)

        prior=_operation(c,email,request_id)
        replay=_replay(prior,SLOT_ROUTE,digest)
        if replay is not None:
            return replay

        item=_item(c,item_id)
        if item is None or not exact_artifact_admitted(c,"event",item):
            return error("program_item_not_found",404)
        if not _valid_window(item,data["start"],data["end"]):
            return error("invalid_slot_window",422)

        now=int(time.time())
        slot_id=secrets.token_hex(12)
        c.execute(
            "INSERT INTO partner_appointment_slots_v1("
            "id,organization_id,item_id,start,\"end\",capacity,status,version,"
            "demo_only,created_by,created_at,updated_at"
            ") VALUES(?,?,?,?,?,?,'open',1,?,?,?,?)",
            (
                slot_id,organization_id,item_id,data["start"],data["end"],capacity,
                int(member["demo_only"]),email,now,now,
            ),
        )
        slot=_slot(c,slot_id)
        result={
            "slot":_slot_projection(slot),
            "truthBoundary":"organization_member_created_slot",
        }
        _store_operation(c,email,request_id,SLOT_ROUTE,digest,result)
        audit(c,"partner_appointment_slot_created",email,{
            "slot_id":slot_id,"organization_id":organization_id,
            "item_id":item_id,"request_id":request_id,
        })
        return custom(result,201)

    expected=(
        {"action","slot_id","expected_version","start","end","capacity","request_id"}
        if action=="update"
        else {"action","slot_id","expected_version","request_id"}
    )
    if set(data)!=expected:
        return error("invalid_request",422)
    slot_id=data.get("slot_id")
    expected_version=data.get("expected_version")
    if (
        not isinstance(slot_id,str)
        or not SLOT_ID.fullmatch(slot_id)
        or type(expected_version) is not int
        or expected_version<1
    ):
        return error("invalid_request",422)

    slot=_slot(c,slot_id,lock=True)
    if slot is None or not _slot_visible(slot):
        return error("slot_not_found",404)
    if _member(c,slot["organization_id"],email) is None:
        return error("slot_not_found",404)

    prior=_operation(c,email,request_id)
    replay=_replay(prior,SLOT_ROUTE,digest)
    if replay is not None:
        return replay

    if int(slot["version"])!=expected_version:
        return error("version_conflict",409)
    if slot["status"]!="open":
        return error("slot_not_open",409)

    now=int(time.time())
    if action=="update":
        capacity=data.get("capacity")
        if type(capacity) is not int or not 1<=capacity<=1000:
            return error("invalid_request",422)
        item=_item(c,slot["item_id"])
        if item is None or not exact_artifact_admitted(c,"event",item):
            return error("program_item_not_found",404)
        if not _valid_window(item,data["start"],data["end"]):
            return error("invalid_slot_window",422)
        confirmed=int(c.execute(
            "SELECT COUNT(*) n FROM partner_appointment_bookings_v1 "
            "WHERE slot_id=? AND status='confirmed'",
            (slot_id,),
        ).fetchone()["n"])
        if capacity<confirmed:
            return error("capacity_below_confirmed",409)
        c.execute(
            "UPDATE partner_appointment_slots_v1 "
            "SET start=?,\"end\"=?,capacity=?,version=version+1,updated_at=? "
            "WHERE id=? AND version=?",
            (data["start"],data["end"],capacity,now,slot_id,expected_version),
        )
        kind="updated"
    else:
        target="closed" if action=="close" else "cancelled"
        c.execute(
            "UPDATE partner_appointment_slots_v1 "
            "SET status=?,version=version+1,updated_at=? "
            "WHERE id=? AND version=?",
            (target,now,slot_id,expected_version),
        )
        kind=target

    current=_slot(c,slot_id)
    result={
        "slot":_slot_projection(current),
        "truthBoundary":"organization_member_managed_slot",
    }
    _store_operation(c,email,request_id,SLOT_ROUTE,digest,result)
    audit(c,"partner_appointment_slot_"+kind,email,{
        "slot_id":slot_id,"organization_id":slot["organization_id"],
        "request_id":request_id,
    })
    return custom(result)


def _participant_booking(c,role,email,data):
    if role!="participant":
        return error("forbidden",403)
    if not isinstance(data,dict) or set(data)!={"slot_id","action"}:
        return error("invalid_request",422)
    slot_id=data.get("slot_id")
    action=data.get("action")
    if (
        not isinstance(slot_id,str)
        or not SLOT_ID.fullmatch(slot_id)
        or action not in ("book","cancel")
    ):
        return error("invalid_request",422)
    if _participant(c,email) is None:
        return error("forbidden",403)

    own=c.execute(
        "SELECT status,requested_at,updated_at "
        "FROM partner_appointment_bookings_v1 WHERE slot_id=? AND email=?",
        (slot_id,email),
    ).fetchone()
    slot=_slot(c,slot_id,lock=True)

    if action=="cancel":
        if own is None or own["status"]=="cancelled":
            return error("appointment_not_found",404)
        was_confirmed=own["status"]=="confirmed"
        now=int(time.time())
        c.execute(
            "UPDATE partner_appointment_bookings_v1 "
            "SET status='cancelled',updated_at=? WHERE slot_id=? AND email=?",
            (now,slot_id,email),
        )
        promoted=False
        if was_confirmed and _slot_visible(slot) and slot["status"]=="open":
            item=_item(c,slot["item_id"])
            if item is not None and exact_artifact_admitted(c,"event",item):
                waiter=c.execute(
                    "SELECT email FROM partner_appointment_bookings_v1 "
                    "WHERE slot_id=? AND status='waitlist' "
                    "ORDER BY requested_at,email LIMIT 1",
                    (slot_id,),
                ).fetchone()
                if waiter:
                    c.execute(
                        "UPDATE partner_appointment_bookings_v1 "
                        "SET status='confirmed',updated_at=? "
                        "WHERE slot_id=? AND email=? AND status='waitlist'",
                        (now,slot_id,waiter["email"]),
                    )
                    promoted=True
        current=c.execute(
            "SELECT status,requested_at,updated_at "
            "FROM partner_appointment_bookings_v1 WHERE slot_id=? AND email=?",
            (slot_id,email),
        ).fetchone()
        audit(c,"partner_appointment_cancelled",email,{"slot_id":slot_id})
        return custom({
            "booking":_booking_projection(slot,current) if slot is not None else {
                "slotId":slot_id,"status":"cancelled",
                "requestedAt":current["requested_at"],"updatedAt":current["updated_at"],
                "verifiedAttendance":False,"marketingConsent":False,"partnerLead":False,
            },
            "queuePromotionOccurred":promoted,
        })

    if not _slot_visible(slot) or slot["status"]!="open":
        return error("slot_not_found",404)
    item=_item(c,slot["item_id"])
    if item is None or not exact_artifact_admitted(c,"event",item):
        return error("slot_not_found",404)

    if own is not None and own["status"] in ("confirmed","waitlist"):
        return custom({
            "booking":_booking_projection(slot,own),
            "replayed":True,
        })

    conflict=c.execute(
        'SELECT p.id FROM activity_bookings b '
        'JOIN program_items p ON p.id=b.item_id '
        "WHERE b.email=? AND b.status='booked' "
        'AND p.start<? AND p."end">? LIMIT 1',
        (email,slot["end"],slot["start"]),
    ).fetchone()
    if conflict:
        return error("schedule_conflict",409)

    other=c.execute(
        'SELECT s.id FROM partner_appointment_bookings_v1 b '
        'JOIN partner_appointment_slots_v1 s ON s.id=b.slot_id '
        "WHERE b.email=? AND b.status='confirmed' AND s.id<>? "
        'AND s.start<? AND s."end">? LIMIT 1',
        (email,slot_id,slot["end"],slot["start"]),
    ).fetchone()
    if other:
        return error("schedule_conflict",409)

    confirmed=int(c.execute(
        "SELECT COUNT(*) n FROM partner_appointment_bookings_v1 "
        "WHERE slot_id=? AND status='confirmed'",
        (slot_id,),
    ).fetchone()["n"])
    status="confirmed" if confirmed<int(slot["capacity"]) else "waitlist"
    now=int(time.time())
    if own is None:
        c.execute(
            "INSERT INTO partner_appointment_bookings_v1("
            "slot_id,email,status,requested_at,updated_at"
            ") VALUES(?,?,?,?,?)",
            (slot_id,email,status,now,now),
        )
    else:
        c.execute(
            "UPDATE partner_appointment_bookings_v1 "
            "SET status=?,requested_at=?,updated_at=? "
            "WHERE slot_id=? AND email=?",
            (status,now,now,slot_id,email),
        )
    current=c.execute(
        "SELECT status,requested_at,updated_at "
        "FROM partner_appointment_bookings_v1 WHERE slot_id=? AND email=?",
        (slot_id,email),
    ).fetchone()
    audit(c,"partner_appointment_"+status,email,{"slot_id":slot_id})
    return custom({
        "booking":_booking_projection(slot,current),
        "replayed":False,
    },201)


def handle_command(c,route,role,email,data):
    if route==SLOT_ROUTE:
        return _partner_slot(c,role,email,data)
    if route==BOOKING_ROUTE:
        return _participant_booking(c,role,email,data)
    return None
