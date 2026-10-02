import time

from app.commanding import error, ok
from app.core import audit, notify

ROUTES = {"/api/learning", "/api/challenge"}


def handle_command(c, route, role, email, data):
    if route not in ROUTES:
        return None
    if role != "participant":
        return error("forbidden", 403)

    if route == "/api/learning":
        track_id = str(data.get("track_id", ""))[:20]
        action = str(data.get("action", "enroll"))
        track = c.execute("SELECT id,title FROM learning_tracks WHERE id=?", (track_id,)).fetchone()
        if not track:
            return error("learning_track_not_found", 404)
        total = c.execute("SELECT COUNT(*) n FROM learning_steps WHERE track_id=?", (track_id,)).fetchone()["n"]
        if action == "enroll":
            c.execute(
                "INSERT INTO learning_enrollments(email,track_id,status,current_step,started,updated) "
                "VALUES(?,?,'active',0,?,?) ON CONFLICT(email,track_id) DO UPDATE SET status='active',updated=excluded.updated",
                (email, track_id, int(time.time()), int(time.time())),
            )
            notify(c, email, "learning_enrolled", "Маршрут начат", track["title"] + " · прогресс сохраняется в профиле.")
            audit(c, "learning_enrolled", email, {"track_id": track_id})
        elif action == "advance":
            row = c.execute(
                "SELECT current_step,status FROM learning_enrollments WHERE email=? AND track_id=?",
                (email, track_id),
            ).fetchone()
            if not row:
                return error("learning_not_enrolled", 409)
            new_step = min(total, int(row["current_step"]) + 1)
            status = "completed" if total and new_step >= total else "active"
            c.execute(
                "UPDATE learning_enrollments SET current_step=?,status=?,updated=? WHERE email=? AND track_id=?",
                (new_step, status, int(time.time()), email, track_id),
            )
            if status == "completed":
                notify(c, email, "learning_completed", "Маршрут завершён", track["title"] + " · материалы и replay остаются в вашем профиле.")
            audit(c, "learning_advanced", email, {"track_id": track_id, "current_step": new_step, "total_steps": total, "status": status})
        else:
            return error("bad_action", 400)
        return ok()

    cid = str(data.get("challenge_id", "health30"))[:40]
    action = str(data.get("action", "start"))
    if action == "start":
        reward = "Гарантированный partner benefit после подтверждения условий; не связан с покупкой лекарства"
        c.execute(
            "INSERT INTO challenges(email,challenge_id,status,days_required,started,verified,reward) "
            "VALUES(?,?,'active',30,?,0,?) ON CONFLICT(email,challenge_id) DO UPDATE SET status='active',started=excluded.started,reward=excluded.reward",
            (email, cid, int(time.time()), reward),
        )
        for aid, label in [
            ("01_platform", "Подписка на СОСТОЯНИЕ"),
            ("02_promomed", "Выбранный публичный канал Промомед"),
            ("03_partner", "Выбранный канал партнёра"),
            ("04_content", "Контент / эфир в течение маршрута"),
            ("05_day30", "Финальная проверка на 30-й день"),
        ]:
            c.execute(
                "INSERT OR IGNORE INTO challenge_actions(email,challenge_id,action_id,label,status,ts) VALUES(?,?,?,?,'planned',?)",
                (email, cid, aid, label, int(time.time())),
            )
        audit(c, "challenge_started", email, {"challenge_id": cid, "days": 30})
        notify(c, email, "challenge_started", "30 дней СОСТОЯНИЯ", "Подписки и действия подтверждаются по опубликованным правилам. Награда не зависит от покупки лекарств.")
    elif action == "check":
        aid = str(data.get("action_id", ""))[:40]
        row = c.execute(
            "SELECT 1 FROM challenge_actions WHERE email=? AND challenge_id=? AND action_id=?",
            (email, cid, aid),
        ).fetchone()
        if not row:
            return error("challenge_action_not_found", 404)
        c.execute(
            "UPDATE challenge_actions SET status='confirmed_demo',ts=? WHERE email=? AND challenge_id=? AND action_id=?",
            (int(time.time()), email, cid, aid),
        )
        audit(c, "challenge_action_confirmed", email, {"challenge_id": cid, "action_id": aid})
    elif action == "verify_demo":
        remaining = c.execute(
            "SELECT COUNT(*) n FROM challenge_actions WHERE email=? AND challenge_id=? AND status!='confirmed_demo'",
            (email, cid),
        ).fetchone()["n"]
        if remaining:
            return error("challenge_incomplete", 409, remaining=remaining)
        c.execute(
            "UPDATE challenges SET status='completed',verified=? WHERE email=? AND challenge_id=?",
            (int(time.time()), email, cid),
        )
        audit(c, "challenge_completed", email, {"challenge_id": cid})
    else:
        return error("bad_action", 400)
    return ok()
