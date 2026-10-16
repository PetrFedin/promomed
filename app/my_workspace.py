"""Participant-owned workspace, not an aggregate or medically approved record.

The HTTP composition layer authenticates the actor. Each read/write rechecks
active account ownership here. Callers commit or roll back; this module never
commits. Personal notes are participant-authored text, not medical facts.
"""
import re
import time
import uuid

from app import db
from app.commanding import custom, error

READ_ROUTE = "/api/my-state/v1"
PAGE_PREFIX = READ_ROUTE + "/notes/before/"
NOTE_ROUTE = READ_ROUTE + "/notes"
DELETE_ROUTE = NOTE_ROUTE + "/delete"
LOGOUT_ROUTE = READ_ROUTE + "/logout-all"
WRITE_ROUTES = frozenset((NOTE_ROUTE, DELETE_ROUTE, LOGOUT_ROUTE))
KEY = re.compile(r"^[a-f0-9]{32}$")
PAGE_SIZE = 20
MAX_NOTE_CHARS = 2000


def _account(c, role, email, *, lock=False):
    if role != "participant" or not isinstance(email, str) or not email:
        return None
    if not db.demo_seed_enabled() and email.lower().endswith("@demo.ru"):
        return None
    if lock and db.backend_name() == "sqlite" and not c.in_transaction:
        c.execute("BEGIN IMMEDIATE")
    sql = (
        "SELECT email,name FROM accounts WHERE email=? "
        "AND role='participant' AND status='active'"
    )
    if lock and db.backend_name() == "postgres":
        sql += " FOR UPDATE"
    return c.execute(sql, (email,)).fetchone()


def _notes(c, email, before=None):
    args = [email]
    where = "email=? AND deleted_at IS NULL"
    if before is not None:
        cursor = c.execute(
            "SELECT created_at,id FROM personal_notes_v1 WHERE email=? AND id=?",
            (email, before),
        ).fetchone()
        if cursor is None:
            return None
        where += " AND (created_at<? OR (created_at=? AND id<?))"
        args.extend((cursor["created_at"], cursor["created_at"], cursor["id"]))
    rows = [
        dict(r)
        for r in c.execute(
            "SELECT id,body,created_at FROM personal_notes_v1 WHERE "
            + where
            + " ORDER BY created_at DESC,id DESC LIMIT 21",
            tuple(args),
        )
    ]
    items = rows[:PAGE_SIZE]
    return {
        "items": items,
        "nextBefore": items[-1]["id"] if len(rows) > PAGE_SIZE else None,
    }


def read(c, path, role, email):
    if path != READ_ROUTE and not path.startswith(PAGE_PREFIX):
        return None
    account = _account(c, role, email)
    if account is None:
        return {"error": "forbidden"}, 403
    if path.startswith(PAGE_PREFIX):
        cursor = path[len(PAGE_PREFIX):]
        if not KEY.fullmatch(cursor):
            return {"error": "not_found"}, 404
        result = _notes(c, email, cursor)
        return (
            (result, 200)
            if result is not None
            else ({"error": "not_found"}, 404)
        )
    registration = c.execute(
        "SELECT status,ts FROM registrations WHERE email=?", (email,)
    ).fetchone()
    event_registrations = [
        dict(r)
        for r in c.execute(
            "SELECT r.event_id,e.title event_title,e.starts_at,r.status,"
            "r.requested_at,r.updated_at "
            "FROM participant_event_registrations_v1 r "
            "JOIN event_editions_v1 e ON e.id=r.event_id "
            "WHERE r.email=? ORDER BY e.starts_at,r.event_id",
            (email,),
        )
    ]
    bookings = [
        dict(r)
        for r in c.execute(
            "SELECT item_id,status,ts FROM activity_bookings WHERE email=? "
            "ORDER BY ts DESC,item_id LIMIT 51",
            (email,),
        )
    ]
    self_attendance = [
        dict(r)
        for r in c.execute(
            "SELECT a.item_id,p.title,a.status,a.checkin_ts,a.checkout_ts,a.source "
            "FROM session_attendance a "
            "LEFT JOIN program_items p ON p.id=a.item_id "
            "WHERE a.email=? AND a.source='participant_self_report' "
            "ORDER BY a.checkin_ts DESC,a.item_id LIMIT 50",
            (email,),
        )
    ]
    return {
        "version": "my-state-v1",
        "account": dict(account),
        "demoOnly": bool(db.demo_seed_enabled()),
        "registration": dict(registration) if registration else None,
        "eventRegistrations": event_registrations,
        "bookings": bookings[:50],
        "selfAttendance": self_attendance,
        "bookingsTruncated": len(bookings) > 50,
        "notes": _notes(c, email),
        "truthBoundary": {
            "ownAccountOnly": True,
            "noteSource": "participant_authored_unreviewed",
            "bookingIsAttendance": False,
            "eventRegistrationIsAttendance": False,
            "selfAttendanceIsVerifiedAttendance": False,
            "selfAttendanceCountsAsAttendanceKpi": False,
            "waitlistIsConfirmation": False,
            "publicCatalogAdmitted": False,
            "externalPilotAccepted": False,
            "medicalInference": False,
        },
    }, 200


def handle_command(c, route, role, email, data):
    if route not in WRITE_ROUTES:
        return None
    if _account(c, role, email, lock=True) is None:
        return error("forbidden", 403)
    if not isinstance(data, dict):
        return error("invalid_request", 422)

    if route == LOGOUT_ROUTE:
        if data:
            return error("invalid_request", 422)
        c.execute(
            "UPDATE auth_sessions SET revoked_at=? WHERE email=? "
            "AND revoked_at IS NULL",
            (int(time.time()), email),
        )
        return custom({"signedOut": True, "scope": "all_account_sessions"})

    if route == DELETE_ROUTE:
        if (
            set(data) != {"id"}
            or not isinstance(data["id"], str)
            or not KEY.fullmatch(data["id"])
        ):
            return error("not_found", 404)
        row = c.execute(
            "SELECT id FROM personal_notes_v1 WHERE email=? AND id=?",
            (email, data["id"]),
        ).fetchone()
        if row is None:
            return error("not_found", 404)
        # Erase text but retain request tombstone to block retry resurrection.
        c.execute(
            "UPDATE personal_notes_v1 "
            "SET body='',deleted_at=COALESCE(deleted_at,?) "
            "WHERE email=? AND id=?",
            (int(time.time()), email, data["id"]),
        )
        return custom({"deleted": True, "id": data["id"]})

    if set(data) != {"text", "request_id"}:
        return error("invalid_request", 422)
    text, request_key = data["text"], data["request_id"]
    if (
        not isinstance(text, str)
        or not isinstance(request_key, str)
        or not KEY.fullmatch(request_key)
    ):
        return error("invalid_request", 422)
    text = text.strip()
    if not text or len(text) > MAX_NOTE_CHARS or "\x00" in text:
        return error("invalid_note", 422)
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return error("invalid_note", 422)

    note_id = uuid.uuid4().hex
    c.execute(
        "INSERT INTO personal_notes_v1"
        "(id,email,request_key,body,created_at) VALUES(?,?,?,?,?) "
        "ON CONFLICT(email,request_key) DO NOTHING",
        (note_id, email, request_key, text, int(time.time())),
    )
    row = c.execute(
        "SELECT id,body,created_at,deleted_at FROM personal_notes_v1 "
        "WHERE email=? AND request_key=?",
        (email, request_key),
    ).fetchone()
    if row is None:
        raise RuntimeError("personal_note_write_not_visible")
    if row["deleted_at"] is not None:
        return error("note_deleted", 409)
    if row["body"] != text:
        return error("idempotency_conflict", 409)
    replayed = row["id"] != note_id
    note = {key: row[key] for key in ("id", "body", "created_at")}
    return custom(
        {"note": note, "replayed": replayed},
        200 if replayed else 201,
    )
