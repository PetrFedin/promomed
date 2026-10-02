import time

from app.commanding import error, ok
from app.core import audit, notify

ROUTES = {
    "/api/follow-expert",
    "/api/subscribe-topic",
    "/api/community-post",
    "/api/direct-message",
    "/api/meeting",
    "/api/mutual-meeting",
    "/api/meeting-action",
}


def handle_command(c, route, role, email, data):
    if route not in ROUTES:
        return None

    if route == "/api/follow-expert":
        if role != "participant":
            return error("forbidden", 403)
        speaker_id = str(data.get("speaker_id", ""))[:20]
        action = str(data.get("action", "follow"))
        speaker = c.execute("SELECT id,name FROM speakers WHERE id=?", (speaker_id,)).fetchone()
        if not speaker:
            return error("speaker_not_found", 404)
        if action == "unfollow":
            c.execute("DELETE FROM expert_follows WHERE email=? AND speaker_id=?", (email, speaker_id))
            audit(c, "expert_unfollowed", email, {"speaker_id": speaker_id})
        else:
            c.execute(
                "INSERT INTO expert_follows(email,speaker_id,status,ts) VALUES(?,?,'active',?) "
                "ON CONFLICT(email,speaker_id) DO UPDATE SET status='active',ts=excluded.ts",
                (email, speaker_id, int(time.time())),
            )
            notify(c, email, "expert_followed", "Вы подписались на эксперта", speaker["name"] + " · новые материалы и эфиры появятся в вашем маршруте.")
            audit(c, "expert_followed", email, {"speaker_id": speaker_id})
        return ok()

    if route == "/api/subscribe-topic":
        if role != "participant":
            return error("forbidden", 403)
        topic = str(data.get("topic", ""))[:120].strip()
        action = str(data.get("action", "subscribe"))
        allowed = {r["topic"] for r in c.execute("SELECT DISTINCT topic FROM community_threads")}
        if topic not in allowed:
            return error("topic_not_found", 404)
        if action == "unsubscribe":
            c.execute("DELETE FROM topic_subscriptions WHERE email=? AND topic=?", (email, topic))
            audit(c, "topic_unsubscribed", email, {"topic": topic})
        else:
            c.execute(
                "INSERT INTO topic_subscriptions(email,topic,status,ts) VALUES(?,?,'active',?) "
                "ON CONFLICT(email,topic) DO UPDATE SET status='active',ts=excluded.ts",
                (email, topic, int(time.time())),
            )
            notify(c, email, "topic_subscribed", "Тема добавлена в ваш маршрут", topic + " · Studio, материалы, события и обсуждения будут собираться вместе.")
            audit(c, "topic_subscribed", email, {"topic": topic})
        return ok()

    if route == "/api/community-post":
        if role != "participant":
            return error("forbidden", 403)
        thread_id = str(data.get("thread_id", ""))[:20]
        text = str(data.get("body", "")).strip()[:800]
        thread = c.execute("SELECT id,title FROM community_threads WHERE id=? AND status='open'", (thread_id,)).fetchone()
        if not thread:
            return error("thread_not_found", 404)
        if len(text) < 8:
            return error("post_too_short", 400)
        c.execute(
            "INSERT INTO community_posts(thread_id,email,body,status,ts) VALUES(?,?,?,'pending_moderation',?)",
            (thread_id, email, text, int(time.time())),
        )
        notify(c, email, "community_post", "Вопрос отправлен на модерацию", thread["title"] + " · после проверки он появится в обсуждении.")
        audit(c, "community_post_submitted", email, {"thread_id": thread_id})
        return ok()

    if route == "/api/direct-message":
        if role not in ("participant", "organizer"):
            return error("forbidden", 403)
        recipient = str(data.get("recipient", "")).lower()[:120].strip()
        text = str(data.get("body", "")).strip()[:500]
        context = str(data.get("context", "inbox"))[:80]
        if recipient == email:
            return error("recipient_not_allowed", 403)
        recipient_account = c.execute(
            "SELECT email,role,name,status FROM accounts WHERE email=?",
            (recipient,),
        ).fetchone()
        sender_account = c.execute(
            "SELECT email,role,name,status FROM accounts WHERE email=?",
            (email,),
        ).fetchone()
        if not recipient_account or recipient_account["status"] != "active":
            return error("recipient_not_allowed", 403)
        if len(text) < 1:
            return error("message_required", 422)
        allowed = False
        if role == "organizer":
            allowed = recipient_account["role"] == "participant"
        elif recipient_account["role"] == "organizer":
            allowed = True
        elif recipient_account["role"] == "participant":
            rel = c.execute(
                """SELECT 1 FROM mutual_meetings
                   WHERE status='confirmed' AND ((requester=? AND target_email=?) OR (requester=? AND target_email=?))
                   LIMIT 1""",
                (email, recipient, recipient, email),
            ).fetchone()
            allowed = bool(rel)
        if not allowed:
            return error("conversation_requires_mutual_consent", 403)
        c.execute(
            "INSERT INTO direct_messages(sender,recipient,context,body,status,ts) VALUES(?,?,?,?, 'delivered',?)",
            (email, recipient, context, text, int(time.time())),
        )
        sender_name = sender_account["name"] if sender_account else email
        notify(c, recipient, "direct_message", "Новое сообщение", sender_name + " · " + text[:120])
        audit(c, "direct_message_sent", email, {"recipient": recipient, "context": context})
        return ok()

    if route == "/api/meeting":
        if role != "participant":
            return error("forbidden", 403)
        target = str(data.get("target", "Участник с похожими интересами"))[:120]
        slot = str(data.get("slot", "14:20"))[:20]
        place = str(data.get("place", "Клуб СОСТОЯНИЯ"))[:80]
        c.execute(
            "INSERT INTO meetings(requester,target,slot,place,status,ts) VALUES(?,?,?,?, 'requested',?)",
            (email, target, slot, place, int(time.time())),
        )
        c.execute("UPDATE passport SET network=1,updated=? WHERE email=?", (int(time.time()), email))
        notify(c, email, "meeting_requested", "Встреча запрошена", slot + " · " + place)
        audit(c, "meeting_requested", email, {"target": target, "slot": slot, "place": place})
        return ok()

    if route == "/api/mutual-meeting":
        if role != "participant":
            return error("forbidden", 403)
        action = str(data.get("action", "request"))
        if action == "request":
            target_email = str(data.get("target_email", "participant2@demo.ru")).lower()[:120]
            if target_email == email:
                return error("self_meeting", 409)
            target_account = c.execute(
                "SELECT email,role,name,status FROM accounts WHERE email=?",
                (target_email,),
            ).fetchone()
            if not target_account or target_account["status"] != "active" or target_account["role"] != "participant":
                return error("target_not_found", 404)
            target_name = str(data.get("target_name") or target_account["name"])[:120]
            slot = str(data.get("slot", "14:20"))[:20]
            place = str(data.get("place", "Клуб СОСТОЯНИЯ"))[:80]
            overlap = c.execute(
                "SELECT 1 FROM mutual_meetings WHERE requester=? AND slot=? AND status IN ('requested','confirmed')",
                (email, slot),
            ).fetchone()
            if overlap:
                return error("meeting_slot_conflict", 409)
            c.execute(
                "INSERT INTO mutual_meetings(requester,target_email,target_name,slot,place,status,requester_ok,target_ok,ts) "
                "VALUES(?,?,?,?,?,'requested',1,0,?)",
                (email, target_email, target_name, slot, place, int(time.time())),
            )
            notify(c, target_email, "meeting_invite", "Новый запрос на встречу", slot + " · " + place + " · взаимное подтверждение")
            audit(c, "mutual_meeting_requested", email, {"target_email": target_email, "slot": slot})
        else:
            mid = int(data.get("id", 0))
            row = c.execute("SELECT * FROM mutual_meetings WHERE id=?", (mid,)).fetchone()
            if not row or email not in (row["requester"], row["target_email"]):
                return error("meeting_not_found", 404)
            if action == "accept":
                if email != row["target_email"]:
                    return error("target_confirmation_required", 403)
                c.execute("UPDATE mutual_meetings SET target_ok=1,status='confirmed' WHERE id=?", (mid,))
                notify(c, row["requester"], "meeting_confirmed", "Встреча подтверждена", row["slot"] + " · " + row["place"])
                notify(c, row["target_email"], "meeting_confirmed", "Встреча подтверждена", row["slot"] + " · " + row["place"])
                audit(c, "mutual_meeting_confirmed", email, {"id": mid})
            elif action == "cancel":
                c.execute("UPDATE mutual_meetings SET status='cancelled' WHERE id=?", (mid,))
                audit(c, "mutual_meeting_cancelled", email, {"id": mid})
            else:
                return error("bad_action", 400)
        return ok()

    if route == "/api/meeting-action":
        if role != "participant":
            return error("forbidden", 403)
        mid = int(data.get("id", 0))
        action = str(data.get("action", "cancel"))
        row = c.execute(
            "SELECT status,target,slot,place FROM meetings WHERE id=? AND requester=?",
            (mid, email),
        ).fetchone()
        if not row:
            return error("meeting_not_found", 404)
        if action not in ("accept_demo", "cancel"):
            return error("bad_action", 400)
        status = "confirmed" if action == "accept_demo" else "cancelled"
        c.execute("UPDATE meetings SET status=? WHERE id=?", (status, mid))
        notify(c, email, "meeting_" + status, "Встреча " + ("подтверждена" if status == "confirmed" else "отменена"), row["slot"] + " · " + row["place"])
        audit(c, "meeting_" + status, email, {"id": mid, "target": row["target"]})
        return ok()
