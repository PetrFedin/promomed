"""Read-only demo protocol projections.

Demo events are global synthetic fixtures, not a tenant-scoped production
evidence feed. Never call these reads with a non-demo authority.
"""
from app import db
from app.analytics import commercial, state
from app.core import sval
from app.demo import DEMO_STEPS

DEMO_ROUTES = frozenset(("/api/demo/status", "/api/demo/evidence"))


def serve(route, actor, connect):
    """Return an HTTP-compatible (payload, status) pair or None."""
    if route not in DEMO_ROUTES:
        return None
    if not db.demo_seed_enabled():
        return {"error": "not_found"}, 404

    if route == "/api/demo/status":
        if not actor or actor[0] not in ("sales", "organizer"):
            return {"error": "forbidden"}, 403
        c = connect()
        try:
            idx = int(sval(c, "demo_step", "-1"))
            payload = state(c, actor[2])
        finally:
            c.close()
        payload["step_index"] = idx
        payload["step_key"] = DEMO_STEPS[idx][0] if 0 <= idx < len(DEMO_STEPS) else "not_started"
        payload["step_title"] = DEMO_STEPS[idx][1] if 0 <= idx < len(DEMO_STEPS) else "Демо не подготовлено"
        payload["total_steps"] = len(DEMO_STEPS)
        return payload, 200

    if not actor or actor[0] not in ("sales", "organizer", "partner"):
        return {"error": "forbidden"}, 403
    c = connect()
    try:
        rows = [
            dict(r) for r in c.execute(
                "SELECT id,kind,actor,payload,ts FROM events ORDER BY id DESC LIMIT 30"
            )
        ]
        rows.reverse()
        metrics = commercial(c)
        metrics["placement_status"] = state(c).get("placement_status")
        metrics["live_state"] = sval(c, "live_state", "scheduled")
        metrics["phase"] = sval(c, "phase", "before")
        metrics["session_time"] = sval(c, "session_time", "11:00")
        metrics["session_room"] = sval(c, "session_room", "Лекторий")
        metrics["occupied"] = int(sval(c, "occupied", "0"))
        metrics["capacity"] = int(sval(c, "capacity", "120"))
        deliverables = [
            dict(r) for r in c.execute(
                "SELECT id,label,status,evidence,updated FROM deliverables ORDER BY id"
            )
        ]
        notifications = c.execute("SELECT COUNT(*) n FROM notifications").fetchone()["n"]
        metrics["notifications"] = notifications
    finally:
        c.close()
    return {
        "events": rows,
        "metrics": metrics,
        "deliverables": deliverables,
        "proposed_pilot_gates": [
            {"id": "audience", "label": "Аудитория", "criterion": "Регистрация → фактическое участие", "target": "Цель пилота согласуется до запуска", "status": "to_agree"},
            {"id": "engagement", "label": "Вовлечённость", "criterion": "Контент → событие → post-event возврат", "target": "Цель пилота согласуется до запуска", "status": "to_agree"},
            {"id": "partner", "label": "Коммерция", "criterion": "Добровольные лиды и ценность партнёра", "target": "Цель пилота согласуется до запуска", "status": "to_agree"},
            {"id": "operations", "label": "Операции", "criterion": "Check-in / waitlist / venue / live без критических тупиков", "target": "0 критических сценариев без recovery path", "status": "proposed"},
            {"id": "trust", "label": "Доверие", "criterion": "Контент, согласия и партнёрская прозрачность", "target": "100% обязательных approval / disclosure полей в пилоте", "status": "proposed"},
        ],
    }, 200
