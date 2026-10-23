"""Organization-scoped partner appointment authority.

Appointment booking is explicit contact sharing for one organization and slot.
It is not attendance, marketing consent, medical consent, lead conversion or
contract acceptance.
"""
import secrets
import time
from urllib.parse import parse_qs, urlparse

from app import db, partner_org_scope, appointment_projection
from app.commanding import custom, error

ROUTE="/api/partner-appointments/v1"
AVAILABLE_ROUTE=ROUTE+"/available"
SLOT_STATES=frozenset(("open","closed","cancelled"))


def _participant(c,email):
    if not isinstance(email,str) or not email:
        return None
    return c.execute(
        "SELECT email FROM accounts WHERE email=? "
        "AND role='participant' AND status='active'",
        (email,),
    ).fetchone()


def _placement_enabled(c,organization_id):
    # Placement and its parent institution must both remain admitted.
    # A previously enabled placement does not outlive its organization.
    row=c.execute(
        "SELECT p.status,p.demo_only FROM partner_commercial_placements_v1 p "
        "JOIN institutional_organizations o ON o.id=p.organization_id "
        "WHERE p.organization_id=? AND o.status='active' "
        "AND LENGTH(TRIM(o.partner_id))>0 AND o.demo_only=p.demo_only",
        (organization_id,),
    ).fetchone()
    if not row or row["status"]!="enabled":
        return False
    if not db.demo_seed_enabled() and int(row["demo_only"] or 0)!=0:
        return False
    return True

def _slot(c,slot_id,*,lock=False):
    if lock and db.backend_name()=="sqlite" and not getattr(c,"in_transaction",False):
        c.execute("BEGIN IMMEDIATE")
    sql=(
        "SELECT id,organization_id,starts_at,ends_at,capacity,status,version,"
        "created_at,updated_at,created_by,demo_only "
        "FROM partner_appointment_slots_v1 WHERE id=?"
    )
    if lock and db.backend_name()=="postgres":
        sql+=" FOR UPDATE"
    row=c.execute(sql,(slot_id,)).fetchone()
    if row and not db.demo_seed_enabled() and int(row["demo_only"] or 0)!=0:
        return None
    return row


def _own_booking(c,slot_id,email):
    return c.execute(
        "SELECT slot_id,email,status,contact_consent_at,requested_at,updated_at "
        "FROM participant_partner_appointments_v1 "
        "WHERE slot_id=? AND email=?",
        (slot_id,email),
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
             AND LENGTH(TRIM(o.partner_id))>0
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
    for membership in memberships:
        if not db.demo_seed_enabled() and int(membership["demo_only"] or 0)!=0:
            continue
        slots=[]
        source_slots=list(c.execute(
            "SELECT id,starts_at,ends_at,capacity,status,version,updated_at "
            "FROM partner_appointment_slots_v1 "
            "WHERE organization_id=? AND demo_only=? "
            "ORDER BY CASE WHEN ends_at>? THEN 0 ELSE 1 END,starts_at,id LIMIT 201",
            (membership["id"],int(membership["demo_only"]),now),
        ))
        for slot in source_slots[:200]:
            counts=c.execute("SELECT SUM(CASE WHEN status='booked' THEN 1 ELSE 0 END) booked,"
                "SUM(CASE WHEN status='waitlist' THEN 1 ELSE 0 END) waitlist "
                "FROM participant_partner_appointments_v1 WHERE slot_id=?",(slot["id"],)).fetchone()
            bookings=[dict(x) for x in c.execute(
                "SELECT email,status,contact_consent_at,requested_at,updated_at "
                "FROM participant_partner_appointments_v1 "
                "WHERE slot_id=? AND status IN ('booked','waitlist') "
                "ORDER BY requested_at,email LIMIT 501",
                (slot["id"],),
            )]
            booked,waiting=int(counts['booked'] or 0),int(counts['waitlist'] or 0)
            slots.append({**dict(slot),"bookings":bookings[:500],"bookingsTruncated":len(bookings)>500,
                "counts":{"booked":booked,"waitlist":waiting,"available":max(0,slot['capacity']-booked),
                          "overCapacity":max(0,booked-slot['capacity'])}})
        organizations.append({
            "organizationId":membership["id"],
            "organizationName":membership["name"],
            "memberRole":membership["member_role"],
            "slots":slots,
            "slotsTruncated":len(source_slots)>200,
        })
    return {
        "version":"partner-appointments-v1",
        "organizations":organizations,
        "truthBoundary":{
            "appointmentIsNotAttendance":True,
            "contactSharingIsSlotSpecific":True,
            "marketingConsent":False,
            "medicalConsent":False,
        },
    }


def _participant_snapshot(c,email):
    rows,truncated=appointment_projection.owned(c,email,int(time.time()))
    return {
        "version":"partner-appointments-v1",
        "myAppointments":rows,
        "truncated":truncated,
        "truthBoundary":{
            "appointmentIsNotAttendance":True,
            "waitlistIsNotBooking":True,
            "marketingConsent":False,
            "medicalConsent":False,
        },
    }


def _available(c,organization_id,email):
    if not partner_org_scope.org_id(organization_id):
        return {"error":"invalid_organization"},422
    if not _placement_enabled(c,organization_id):
        return {"error":"organization_not_found"},404
    org=c.execute("SELECT id,name,demo_only FROM institutional_organizations WHERE id=?",(organization_id,)).fetchone()
    now=int(time.time())
    rows=list(c.execute("SELECT s.id,s.starts_at,s.ends_at,s.capacity,s.version,b.status my_status,"
        "(SELECT COUNT(*) FROM participant_partner_appointments_v1 n WHERE n.slot_id=s.id AND n.status='booked') booked "
        "FROM partner_appointment_slots_v1 s LEFT JOIN participant_partner_appointments_v1 b ON b.slot_id=s.id AND b.email=? "
        "WHERE s.organization_id=? AND s.status='open' AND s.starts_at>? AND s.demo_only=? "
        "ORDER BY s.starts_at,s.id LIMIT 201",(email,organization_id,now,org['demo_only'])))
    own,partial=appointment_projection.owned(c,email,now)
    slots=[]
    for row in rows[:200]:
        if not appointment_projection.positive_time(row['starts_at']) or not appointment_projection.positive_time(row['ends_at']) or row['ends_at']<=row['starts_at'] or type(row['capacity']) is not int or row['capacity']<1:
            continue
        conflicts=[]
        for other in own:
            overlap=min(row['ends_at'],other['ends_at'])-max(row['starts_at'],other['starts_at'])
            if other['slot_id']!=row['id'] and other['effective_status']=='booked' and overlap>0:
                conflicts.append({'slotId':other['slot_id'],'title':other['organization_name'],'overlapSeconds':overlap})
        slots.append({'id':row['id'],'version':row['version'],'startsAt':row['starts_at'],'endsAt':row['ends_at'],
            'availableSeats':max(0,row['capacity']-row['booked']),
            'myStatus':row['my_status'] if row['my_status'] in ('booked','waitlist') else None,'knownConflicts':conflicts})
    return {'organization':{'id':org['id'],'name':org['name']},'slots':slots,'asOf':now,
            'truncated':len(rows)>200,'conflictsComplete':not partial},200


def read(c,raw_path,role,email):
    parsed=urlparse(raw_path)
    if parsed.path==AVAILABLE_ROUTE:
        args=parse_qs(parsed.query,keep_blank_values=True)
        if parsed.fragment or set(args)!={'organization_id'} or len(args['organization_id'])!=1:
            return {'error':'unsupported_query'},422
        if role!='participant' or not _participant(c,email) or (not db.demo_seed_enabled() and email.lower().endswith('@demo.ru')):
            return {'error':'forbidden'},403
        return _available(c,args['organization_id'][0],email)
    if parsed.path!=ROUTE:
        return None
    if parsed.query or parsed.fragment:
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


def _promote_one(c,slot):
    if (
        slot["status"]!="open"
        or int(slot["ends_at"])<=int(time.time())
        or not _placement_enabled(c,slot["organization_id"])
    ):
        return False
    booked=int(c.execute(
        "SELECT COUNT(*) n FROM participant_partner_appointments_v1 "
        "WHERE slot_id=? AND status='booked'",
        (slot["id"],),
    ).fetchone()["n"])
    if booked>=int(slot["capacity"]):
        return False
    waiter=c.execute(
        "SELECT q.email FROM participant_partner_appointments_v1 q "
        "JOIN accounts a ON a.email=q.email "
        "WHERE q.slot_id=? AND q.status='waitlist' "
        "AND a.role='participant' AND a.status='active' "
        "ORDER BY q.requested_at,q.email LIMIT 1",
        (slot["id"],),
    ).fetchone()
    if not waiter:
        return False
    c.execute(
        "UPDATE participant_partner_appointments_v1 "
        "SET status='booked',updated_at=? "
        "WHERE slot_id=? AND email=? AND status='waitlist'",
        (int(time.time()),slot["id"],waiter["email"]),
    )
    return True


def handle_command(c,route,role,email,data):
    if route!=ROUTE:
        return None
    if not isinstance(data,dict):
        return error("invalid_request",422)
    action=data.get("action")
    now=int(time.time())

    if action=="slot_create":
        if role!="partner":
            return error("forbidden",403)
        organization_id=partner_org_scope.org_id(data.get("organization_id"))
        starts=data.get("starts_at"); ends=data.get("ends_at"); capacity=data.get("capacity")
        if (
            not organization_id
            or type(starts) is not int
            or type(ends) is not int
            or type(capacity) is not int
            or starts<=now
            or ends<=starts
            or capacity<1
            or capacity>1000
        ):
            return error("invalid_request",422)
        membership=partner_org_scope.commercial_member(c,organization_id,email)
        if membership is None or not _placement_enabled(c,organization_id):
            return error("organization_not_found",404)
        slot_id=secrets.token_hex(16)
        c.execute(
            "INSERT INTO partner_appointment_slots_v1("
            "id,organization_id,starts_at,ends_at,capacity,status,version,"
            "created_at,updated_at,created_by,demo_only"
            ") VALUES(?,?,?,?,?,'open',1,?,?,?,?)",
            (
                slot_id,organization_id,starts,ends,capacity,
                now,now,email,int(membership["demo_only"]),
            ),
        )
        slot=_slot(c,slot_id)
        return custom({"slot":dict(slot)},201)

    if action=="slot_update":
        if role!="partner":
            return error("forbidden",403)
        slot_id=data.get("slot_id")
        expected=data.get("expected_version")
        state=data.get("status")
        starts=data.get("starts_at"); ends=data.get("ends_at"); capacity=data.get("capacity")
        if (
            not isinstance(slot_id,str)
            or len(slot_id)!=32
            or type(expected) is not int
            or expected<1
            or not isinstance(state,str)
            or state not in SLOT_STATES
            or type(starts) is not int
            or type(ends) is not int
            or type(capacity) is not int
            or ends<=starts
            or (state=="open" and ends<=now)
            or capacity<1
            or capacity>1000
        ):
            return error("invalid_request",422)
        slot=_slot(c,slot_id,lock=True)
        if slot is None or partner_org_scope.commercial_member(c,slot["organization_id"],email) is None:
            return error("slot_not_found",404)
        if slot["status"]=="cancelled":
            return error("slot_cancelled",409)
        if int(slot["version"])!=expected:
            return error("version_conflict",409)
        if state=="open" and not _placement_enabled(c,slot["organization_id"]):
            return error("placement_unavailable",409)
        booked=int(c.execute(
            "SELECT COUNT(*) n FROM participant_partner_appointments_v1 "
            "WHERE slot_id=? AND status='booked'",
            (slot_id,),
        ).fetchone()["n"])
        if capacity<booked:
            return error("capacity_below_booked",409)
        changed=c.execute(
            "UPDATE partner_appointment_slots_v1 "
            "SET starts_at=?,ends_at=?,capacity=?,status=?,version=version+1,"
            "updated_at=? WHERE id=? AND version=?",
            (starts,ends,capacity,state,now,slot_id,expected),
        )
        if changed.rowcount!=1:
            return error("version_conflict",409)
        updated=_slot(c,slot_id)
        promoted=0
        for _ in range(max(0,capacity-booked)):
            if not _promote_one(c,updated):break
            promoted+=1
        return custom({"slot":dict(updated),"queuePromotions":promoted})

    if role!="participant" or _participant(c,email) is None:
        return error("forbidden",403)

    if action=="book":
        required={"action","slot_id","contact_consent"}
        if not required.issubset(data) or set(data)-required-{"expected_version"}:
            return error("invalid_request",422)
        if "expected_version" in data and (type(data['expected_version']) is not int or data['expected_version']<1):
            return error("invalid_request",422)
        slot_id=data.get("slot_id")
        if not isinstance(slot_id,str) or len(slot_id)!=32:
            return error("invalid_request",422)
        if data.get("contact_consent") is not True:
            return error("contact_consent_required",422)
        slot=_slot(c,slot_id,lock=True)
        if (
            slot is None
            or slot["status"]!="open"
            or int(slot["ends_at"])<=now
            or not _placement_enabled(c,slot["organization_id"])
        ):
            return error("slot_not_found",404)
        if 'expected_version' in data and data['expected_version']!=slot['version']:
            return error('version_conflict',409)
        own=_own_booking(c,slot_id,email)
        if own and own["status"] in ("booked","waitlist"):
            return custom({"appointment":dict(own),"replayed":True})
        booked=int(c.execute(
            "SELECT COUNT(*) n FROM participant_partner_appointments_v1 "
            "WHERE slot_id=? AND status='booked'",
            (slot_id,),
        ).fetchone()["n"])
        status="booked" if booked<int(slot["capacity"]) else "waitlist"
        if own is None:
            c.execute(
                "INSERT INTO participant_partner_appointments_v1("
                "slot_id,email,status,contact_consent_at,requested_at,updated_at"
                ") VALUES(?,?,?,?,?,?)",
                (slot_id,email,status,now,now,now),
            )
        else:
            c.execute(
                "UPDATE participant_partner_appointments_v1 "
                "SET status=?,contact_consent_at=?,requested_at=?,updated_at=? "
                "WHERE slot_id=? AND email=?",
                (status,now,now,now,slot_id,email),
            )
        current=_own_booking(c,slot_id,email)
        return custom({"appointment":dict(current),"replayed":False},201)

    if action=="cancel":
        if set(data)!={"action","slot_id"}:
            return error("invalid_request",422)
        slot_id=data.get("slot_id")
        if not isinstance(slot_id,str) or len(slot_id)!=32:
            return error("invalid_request",422)
        # Lock the parent capacity authority before reading this owner's row.
        # Concurrent duplicate cancels must not both observe an old 'booked' state.
        slot=_slot(c,slot_id,lock=True)
        own=_own_booking(c,slot_id,email)
        if own is None or own["status"]=="cancelled":
            return error("appointment_not_found",404)
        was_booked=own["status"]=="booked"
        c.execute(
            "UPDATE participant_partner_appointments_v1 "
            "SET status='cancelled',updated_at=? WHERE slot_id=? AND email=?",
            (now,slot_id,email),
        )
        promoted=_promote_one(c,slot) if was_booked and slot is not None else False
        return custom({
            "slotId":slot_id,
            "status":"cancelled",
            "queuePromotionOccurred":promoted,
        })

    return error("bad_action",400)
