"""Participant-owned unified calendar projection; no new booking authority.

Only source-dated event editions and partner slots are combined. Programme
items with clock-only start/end values are deliberately excluded until a
canonical event date and timezone exist. No medical, marketing or attendance
inference is derived from these records.
"""
from datetime import datetime, timezone
import hashlib
import time
from urllib.parse import urlparse

from app import db

ROUTE = "/api/participant-agenda/v1"
MAX_ROWS = 200


def _account(c, role, email):
    if role != "participant" or not isinstance(email, str) or not email:
        return False
    if not db.demo_seed_enabled() and email.lower().endswith("@demo.ru"):
        return False
    return bool(c.execute(
        "SELECT 1 FROM accounts WHERE email=? AND role='participant' "
        "AND status='active'", (email,),
    ).fetchone())


def _positive_time(value):
    return int(value) if type(value) is int and value > 0 else None


def _event_rows(c, email, now):
    rows = list(c.execute(
        "SELECT e.id,e.title,e.starts_at,e.registration_status,e.demo_only,"
        "r.status AS my_status "
        "FROM participant_event_registrations_v1 r "
        "JOIN event_editions_v1 e ON e.id=r.event_id "
        "WHERE r.email=? ORDER BY e.starts_at DESC,e.id DESC LIMIT 201",
        (email,),
    ))
    truncated = len(rows) > MAX_ROWS
    result = []
    for row in rows[:MAX_ROWS]:
        if not db.demo_seed_enabled() and int(row["demo_only"] or 0):
            continue
        start = _positive_time(row["starts_at"])
        if start is None:
            continue
        cancelled = row["registration_status"] == "cancelled"
        status = (
            "unavailable" if cancelled and row["my_status"] != "cancelled"
            else row["my_status"]
        )
        current = status == "confirmed" and start > now
        result.append({
            "id": "event:" + row["id"],
            "kind": "event_edition",
            "title": row["title"],
            "startsAt": start,
            "endsAt": None,
            "timePrecision": "start_only",
            "state": status,
            "calendarEligible": current,
            "source": "participant_event_registrations_v1",
            "attendanceClaimed": False,
        })
    return result, truncated


def _appointment_rows(c, email, now):
    rows = list(c.execute(
        "SELECT b.slot_id,b.status AS booking_status,"
        "s.starts_at,s.ends_at,s.status AS slot_status,s.demo_only,"
        "o.name AS organization_name,o.status AS org_status,"
        "o.partner_id,o.demo_only AS org_demo_only,"
        "p.status AS placement_status,p.demo_only AS placement_demo_only "
        "FROM participant_partner_appointments_v1 b "
        "JOIN partner_appointment_slots_v1 s ON s.id=b.slot_id "
        "JOIN institutional_organizations o ON o.id=s.organization_id "
        "LEFT JOIN partner_commercial_placements_v1 p ON p.organization_id=o.id "
        "WHERE b.email=? ORDER BY s.starts_at DESC,b.slot_id DESC LIMIT 201",
        (email,),
    ))
    truncated = len(rows) > MAX_ROWS
    result = []
    for row in rows[:MAX_ROWS]:
        if not db.demo_seed_enabled() and int(row["demo_only"] or 0):
            continue
        start, end = _positive_time(row["starts_at"]), _positive_time(row["ends_at"])
        if start is None or end is None or end <= start:
            continue
        admitted = (
            row["org_status"] == "active"
            and isinstance(row["partner_id"], str)
            and bool(row["partner_id"].strip())
            and int(row["demo_only"]) == int(row["org_demo_only"])
            and row["placement_status"] == "enabled"
            and row["placement_demo_only"] is not None
            and int(row["demo_only"]) == int(row["placement_demo_only"])
            and row["slot_status"] in ("open", "closed")
        )
        state = (
            "cancelled" if row["booking_status"] == "cancelled"
            else "unavailable" if not admitted
            else row["booking_status"]
        )
        result.append({
            "id": "appointment:" + row["slot_id"],
            "kind": "partner_appointment",
            "title": "Встреча · " + (row["organization_name"] or "Партнёр"),
            "startsAt": start,
            "endsAt": end,
            "timePrecision": "exact_interval",
            "state": state,
            "calendarEligible": state == "booked" and end > now,
            "source": "participant_partner_appointments_v1",
            "attendanceClaimed": False,
        })
    return result, truncated


def _conflicts(items):
    """Only known partner appointment intervals can prove overlaps."""
    appointments = [
        item for item in items
        if item["kind"] == "partner_appointment"
        and item["state"] == "booked" and item["calendarEligible"]
        and item["endsAt"] is not None
    ]
    appointments.sort(key=lambda x: (x["startsAt"], x["id"]))
    conflicts = []
    for index, first in enumerate(appointments):
        for other in appointments[index + 1:]:
            if other["startsAt"] >= first["endsAt"]:
                break
            if first["startsAt"] < other["endsAt"]:
                conflicts.append({
                    "first": first["id"],
                    "second": other["id"],
                    "kind": "known_interval_overlap",
                })
    return conflicts


def _escape(value):
    # Escape untrusted titles before constructing an RFC 5545 TEXT field.
    value = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    value = "".join(ch for ch in value if ch == "\n" or ord(ch) >= 32)
    return (value.replace("\\", "\\\\").replace("\n", "\\n")
            .replace(",", "\\,").replace(";", "\\;"))


def _fold(line):
    """Fold iCalendar content lines at <=75 UTF-8 octets."""
    parts, current, width = [], "", 0
    for char in line:
        octets = len(char.encode("utf-8"))
        if width + octets > 75:
            parts.append(current)
            current, width = " " + char, 1 + octets
        else:
            current += char
            width += octets
    parts.append(current)
    return "\r\n".join(parts)


def _utc(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _ics(items, now):
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0",
        "PRODID:-//SOSTOYANIE//Participant Agenda V1//RU",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
    ]
    for item in items:
        if not item["calendarEligible"]:
            continue
        uid = hashlib.sha256(item["id"].encode("utf-8")).hexdigest()[:32]
        lines += [
            "BEGIN:VEVENT", "UID:" + uid + "@sostoyanie.invalid",
            "DTSTAMP:" + _utc(now),
            "DTSTART:" + _utc(item["startsAt"]),
        ]
        if item["endsAt"] is not None:
            lines.append("DTEND:" + _utc(item["endsAt"]))
        lines.append("SUMMARY:" + _escape(item["title"]))
        desc = (
            "Подтверждённая запись, не доказательство посещения."
            if item["endsAt"] is not None
            else "Начало мероприятия; время окончания не указано."
        )
        lines.append("DESCRIPTION:" + _escape(desc))
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def snapshot(c, email, now=None):
    now = int(time.time()) if now is None else int(now)
    events, events_truncated = _event_rows(c, email, now)
    appointments, appointments_truncated = _appointment_rows(c, email, now)
    combined = sorted(
        events + appointments,
        key=lambda item: (item["startsAt"], item["kind"], item["id"]),
    )
    return {
        "version": "participant-agenda-v1",
        "items": combined,
        "conflicts": _conflicts(combined),
        "calendarIcs": _ics(combined, now),
        "truncated": events_truncated or appointments_truncated,
        "truthBoundary": {
            "ownAccountOnly": True,
            "bookingsAreNotAttendance": True,
            "waitlistNeverExportedAsConfirmed": True,
            "unavailablePartnerNeverExportedAsConfirmed": True,
            "eventEndNeverInvented": True,
            "programmeClockOnlyExcluded": True,
            "medicalInference": False,
            "contactExported": False,
        },
    }


def read(c, raw_path, role, email):
    parsed = urlparse(raw_path)
    if parsed.path != ROUTE:
        return None
    if parsed.query or parsed.fragment:
        return {"error": "unsupported_query"}, 422
    if not _account(c, role, email):
        return {"error": "forbidden"}, 403
    return snapshot(c, email), 200


def serve(actor, raw_path):
    if not actor:
        return {"error": "unauthorized"}, 401
    c = db.connect()
    try:
        return read(c, raw_path, actor[0], actor[2])
    finally:
        c.close()
