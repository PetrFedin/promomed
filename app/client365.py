"""Client Relationship 365: participant-owned, source-labelled, read-only facts.

Do not infer retention, medical status or financial impact from a demonstration,
a scheduled follow-up, a self-reported attendance or an enrollment.
"""
import time
from urllib.parse import urlparse
from app import db

OBSERVED_KINDS = {
    "replay_opened": "Открыта запись события",
    "takeaway_saved": "Сохранён личный вывод",
    "learning_enrolled": "Начата образовательная программа",
    "learning_advanced": "Выполнен шаг образовательной программы",
    "discovery_saved": "Сохранён материал",
    "session_feedback": "Отправлен отзыв",
}
STAFF_SOURCES = {"staff", "organizer"}
ATTENDED_STATES = {"present", "completed", "checked_in", "attended", "complete"}
DAY_SECONDS = 86400


def _timestamp(value, now):
    """Only finite, positive and non-future observed timestamps are admissible."""
    if type(value) not in (int, float):
        return None
    ts = int(value)
    return ts if 0 < ts <= now else None


def snapshot(c, email, now=None):
    if not isinstance(email, str) or not email:
        raise ValueError("participant_identity_required")
    now = int(time.time()) if now is None else int(now)
    demo = bool(db.demo_seed_enabled() or email.lower().endswith("@demo.ru"))

    account = c.execute(
        "SELECT role,status FROM accounts WHERE email=?", (email,)
    ).fetchone()
    if not account or account["role"] != "participant" or account["status"] != "active":
        raise PermissionError("participant_account_not_active")

    registration = c.execute(
        "SELECT status,ts FROM registrations WHERE email=?", (email,)
    ).fetchone()
    registered_at = (
        _timestamp(registration["ts"], now)
        if registration and registration["status"] == "confirmed" else None
    )

    events = []
    if registered_at:
        events.append({
            "id": "registration", "kind": "registration",
            "title": "Регистрация подтверждена системой",
            "observedAt": registered_at,
            "source": "registrations", "assurance": "application_record",
        })

    bookings = c.execute(
        """SELECT b.item_id,b.status,b.ts,p.title,p.venue
           FROM activity_bookings b
           LEFT JOIN program_items p ON p.id=b.item_id
           WHERE b.email=? ORDER BY b.ts DESC,b.item_id LIMIT 50""",
        (email,),
    )
    booked_count = 0
    waitlist_count = 0
    for b in bookings:
        ts = _timestamp(b["ts"], now)
        if not ts:
            continue
        if b["status"] in ("booked", "confirmed"):
            booked_count += 1
            status = "Запись сохранена"
        elif b["status"] == "waitlist":
            waitlist_count += 1
            status = "Лист ожидания"
        else:
            continue
        events.append({
            "id": "booking:" + b["item_id"],
            "kind": "booking",
            "title": status + ": " + (b["title"] or b["item_id"]),
            "observedAt": ts, "source": "activity_bookings",
            "assurance": "recorded_booking_not_attendance",
        })

    rows = c.execute(
        """SELECT a.item_id,a.status,a.checkin_ts,a.source,p.title
           FROM session_attendance a
           LEFT JOIN program_items p ON p.id=a.item_id
           WHERE a.email=? ORDER BY a.checkin_ts DESC,a.item_id LIMIT 50""",
        (email,),
    )
    staff_recorded = 0
    self_recorded = 0
    for a in rows:
        ts = _timestamp(a["checkin_ts"], now)
        if not ts or a["status"] not in ATTENDED_STATES:
            continue
        internal_staff = a["source"] in STAFF_SOURCES
        if internal_staff:
            staff_recorded += 1
        else:
            self_recorded += 1
        events.append({
            "id": "attendance:" + a["item_id"],
            "kind": "attendance",
            "title": "Посещение отмечено: " + (a["title"] or a["item_id"]),
            "observedAt": ts, "source": "session_attendance",
            "assurance": (
                "staff_recorded_not_independently_verified"
                if internal_staff else "self_recorded_not_verified"
            ),
        })

    saved_notes = c.execute(
        "SELECT id,session_id,ts FROM takeaways WHERE email=? ORDER BY ts DESC,id DESC LIMIT 30",
        (email,),
    )
    note_count = 0
    for n in saved_notes:
        ts = _timestamp(n["ts"], now)
        if not ts:
            continue
        note_count += 1
        events.append({
            "id": "takeaway:" + str(n["id"]),
            "kind": "takeaway",
            "title": "Сохранён собственный вывод" + (
                " · " + n["session_id"] if n["session_id"] else ""
            ),
            "observedAt": ts, "source": "takeaways",
            "assurance": "participant_saved_not_medically_reviewed",
        })

    action_rows = c.execute(
        "SELECT id,kind,ts FROM events WHERE actor=? ORDER BY ts DESC,id DESC LIMIT 250",
        (email,),
    )
    explicit_actions = []
    for action in action_rows:
        if action["kind"] not in OBSERVED_KINDS:
            continue
        ts = _timestamp(action["ts"], now)
        if not ts:
            continue
        explicit_actions.append((action["id"], action["kind"], ts))
        events.append({
            "id": "activity:" + str(action["id"]),
            "kind": action["kind"],
            "title": OBSERVED_KINDS[action["kind"]],
            "observedAt": ts, "source": "events",
            "assurance": "account_action_recorded_not_externally_verified",
        })

    planned = []
    rows = c.execute(
        "SELECT day,track,status,ts FROM followups WHERE email=? ORDER BY day,ts LIMIT 60",
        (email,),
    )
    for r in rows:
        if r["day"] not in (1, 7, 30):
            continue
        planned.append({
            "day": r["day"], "topic": r["track"] or "",
            "recordStatus": r["status"],
            "isEvidenceOfReturn": False,
            "source": "followups",
        })

    milestones = []
    for day in (1, 7, 30):
        threshold = registered_at + day * DAY_SECONDS if registered_at else None
        due = threshold is not None and now >= threshold
        hits = [
            "activity:" + str(event_id)
            for event_id, kind, ts in explicit_actions
            if due and ts >= threshold
        ]
        milestones.append({
            "day": day,
            "baseline": "registration_timestamp",
            "eligibleAt": threshold,
            "state": (
                "no_registration_baseline" if not registered_at
                else "not_due" if not due
                else "observed_account_activity" if hits
                else "no_observed_account_activity"
            ),
            "recordedActionCount": len(hits),
            "sourceRefs": hits[:20],
            "externallyVerifiedRetention": False,
        })

    events.sort(key=lambda e: (e["observedAt"], e["id"]), reverse=True)
    consent = c.execute(
        "SELECT COUNT(*) n FROM product_interests WHERE email=? AND status='requested'",
        (email,),
    ).fetchone()["n"]

    return {
        "mode": "client365_account_activity_v1",
        "demoOnly": demo,
        "registeredAt": registered_at,
        "events": events[:80],
        "followups": planned,
        "milestones": milestones,
        "counts": {
            "activeBookings": booked_count,
            "waitlist": waitlist_count,
            "staffRecordedAttendance": staff_recorded,
            "selfRecordedAttendance": self_recorded,
            "savedTakeaways": note_count,
            "recordedAccountActions": len(explicit_actions),
            "informationRequests": int(consent),
        },
        "truthBoundary": {
            "ownAccountOnly": True,
            "timeWindowOrigin": "registration_not_event_date",
            "scheduledFollowupsAreNotReturns": True,
            "selfCheckinIsNotVerifiedAttendance": True,
            "staffRecordIsNotIndependentAttendanceProof": True,
            "productInterestIsNotPartnerMarketingConsent": True,
            "medicalInference": False,
            "cohortRetentionRate": None,
            "recognizedRevenue": None,
            "externalAcceptance": False,
        },
    }


def read(c, actor, raw_path):
    parsed = urlparse(raw_path)
    if parsed.path != "/api/client-365":
        return None
    if not actor:
        return {"error": "unauthorized"}, 401
    if actor[0] != "participant":
        return {"error": "forbidden"}, 403
    if parsed.query:
        # Never accept an email, account or user selector from the client.
        return {"error": "unsupported_client_365_query"}, 422
    try:
        return snapshot(c, actor[2]), 200
    except PermissionError:
        return {"error": "forbidden"}, 403
    except ValueError:
        return {"error": "invalid_identity"}, 422
