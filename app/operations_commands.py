import time

from app import db
from app.analytics import state
from app.commanding import custom, error, ok
from app.core import audit, notify, setv, sval

ROUTES = {
    "/api/move-session",
    "/api/live",
    "/api/checkin",
    "/api/staff-assignment",
    "/api/speaker-readiness",
    "/api/broadcast",
    "/api/venue-state",
    "/api/incident",
    "/api/stream-control",
    "/api/venue",
    "/api/phase",
}


def handle_command(c, route, role, email, data):
    if route not in ROUTES:
        return None

    if route == "/api/checkin":
        if role != "staff":
            return error("forbidden", 403)
        ticket = str(data.get("ticket", "DEMO-2027-001"))
        try:
            c.execute("INSERT INTO checkins(ticket,ts,staff) VALUES(?,?,?)", (ticket, int(time.time()), email))
            audit(c, "checkin", email, {"ticket": ticket})
            result = "valid"
        except db.INTEGRITY_ERRORS:
            result = "duplicate"
        payload = state(c, email)
        payload["scan_result"] = result
        return custom(payload, 200 if result == "valid" else 409)

    if role != "organizer":
        return error("forbidden", 403)

    if route == "/api/move-session":
        t = str(data.get("time", "11:30"))
        room = str(data.get("room", "Лекторий"))[:80]
        setv(c, "session_time", t)
        setv(c, "session_room", room)
        setv(c, "change_seq", int(sval(c, "change_seq", "0")) + 1)
        for target in ("participant@demo.ru", "participant2@demo.ru", "participant3@demo.ru"):
            notify(c, target, "schedule_changed", "Изменение программы", f"Новая площадка: {t} · {room}.")
        audit(c, "schedule_changed", email, {"time": t, "room": room})
        return ok()

    if route == "/api/live":
        value = str(data.get("state", "live"))
        if value not in ("scheduled", "live", "pause", "ended", "replay"):
            return error("bad_state", 400)
        setv(c, "live_state", value)
        audit(c, "live_state", email, {"state": value})
        return ok()

    if route == "/api/staff-assignment":
        action = str(data.get("action", "update"))
        if action != "update":
            return error("bad_action", 400)
        sid = int(data.get("id", 0))
        venue = str(data.get("venue", ""))[:80]
        status = str(data.get("status", "on_shift"))[:20]
        c.execute(
            "UPDATE staff_assignments SET venue=?,status=?,updated=? WHERE id=?",
            (venue, status, int(time.time()), sid),
        )
        audit(c, "staff_assignment_updated", email, {"id": sid, "venue": venue, "status": status})
        return ok()

    if route == "/api/speaker-readiness":
        speaker_id = str(data.get("speaker_id", ""))[:20]
        item_id = str(data.get("item_id", ""))[:20]
        field = str(data.get("field", "status"))
        allowed = {"status", "checkin", "briefed", "mic", "slides"}
        if field not in allowed:
            return error("bad_field", 400)
        value = data.get("value")
        if field == "status":
            c.execute(
                "UPDATE speaker_readiness SET status=?,updated=? WHERE speaker_id=? AND item_id=?",
                (str(value)[:20], int(time.time()), speaker_id, item_id),
            )
        else:
            c.execute(
                "UPDATE speaker_readiness SET " + field + "=?,updated=? WHERE speaker_id=? AND item_id=?",
                (1 if value else 0, int(time.time()), speaker_id, item_id),
            )
        audit(c, "speaker_readiness_updated", email, {"speaker_id": speaker_id, "item_id": item_id, "field": field, "value": value})
        return ok()

    if route == "/api/broadcast":
        audience = str(data.get("audience", "participants"))[:40]
        venue = str(data.get("venue", "all"))[:80]
        title = str(data.get("title", "Обновление события"))[:120]
        message = str(data.get("body", ""))[:300]
        c.execute(
            "INSERT INTO ops_broadcasts(audience,venue,title,body,status,ts) VALUES(?,?,?,?, 'sent', ?)",
            (audience, venue, title, message, int(time.time())),
        )
        targets = ("participant@demo.ru", "participant2@demo.ru", "participant3@demo.ru") if audience in ("participants", "all") else ()
        for target in targets:
            notify(c, target, "ops_broadcast", title, message)
        audit(c, "ops_broadcast_sent", email, {"audience": audience, "venue": venue, "title": title})
        return ok()

    if route == "/api/venue-state":
        venue = str(data.get("venue", ""))[:80]
        occupied = max(0, int(data.get("occupied", 0)))
        capacity = max(1, int(data.get("capacity", 1)))
        status = str(data.get("status", "open"))[:20]
        next_change = str(data.get("next_change", ""))[:120]
        if occupied > capacity:
            return error("occupied_exceeds_capacity", 409)
        c.execute(
            "INSERT INTO venue_state(venue,capacity,occupied,status,next_change,updated) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(venue) DO UPDATE SET capacity=excluded.capacity,occupied=excluded.occupied,status=excluded.status,next_change=excluded.next_change,updated=excluded.updated",
            (venue, capacity, occupied, status, next_change, int(time.time())),
        )
        audit(c, "venue_state_updated", email, {"venue": venue, "occupied": occupied, "capacity": capacity, "status": status})
        return ok()

    if route == "/api/incident":
        action = str(data.get("action", "create"))
        if action == "create":
            venue = str(data.get("venue", "Главная сцена"))[:80]
            severity = str(data.get("severity", "medium"))[:20]
            title = str(data.get("title", "Операционный инцидент"))[:160]
            recovery = str(data.get("recovery", "Проверить и восстановить"))[:240]
            c.execute(
                "INSERT INTO incidents(venue,severity,title,status,recovery,ts,resolved) VALUES(?,?,?,'open',?,?,0)",
                (venue, severity, title, recovery, int(time.time())),
            )
            audit(c, "incident_opened", email, {"venue": venue, "severity": severity, "title": title})
        elif action == "resolve":
            incident_id = int(data.get("id", 0))
            c.execute("UPDATE incidents SET status='resolved',resolved=? WHERE id=?", (int(time.time()), incident_id))
            audit(c, "incident_resolved", email, {"id": incident_id})
        else:
            return error("bad_action", 400)
        return ok()

    if route == "/api/stream-control":
        item_id = str(data.get("item_id", "P01"))[:20]
        status = str(data.get("status", "live"))[:20]
        health = str(data.get("health", "ok"))[:20]
        delay = max(0, int(data.get("delay_sec", 3)))
        c.execute(
            "INSERT INTO stream_state(item_id,status,health,delay_sec,updated) VALUES(?,?,?,?,?) "
            "ON CONFLICT(item_id) DO UPDATE SET status=excluded.status,health=excluded.health,delay_sec=excluded.delay_sec,updated=excluded.updated",
            (item_id, status, health, delay, int(time.time())),
        )
        audit(c, "stream_control", email, {"item_id": item_id, "status": status, "health": health, "delay_sec": delay})
        return ok()

    if route == "/api/venue":
        occupied = max(0, int(data.get("occupied", 0)))
        capacity = max(1, int(data.get("capacity", 120)))
        room = str(data.get("room", "Лекторий"))[:80]
        if occupied > capacity:
            return error("occupied_exceeds_capacity", 409)
        setv(c, "occupied", occupied)
        setv(c, "capacity", capacity)
        setv(c, "session_room", room)
        setv(c, "change_seq", int(sval(c, "change_seq", "0")) + 1)
        audit(c, "venue_updated", email, {"occupied": occupied, "capacity": capacity, "room": room})
        return ok()

    value = str(data.get("phase", "during"))
    setv(c, "phase", value)
    audit(c, "phase_changed", email, {"phase": value})
    return ok()
