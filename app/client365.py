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
SELF_REPORTED_STATES = {"self_reported", "self_reported_complete"}
DAY_SECONDS = 86400


def _timestamp(value, now):
    """Only finite, positive and non-future observed timestamps are admissible."""
    if type(value) not in (int, float):
        return None
    ts = int(value)
    return ts if 0 < ts <= now else None


def _registration_projection(c, email, now):
    """Project current event-registration truth; legacy is a last-resort fallback.

    A waitlist, cancelled registration or cancelled edition cannot be the
    baseline for D1/D7/D30. The current row's updated_at is the recorded last
    status transition, NOT a separately attested immutable confirmation event.
    """
    rows = list(c.execute(
        """SELECT r.event_id,r.status,r.requested_at,r.updated_at,
                  e.title,e.starts_at,e.registration_status,
                  e.updated_at AS edition_updated_at,e.demo_only
           FROM participant_event_registrations_v1 r
           JOIN event_editions_v1 e ON e.id=r.event_id
           WHERE r.email=? ORDER BY r.requested_at,r.event_id""",
        (email,),
    ))
    history = []
    counts = {"confirmed": 0, "waitlist": 0, "cancelled": 0}
    confirmed = []
    titles = {
        "confirmed": "Место подтверждено",
        "waitlist": "Лист ожидания",
        "cancelled": "Регистрация отменена",
        "edition_cancelled": "Событие отменено",
    }
    for row in rows:
        # In production a demo edition never becomes a real registration fact.
        if not db.demo_seed_enabled() and int(row["demo_only"] or 0) != 0:
            continue
        status = (
            "edition_cancelled"
            if row["registration_status"] == "cancelled"
            else row["status"]
        )
        counts["cancelled" if status == "edition_cancelled" else status] += 1
        source_ts = (
            row["edition_updated_at"] if status == "edition_cancelled"
            else row["requested_at"] if status == "waitlist"
            else row["updated_at"]
        )
        ts = _timestamp(source_ts, now)
        if ts is not None:
            history.append({
                "id": "event-registration:" + row["event_id"],
                "kind": "registration",
                "title": titles[status] + ": " + row["title"],
                "observedAt": ts,
                "source": "participant_event_registrations_v1",
                "assurance": "current_status_record_not_attendance",
                "eventId": row["event_id"],
                "registrationStatus": status,
            })
        if status == "confirmed":
            confirmation = _timestamp(row["updated_at"], now)
            if confirmation is not None:
                confirmed.append((confirmation, row["event_id"]))

    # Even a waitlisted/cancelled or hidden canonical record suppresses a
    # misleading older legacy "confirmed" record for this same account.
    if rows:
        earliest = min(confirmed) if confirmed else None
        return (
            earliest[0] if earliest else None,
            "event_registration_v1",
            earliest[1] if earliest else None,
            history,
            counts,
        )

    legacy = c.execute(
        "SELECT status,ts FROM registrations WHERE email=?", (email,)
    ).fetchone()
    legacy_ts = (
        _timestamp(legacy["ts"], now)
        if legacy is not None and legacy["status"] == "confirmed"
        else None
    )
    if legacy_ts is not None:
        history.append({
            "id": "registration",
            "kind": "registration",
            "title": "Историческая регистрация (прежний контур)",
            "observedAt": legacy_ts,
            "source": "registrations",
            "assurance": "legacy_application_record_not_event_admission",
        })
    return (
        legacy_ts,
        "legacy_registrations" if legacy is not None else "none",
        None,
        history,
        counts,
    )


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

    (registered_at, registration_source, baseline_event_id,
     registration_events, event_registration_counts) = _registration_projection(
        c, email, now
    )
    events = list(registration_events)

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
    participant_self_reports = 0
    for a in rows:
        ts = _timestamp(a["checkin_ts"], now)
        if not ts:
            continue
        self_report = (
            a["source"] == "participant_self_report"
            and a["status"] in SELF_REPORTED_STATES
        )
        if not self_report and a["status"] not in ATTENDED_STATES:
            continue
        internal_staff = a["source"] in STAFF_SOURCES and not self_report
        if self_report:
            participant_self_reports += 1
        elif internal_staff:
            staff_recorded += 1
        else:
            self_recorded += 1
        events.append({
            "id": "attendance:" + a["item_id"],
            "kind": "attendance",
            "title": (
                "Самостоятельная отметка: " if self_report
                else "Посещение отмечено: "
            ) + (a["title"] or a["item_id"]),
            "observedAt": ts, "source": "session_attendance",
            "assurance": (
                "staff_recorded_not_independently_verified"
                if internal_staff else "participant_self_report_not_verified"
                if self_report else "self_recorded_not_verified"
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
        "registrationSource": registration_source,
        "registrationBaselineEventId": baseline_event_id,
        "registrationTimeBasis": (
            "last_status_update_not_immutable_confirmation"
            if registration_source == "event_registration_v1"
            else "legacy_registration_timestamp"
            if registration_source == "legacy_registrations"
            else "none"
        ),
        "events": events[:80],
        "followups": planned,
        "milestones": milestones,
        "counts": {
            "eventRegistrationsConfirmed": event_registration_counts["confirmed"],
            "eventRegistrationsWaitlist": event_registration_counts["waitlist"],
            "eventRegistrationsCancelled": event_registration_counts["cancelled"],
            "activeBookings": booked_count,
            "waitlist": waitlist_count,
            "staffRecordedAttendance": staff_recorded,
            "selfRecordedAttendance": self_recorded,
            "participantSelfReports": participant_self_reports,
            "savedTakeaways": note_count,
            "recordedAccountActions": len(explicit_actions),
            "informationRequests": int(consent),
        },
        "truthBoundary": {
            "ownAccountOnly": True,
            "timeWindowOrigin": "registration_not_event_date",
            "scheduledFollowupsAreNotReturns": True,
            "canonicalEventRegistrationOverridesLegacy": True,
            "waitlistOrCancelledIsNotConfirmed": True,
            "registrationIsNotAttendance": True,
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


def serve(actor, raw_path):
    """Open the source DB only for scoped read; never mutate a lifecycle row."""
    c=db.connect()
    try:
        return read(c,actor,raw_path)
    finally:
        c.close()
