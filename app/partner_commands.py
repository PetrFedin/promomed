import time

from app.commanding import error, ok
from app.core import audit, notify

ROUTES = {
    "/api/appointment-booking",
    "/api/appointment-manage",
    "/api/placement",
    "/api/lead",
}


def handle_command(c, route, role, email, data):
    if route not in ROUTES:
        return None

    if route == "/api/placement":
        if role != "partner":
            return error("forbidden", 403)
        status = str(data.get("status", "active"))
        if status not in ("contracted", "active", "ended"):
            return error("bad_status", 400)
        c.execute("UPDATE placements SET status=?,ts=? WHERE id=1", (status, int(time.time())))
        audit(c, "placement_" + status, email, {})
        return ok()

    if route == "/api/lead":
        if role != "participant":
            return error("forbidden", 403)
        if data.get("consent") is not True:
            return error("consent_required", 422)
        kind = str(data.get("kind", "materials"))
        c.execute("INSERT INTO leads(kind,status,ts) VALUES(?,'new',?)", (kind, int(time.time())))
        c.execute("UPDATE placements SET leads=leads+1 WHERE id=1")
        audit(c, "voluntary_lead", email, {"kind": kind, "consent": True})
        return ok()

    if role != "participant":
        return error("forbidden", 403)

    if route == "/api/appointment-booking":
        slot_id = str(data.get("slot_id", ""))[:20]
        slot = c.execute(
            "SELECT a.*,p.title,p.venue FROM appointment_slots a JOIN program_items p ON p.id=a.item_id WHERE a.id=?",
            (slot_id,),
        ).fetchone()
        if not slot:
            return error("slot_not_found", 404)
        conflict = c.execute(
            "SELECT 1 FROM activity_bookings b JOIN program_items p ON p.id=b.item_id "
            "WHERE b.email=? AND b.status='booked' AND p.start<? AND p.\"end\">?",
            (email, slot["end"], slot["start"]),
        ).fetchone()
        if conflict:
            return error("schedule_conflict", 409)
        used = c.execute(
            "SELECT COUNT(*) n FROM appointment_bookings WHERE slot_id=? AND status='booked'",
            (slot_id,),
        ).fetchone()["n"]
        status = "booked" if used < int(slot["capacity"]) else "waitlist"
        c.execute(
            "INSERT INTO appointment_bookings(email,slot_id,status,ts) VALUES(?,?,?,?) "
            "ON CONFLICT(email,slot_id) DO UPDATE SET status=excluded.status,ts=excluded.ts",
            (email, slot_id, status, int(time.time())),
        )
        audit(c, "appointment_" + status, email, {"slot_id": slot_id, "item_id": slot["item_id"]})
        partner_name = c.execute(
            "SELECT pr.name FROM appointment_slots a JOIN partners pr ON pr.id=a.partner_id WHERE a.id=?",
            (slot_id,),
        ).fetchone()
        c.execute(
            "INSERT INTO partner_engagement(email,partner,kind,ref_id,consent,ts) VALUES(?,?,?,?,0,?)",
            (email, partner_name["name"] if partner_name else "partner", "appointment_" + status, slot_id, int(time.time())),
        )
        notify(c, email, "appointment_" + status, "Запись к партнёру", slot["start"] + " · " + slot["venue"] + " · " + slot["title"])
        return ok()

    action = str(data.get("action", "cancel"))
    slot_id = str(data.get("slot_id", ""))[:20]
    row = c.execute(
        'SELECT b.status,a.start,a."end",a.item_id FROM appointment_bookings b '
        'JOIN appointment_slots a ON a.id=b.slot_id WHERE b.email=? AND b.slot_id=?',
        (email, slot_id),
    ).fetchone()
    if not row:
        return error("appointment_not_found", 404)

    if action == "cancel":
        was_booked = row["status"] == "booked"
        c.execute("UPDATE appointment_bookings SET status='cancelled',ts=? WHERE email=? AND slot_id=?", (int(time.time()), email, slot_id))
        c.execute(
            "INSERT INTO appointment_history(email,slot_id,action,from_slot,to_slot,ts) VALUES(?,?, 'cancel', ?, NULL, ?)",
            (email, slot_id, slot_id, int(time.time())),
        )
        if was_booked:
            waiter = c.execute(
                "SELECT email FROM appointment_bookings WHERE slot_id=? AND status='waitlist' ORDER BY ts LIMIT 1",
                (slot_id,),
            ).fetchone()
            if waiter:
                c.execute(
                    "UPDATE appointment_bookings SET status='booked',ts=? WHERE email=? AND slot_id=?",
                    (int(time.time()), waiter["email"], slot_id),
                )
                notify(c, waiter["email"], "appointment_promoted", "Освободилось место", "Ваша запись к партнёру подтверждена.")
                audit(c, "appointment_waitlist_promoted", waiter["email"], {"slot_id": slot_id})
        audit(c, "appointment_cancelled", email, {"slot_id": slot_id})
        return ok()

    if action != "reschedule":
        return error("bad_action", 400)

    to_slot = str(data.get("to_slot", ""))[:20]
    target = c.execute("SELECT * FROM appointment_slots WHERE id=?", (to_slot,)).fetchone()
    if not target:
        return error("slot_not_found", 404)
    conflict = c.execute(
        'SELECT p.id,p.title,p.start,p."end",p.venue FROM activity_bookings b '
        'JOIN program_items p ON p.id=b.item_id '
        "WHERE b.email=? AND b.status='booked' AND p.start<? AND p.\"end\">?",
        (email, target["end"], target["start"]),
    ).fetchone()
    if conflict:
        return error(
            "schedule_conflict",
            409,
            conflict=dict(conflict),
            requested={"slot_id": to_slot, "start": target["start"], "end": target["end"]},
        )
    used = c.execute(
        "SELECT COUNT(*) n FROM appointment_bookings WHERE slot_id=? AND status='booked'",
        (to_slot,),
    ).fetchone()["n"]
    if used >= int(target["capacity"]):
        return error("slot_full", 409)

    was_booked = row["status"] == "booked"
    c.execute("UPDATE appointment_bookings SET status='cancelled',ts=? WHERE email=? AND slot_id=?", (int(time.time()), email, slot_id))
    if was_booked:
        waiter = c.execute(
            "SELECT email FROM appointment_bookings WHERE slot_id=? AND status='waitlist' ORDER BY ts LIMIT 1",
            (slot_id,),
        ).fetchone()
        if waiter:
            c.execute(
                "UPDATE appointment_bookings SET status='booked',ts=? WHERE email=? AND slot_id=?",
                (int(time.time()), waiter["email"], slot_id),
            )
            notify(c, waiter["email"], "appointment_promoted", "Освободилось место", "Ваша запись к партнёру подтверждена.")
    c.execute(
        "INSERT INTO appointment_bookings(email,slot_id,status,ts) VALUES(?,?,'booked',?) "
        "ON CONFLICT(email,slot_id) DO UPDATE SET status='booked',ts=excluded.ts",
        (email, to_slot, int(time.time())),
    )
    c.execute(
        "INSERT INTO appointment_history(email,slot_id,action,from_slot,to_slot,ts) VALUES(?,?, 'reschedule', ?, ?, ?)",
        (email, to_slot, slot_id, to_slot, int(time.time())),
    )
    notify(c, email, "appointment_rescheduled", "Запись перенесена", target["start"] + "–" + target["end"])
    audit(c, "appointment_rescheduled", email, {"from": slot_id, "to": to_slot})
    return ok()
