import time

from app.commanding import error, ok
from app.core import audit, notify
from app import discovery

ROUTES = {
    "/api/journey",
    "/api/profile",
    "/api/takeaway",
    "/api/feedback",
    "/api/passport",
    "/api/product-interest",
    "/api/followup-enroll",
    "/api/discovery/save",
    "/api/discovery/unsave",
}


def handle_command(c, route, role, email, data):
    if route not in ROUTES:
        return None
    if role != "participant":
        return error("forbidden", 403)

    if route == "/api/journey":
        action = str(data.get("action", "replay"))
        c.execute("INSERT OR IGNORE INTO journeys(email,updated) VALUES(?,?)", (email, int(time.time())))
        if action not in ("attended", "replay", "club"):
            return error("bad_action", 400)
        c.execute("UPDATE journeys SET " + action + "=1,updated=? WHERE email=?", (int(time.time()), email))
        audit(c, "journey_" + action, email, {})
        return ok()

    if route == "/api/profile":
        intent = str(data.get("intent", "Понять полезное для себя"))[:120]
        interests = str(data.get("interests", "сон,наука,движение"))[:240]
        networking = 1 if data.get("networking", True) else 0
        visibility = str(data.get("visibility", "event_only"))
        if visibility not in ("private", "event_only", "matches_only"):
            return error("bad_visibility", 400)
        c.execute(
            "INSERT INTO attendee_profiles(email,intent,interests,networking,visibility,updated) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(email) DO UPDATE SET intent=excluded.intent,interests=excluded.interests,networking=excluded.networking,visibility=excluded.visibility,updated=excluded.updated",
            (email, intent, interests, networking, visibility, int(time.time())),
        )
        audit(c, "profile_updated", email, {"intent": intent, "networking": bool(networking), "visibility": visibility})
        return ok()

    if route == "/api/takeaway":
        note = str(data.get("note", ""))[:240].strip()
        if not note:
            return error("note_required", 422)
        sid = str(data.get("session_id", "S2"))[:30]
        source = str(data.get("source", "session"))[:40]
        c.execute(
            "INSERT INTO takeaways(email,session_id,note,source,ts) VALUES(?,?,?,?,?)",
            (email, sid, note, source, int(time.time())),
        )
        audit(c, "takeaway_saved", email, {"session_id": sid, "source": source})
        notify(c, email, "takeaway_saved", "Сохранено в «Мои выводы»", "Вернитесь к мысли после события — она останется рядом с записью и источниками.")
        return ok()

    if route == "/api/feedback":
        rating = max(1, min(5, int(data.get("rating", 5))))
        useful = 1 if data.get("useful", True) else 0
        comment = str(data.get("comment", ""))[:300]
        c.execute(
            "INSERT INTO session_feedback(email,session_id,rating,useful,comment,ts) VALUES(?,?,?,?,?,?)",
            (email, str(data.get("session_id", "S2")), rating, useful, comment, int(time.time())),
        )
        audit(c, "session_feedback", email, {"rating": rating, "useful": bool(useful)})
        return ok()

    if route == "/api/passport":
        dimension = str(data.get("dimension", "content"))
        if dimension not in ("content", "event", "network", "partner"):
            return error("bad_dimension", 400)
        c.execute("UPDATE passport SET " + dimension + "=1,updated=? WHERE email=?", (int(time.time()), email))
        audit(c, "passport_" + dimension, email, {})
        return ok()

    if route in ("/api/discovery/save", "/api/discovery/unsave"):
        kind = str(data.get("target_kind", ""))[:30].strip()
        ref = str(data.get("target_ref", ""))[:120].strip()
        if not kind or not ref:
            return error("target_required", 422)
        if route == "/api/discovery/unsave":
            c.execute("DELETE FROM discovery_saves WHERE email=? AND target_kind=? AND target_ref=?", (email, kind, ref))
            audit(c, "discovery_unsaved", email, {"target_kind": kind, "target_ref": ref})
            return ok()
        found = [x for x in discovery.search(c, kind=kind, limit=100, email=email)["results"] if x["ref"] == ref]
        if not found:
            return error("discovery_target_not_found", 404)
        row = found[0]
        c.execute(
            "INSERT INTO discovery_saves(email,target_kind,target_ref,title,topic,created_at,demo_only) VALUES(?,?,?,?,?,?,1) "
            "ON CONFLICT(email,target_kind,target_ref) DO UPDATE SET title=excluded.title,topic=excluded.topic,created_at=excluded.created_at",
            (email, kind, ref, row["title"], row.get("topic") or "", int(time.time())),
        )
        audit(c, "discovery_saved", email, {"target_kind": kind, "target_ref": ref})
        notify(c, email, "discovery_saved", "Сохранено в ваш маршрут", row["title"])
        return ok()

    if route == "/api/product-interest":
        if data.get("consent") is not True:
            return error("consent_required", 422)
        track = str(data.get("track", "metabolic_health"))[:80]
        context = str(data.get("context", "official_product_information"))[:120]
        consent_version = str(data.get("consent_version", "product-interest-v1"))[:40]
        c.execute(
            "INSERT INTO product_interests(email,track,context,consent_version,status,ts) VALUES(?,?,?,?, 'requested',?)",
            (email, track, context, consent_version, int(time.time())),
        )
        notify(c, email, "product_interest_saved", "Интерес сохранён", "Мы сохранили запрос на официальный материал. Это не медицинская рекомендация и не назначение.")
        audit(c, "product_interest", email, {"track": track, "context": context, "consent_version": consent_version})
        return ok()

    track = str(data.get("track", "metabolic_health"))[:80]
    for day in (1, 7, 30):
        c.execute(
            "INSERT INTO followups(email,day,track,status,ts) VALUES(?,?,?,'planned',?)",
            (email, day, track, int(time.time())),
        )
    audit(c, "followup_30d_enrolled", email, {"track": track, "days": [1, 7, 30]})
    notify(c, email, "followup_enrolled", "30-дневный маршрут включён", "Материалы и события будут продолжать выбранную тему без автоматических медицинских назначений.")
    return ok()
