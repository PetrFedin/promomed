import time

from app.commanding import custom, error, ok
from app.core import audit, notify, promote_waitlist, setv, sval

ROUTES = {
    "/api/register",
    "/api/booking",
    "/api/activity-booking",
    "/api/replay",
    "/api/session-attendance",
}


def handle_command(c, route, role, email, data):
    if route not in ROUTES:
        return None

    if route == "/api/register":
        if role != "participant":
            return error("forbidden", 403)
        c.execute("INSERT OR REPLACE INTO registrations(email,status,ts) VALUES(?,'confirmed',?)", (email, int(time.time())))
        audit(c, "registration", email, {})
        return ok()

    if route == "/api/booking":
        if role != "participant":
            return error("forbidden", 403)
        sid = str(data.get("session_id", "S2"))
        action = str(data.get("action", "book"))
        if action == "cancel":
            old = c.execute("SELECT status FROM bookings WHERE email=? AND session_id=?", (email, sid)).fetchone()
            c.execute("DELETE FROM bookings WHERE email=? AND session_id=?", (email, sid))
            if old and old["status"] == "booked":
                setv(c, "occupied", max(0, int(sval(c, "occupied", "0")) - 1))
                promote_waitlist(c, sid)
            audit(c, "booking_cancelled", email, {"session_id": sid})
        else:
            existing = c.execute("SELECT status FROM bookings WHERE email=? AND session_id=?", (email, sid)).fetchone()
            if not existing:
                status = "booked" if int(sval(c, "occupied", "0")) < int(sval(c, "capacity", "120")) else "waitlist"
                c.execute("INSERT INTO bookings(email,session_id,status,ts) VALUES(?,?,?,?)", (email, sid, status, int(time.time())))
                if status == "booked":
                    setv(c, "occupied", int(sval(c, "occupied", "0")) + 1)
                audit(c, "booking_" + status, email, {"session_id": sid})
        return ok()

    if route == "/api/activity-booking":
        if role != "participant":
            return error("forbidden", 403)
        item_id = str(data.get("item_id", ""))[:20]
        action = str(data.get("action", "book"))
        item = c.execute("SELECT * FROM program_items WHERE id=?", (item_id,)).fetchone()
        if not item:
            return error("program_item_not_found", 404)
        if action == "cancel":
            old = c.execute("SELECT status FROM activity_bookings WHERE email=? AND item_id=?", (email, item_id)).fetchone()
            c.execute("DELETE FROM activity_bookings WHERE email=? AND item_id=?", (email, item_id))
            if old and old["status"] == "booked":
                waiter = c.execute(
                    "SELECT email FROM activity_bookings WHERE item_id=? AND status='waitlist' ORDER BY ts,email LIMIT 1",
                    (item_id,),
                ).fetchone()
                if waiter:
                    c.execute(
                        "UPDATE activity_bookings SET status='booked',ts=? WHERE email=? AND item_id=?",
                        (int(time.time()), waiter["email"], item_id),
                    )
                    notify(c, waiter["email"], "activity_promoted", "Освободилось место", item["start"] + " · " + item["venue"] + " · " + item["title"])
                    audit(c, "activity_waitlist_promoted", waiter["email"], {"item_id": item_id})
            audit(c, "activity_cancelled", email, {"item_id": item_id})
        else:
            conflict = c.execute(
                'SELECT p.id,p.start,p."end",p.title,p.venue FROM activity_bookings b JOIN program_items p ON p.id=b.item_id '
                'WHERE b.email=? AND b.status='booked' AND p.id<>? AND p.start<? AND p."end">?',
                (email, item_id, item["end"], item["start"]),
            ).fetchone()
            if conflict:
                return error(
                    "schedule_conflict",
                    409,
                    conflict=dict(conflict),
                    requested={"id": item["id"], "start": item["start"], "end": item["end"], "title": item["title"], "venue": item["venue"]},
                )
            current = c.execute(
                "SELECT COUNT(*) n FROM activity_bookings WHERE item_id=? AND status='booked'",
                (item_id,),
            ).fetchone()["n"]
            status = "booked" if current < int(item["capacity"]) else "waitlist"
            c.execute(
                "INSERT INTO activity_bookings(email,item_id,status,ts) VALUES(?,?,?,?) "
                "ON CONFLICT(email,item_id) DO UPDATE SET status=excluded.status,ts=excluded.ts",
                (email, item_id, status, int(time.time())),
            )
            audit(c, "activity_" + status, email, {"item_id": item_id, "venue": item["venue"], "format": item["format"]})
            notify(c, email, "activity_" + status, "Запись в программу", item["start"] + " · " + item["venue"] + " · " + item["title"])
        return ok()

    if route == "/api/replay":
        item_id = str(data.get("item_id", "P05"))[:20]
        item = c.execute(
            "SELECT id,title,venue,track,partner,replay FROM program_items WHERE id=?",
            (item_id,),
        ).fetchone()
        if not item:
            return error("program_item_not_found", 404)
        chapters = [dict(r) for r in c.execute(
            "SELECT offset_sec,title,kind FROM replay_chapters WHERE item_id=? ORDER BY offset_sec",
            (item_id,),
        )]
        if role == "participant":
            c.execute("INSERT OR IGNORE INTO journeys(email,updated) VALUES(?,?)", (email, int(time.time())))
            c.execute("UPDATE journeys SET replay=1,updated=? WHERE email=?", (int(time.time()), email))
            audit(c, "replay_opened", email, {"item_id": item_id})
        return custom({
            "item": dict(item),
            "chapters": chapters,
            "transcript": "Демо-транскрипт: полный текст будет поступать из media provider и проходить редакционную проверку.",
            "related": ["A-014", "next_live_demo"],
        })

    if role not in ("participant", "staff", "organizer"):
        return error("forbidden", 403)
    item_id = str(data.get("item_id", ""))[:20]
    action = str(data.get("action", "checkin"))
    item = c.execute("SELECT id,title,venue,track,partner FROM program_items WHERE id=?", (item_id,)).fetchone()
    if not item:
        return error("program_item_not_found", 404)
    target = email
    if role in ("staff", "organizer") and data.get("email"):
        target = str(data.get("email"))[:160].lower()
    if action == "checkin":
        c.execute(
            "INSERT INTO session_attendance(email,item_id,status,checkin_ts,checkout_ts,source) VALUES(?,?,'present',?,NULL,?) "
            "ON CONFLICT(email,item_id) DO UPDATE SET status='present',checkin_ts=excluded.checkin_ts,source=excluded.source",
            (target, item_id, int(time.time()), role),
        )
        audit(c, "session_checkin", email, {"target": target, "item_id": item_id})
    elif action == "checkout":
        c.execute(
            "UPDATE session_attendance SET status='completed',checkout_ts=? WHERE email=? AND item_id=?",
            (int(time.time()), target, item_id),
        )
        audit(c, "session_checkout", email, {"target": target, "item_id": item_id})
    else:
        return error("bad_action", 400)
    c.execute(
        "INSERT INTO partner_engagement(email,partner,kind,ref_id,consent,ts) VALUES(?,?,?,?,0,?)",
        (target, item["partner"], "session_" + action, item_id, int(time.time())),
    )
    return ok()
