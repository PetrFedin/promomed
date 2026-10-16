"""Capacity-aware, participant-owned event registration.

Identity/account creation and event registration are deliberately separate.
This module never infers attendance, consent, retention or commercial value.
"""
import calendar
import time
from urllib.parse import urlparse

from app import db
from app.commanding import custom, error

ROUTE = "/api/event-registration/v1"
DEMO_EVENT_ID = "SOSTOYANIE-2027"


def seed_demo(c):
    if not db.demo_seed_enabled():
        return
    now = int(time.time())
    starts = calendar.timegm((2027, 4, 24, 7, 0, 0))
    c.execute(
        "INSERT OR IGNORE INTO event_editions_v1("
        "id,title,starts_at,registration_status,capacity,demo_only,created_at,updated_at"
        ") VALUES(?,?,?,'open',600,1,?,?)",
        (DEMO_EVENT_ID, "СОСТОЯНИЕ / 2027", starts, now, now),
    )


def _account(c, role, email):
    if role != "participant" or not isinstance(email, str) or not email:
        return None
    return c.execute(
        "SELECT email FROM accounts WHERE email=? "
        "AND role='participant' AND status='active'",
        (email,),
    ).fetchone()


def _event(c, event_id, *, lock=False):
    if lock and db.backend_name() == "sqlite" and not c.in_transaction:
        c.execute("BEGIN IMMEDIATE")
    sql = (
        "SELECT id,title,starts_at,registration_status,capacity,demo_only "
        "FROM event_editions_v1 WHERE id=?"
    )
    if lock and db.backend_name() == "postgres":
        sql += " FOR UPDATE"
    row = c.execute(sql, (event_id,)).fetchone()
    if row and not db.demo_seed_enabled() and int(row["demo_only"] or 0) != 0:
        return None
    return row


def _own(c, event_id, email):
    return c.execute(
        "SELECT event_id,status,requested_at,updated_at "
        "FROM participant_event_registrations_v1 "
        "WHERE event_id=? AND email=?",
        (event_id, email),
    ).fetchone()


def _public_registration(event, row):
    return {
        "eventId": event["id"],
        "eventTitle": event["title"],
        "startsAt": event["starts_at"],
        "status": row["status"] if row else None,
        "requestedAt": row["requested_at"] if row else None,
        "updatedAt": row["updated_at"] if row else None,
        "attendance": None,
        "marketingConsent": False,
        "medicalConsent": False,
    }


def read(c, raw_path, role, email):
    parsed = urlparse(raw_path)
    if parsed.path != ROUTE:
        return None
    if parsed.query or parsed.fragment:
        return {"error": "unsupported_query"}, 422
    if _account(c, role, email) is None:
        return {"error": "forbidden"}, 403

    rows = c.execute(
        "SELECT e.id,e.title,e.starts_at,e.registration_status,e.capacity,e.demo_only,"
        "r.status,r.requested_at,r.updated_at "
        "FROM event_editions_v1 e "
        "LEFT JOIN participant_event_registrations_v1 r "
        "ON r.event_id=e.id AND r.email=? "
        "WHERE e.registration_status<>'cancelled' ORDER BY e.starts_at,e.id",
        (email,),
    )
    events = []
    for row in rows:
        if not db.demo_seed_enabled() and int(row["demo_only"] or 0) != 0:
            continue
        events.append({
            "eventId": row["id"],
            "eventTitle": row["title"],
            "startsAt": row["starts_at"],
            "registrationStatus": row["registration_status"],
            "capacity": row["capacity"],
            "myStatus": row["status"],
            "requestedAt": row["requested_at"],
            "updatedAt": row["updated_at"],
        })
    return {
        "version": "event-registration-v1",
        "events": events,
        "truthBoundary": {
            "accountCreationIsNotEventRegistration": True,
            "registrationIsNotAttendance": True,
            "waitlistIsNotConfirmation": True,
            "marketingConsent": False,
            "medicalConsent": False,
            "partnerLead": False,
        },
    }, 200


def serve(actor, raw_path):
    if not actor:
        return {"error": "unauthorized"}, 401
    c = db.connect()
    try:
        return read(c, raw_path, actor[0], actor[2])
    finally:
        c.close()


def _promote_one(c, event):
    if event["registration_status"] != "open":
        return False
    confirmed = int(c.execute(
        "SELECT COUNT(*) n FROM participant_event_registrations_v1 "
        "WHERE event_id=? AND status='confirmed'",
        (event["id"],),
    ).fetchone()["n"])
    if confirmed >= int(event["capacity"]):
        return False
    waiter = c.execute(
        "SELECT email FROM participant_event_registrations_v1 "
        "WHERE event_id=? AND status='waitlist' "
        "ORDER BY requested_at,email LIMIT 1",
        (event["id"],),
    ).fetchone()
    if not waiter:
        return False
    c.execute(
        "UPDATE participant_event_registrations_v1 "
        "SET status='confirmed',updated_at=? WHERE event_id=? AND email=? "
        "AND status='waitlist'",
        (int(time.time()), event["id"], waiter["email"]),
    )
    return True


def handle_command(c, route, role, email, data):
    if route != ROUTE:
        return None
    if _account(c, role, email) is None:
        return error("forbidden", 403)
    if not isinstance(data, dict) or set(data) != {"event_id", "action"}:
        return error("invalid_request", 422)
    event_id = data.get("event_id")
    action = data.get("action")
    if (
        not isinstance(event_id, str)
        or not 1 <= len(event_id) <= 64
        or any(ch.isspace() for ch in event_id)
        or action not in ("register", "cancel")
    ):
        return error("invalid_request", 422)

    event = _event(c, event_id, lock=True)
    if event is None:
        return error("event_not_found", 404)
    now = int(time.time())
    own = _own(c, event_id, email)

    if action == "cancel":
        if own is None or own["status"] == "cancelled":
            return error("registration_not_found", 404)
        was_confirmed = own["status"] == "confirmed"
        c.execute(
            "UPDATE participant_event_registrations_v1 "
            "SET status='cancelled',updated_at=? WHERE event_id=? AND email=?",
            (now, event_id, email),
        )
        promoted = _promote_one(c, event) if was_confirmed else False
        current = _own(c, event_id, email)
        return custom({
            "registration": _public_registration(event, current),
            "queuePromotionOccurred": promoted,
        })

    if event["registration_status"] in ("closed", "cancelled"):
        return error("registration_closed", 409)

    if own is not None and own["status"] in ("confirmed", "waitlist"):
        return custom({
            "registration": _public_registration(event, own),
            "replayed": True,
        })

    confirmed = int(c.execute(
        "SELECT COUNT(*) n FROM participant_event_registrations_v1 "
        "WHERE event_id=? AND status='confirmed'",
        (event_id,),
    ).fetchone()["n"])
    status = (
        "confirmed"
        if event["registration_status"] == "open"
        and confirmed < int(event["capacity"])
        else "waitlist"
    )
    if own is None:
        c.execute(
            "INSERT INTO participant_event_registrations_v1("
            "event_id,email,status,requested_at,updated_at,source"
            ") VALUES(?,?,?,?,?,'participant')",
            (event_id, email, status, now, now),
        )
    else:
        c.execute(
            "UPDATE participant_event_registrations_v1 "
            "SET status=?,requested_at=?,updated_at=?,source='participant' "
            "WHERE event_id=? AND email=?",
            (status, now, now, event_id, email),
        )
    current = _own(c, event_id, email)
    return custom({
        "registration": _public_registration(event, current),
        "replayed": False,
    }, 201)
