from app import community, content, learning, participant, programme


REASON_LABELS = {
    "continue_learning_track": "Продолжить начатый маршрут",
    "subscribed_topic": "Вы подписаны на эту тему",
    "follows_expert": "Вы следите за этим экспертом",
    "attended_related_session": "Связано с посещённой сессией",
    "booked_related_session": "Связано с вашим расписанием",
    "profile_interest": "Совпадает с вашими интересами",
    "relationship_stage": "Следующий шаг вашего маршрута",
    "saved_for_later": "Вы сохранили это для продолжения",
    "editorial_default": "Редакционный выбор",
}


def _tokens(value):
    return {x.strip().lower() for x in str(value or "").replace(";", ",").split(",") if x.strip()}


def _topic_match(topic, signals):
    t = str(topic or "").strip().lower()
    if not t:
        return False
    return any(s in t or t in s for s in signals if s)


def _reason(code, detail=""):
    return {
        "code": code,
        "label": REASON_LABELS[code],
        "detail": detail,
        "medical_inference": False,
    }


def snapshot(c, email=None):
    if not email:
        return {
            "personalization_mode": "anonymous",
            "personalized_items": [],
            "personalization_reason_codes": REASON_LABELS,
            "personalization_medical_inference": False,
        }

    p = participant.snapshot(c, email)
    comm = community.snapshot(c, email)
    learn = learning.snapshot(c, email)
    prog = programme.snapshot(c, email)
    cont = content.snapshot(c)

    interests = _tokens((p.get("profile") or {}).get("interests"))
    subscriptions = {
        str(x["topic"]).strip().lower()
        for x in comm.get("topic_subscriptions", [])
        if x.get("status") in ("active", "subscribed", "on")
    }
    follows = {
        x["speaker_id"]
        for x in comm.get("expert_follows", [])
        if x.get("status") in ("active", "following", "on")
    }
    attended = {
        x["item_id"]
        for x in prog.get("session_attendance", [])
        if x.get("status") in ("attended", "checked_in", "complete")
    }
    booked = {
        x["item_id"]
        for x in prog.get("activity_bookings", [])
        if x.get("status") in ("booked", "confirmed")
    }
    enrollments = {
        x["track_id"]: x
        for x in learn.get("learning_enrollments", [])
        if x.get("status") in ("active", "in_progress", "started")
    }

    all_topic_signals = interests | subscriptions
    items = []

    # 0) Explicit saved discovery items are strong user intent signals.
    try:
        saved_rows = [dict(x) for x in c.execute(
            "SELECT target_kind,target_ref,title,topic FROM discovery_saves WHERE email=? ORDER BY created_at DESC LIMIT 12",
            (email,),
        )]
    except Exception:
        saved_rows = []
    for row in saved_rows:
        items.append({
            "id": f"saved:{row['target_kind']}:{row['target_ref']}",
            "kind": row["target_kind"],
            "title": row["title"],
            "subtitle": "Сохранено из Discovery",
            "topic": row.get("topic") or "",
            "target_kind": row["target_kind"],
            "target_ref": row["target_ref"],
            "priority": 96,
            "reason": _reason("saved_for_later", row.get("topic") or ""),
        })

    # 1) Continue an enrolled learning journey first.
    steps_by_track = {}
    for step in learn.get("learning_steps", []):
        steps_by_track.setdefault(step["track_id"], []).append(step)
    tracks = {x["id"]: x for x in learn.get("learning_tracks", [])}
    for track_id, enrollment in enrollments.items():
        steps = sorted(steps_by_track.get(track_id, []), key=lambda x: int(x["step_no"]))
        current = int(enrollment.get("current_step") or 0)
        next_step = next((x for x in steps if int(x["step_no"]) > current), steps[-1] if steps else None)
        track = tracks.get(track_id)
        if track and next_step:
            items.append({
                "id": f"continue:{track_id}",
                "kind": "learning",
                "title": track["title"],
                "subtitle": next_step["title"],
                "topic": track["topic"],
                "target_kind": next_step["kind"],
                "target_ref": next_step["ref_id"],
                "priority": 100,
                "reason": _reason("continue_learning_track", f"Шаг {next_step['step_no']} из {len(steps)}"),
            })

    # 2) Content that matches explicit topics/subscriptions.
    for row in cont.get("content_catalog", []):
        status = str(row.get("status") or "")
        if status not in ("published", "concept", "review"):
            continue
        if _topic_match(row.get("theme"), subscriptions):
            code = "subscribed_topic"
            score = 88
        elif _topic_match(row.get("theme"), interests):
            code = "profile_interest"
            score = 78
        else:
            continue
        items.append({
            "id": f"content:{row['id']}",
            "kind": "content",
            "title": row["title"],
            "subtitle": row.get("dek") or "",
            "topic": row.get("theme") or "",
            "target_kind": "content",
            "target_ref": row["id"],
            "priority": score,
            "reason": _reason(code, row.get("theme") or ""),
        })

    # 3) Studio and programme items matching explicit topic signals.
    for ep in cont.get("studio_episodes", []):
        topic = ep.get("topic") or ""
        if _topic_match(topic, subscriptions):
            code, score = "subscribed_topic", 90
        elif _topic_match(topic, interests):
            code, score = "profile_interest", 80
        else:
            continue
        items.append({
            "id": f"studio-topic:{ep['id']}",
            "kind": "studio",
            "title": ep["title"],
            "subtitle": ep.get("dek") or "",
            "topic": topic,
            "target_kind": "studio",
            "target_ref": ep["id"],
            "priority": score,
            "reason": _reason(code, topic),
        })

    for row in prog.get("program", []):
        topic = row.get("track") or ""
        if _topic_match(topic, subscriptions):
            code, score = "subscribed_topic", 86
        elif _topic_match(topic, interests):
            code, score = "profile_interest", 74
        else:
            continue
        items.append({
            "id": f"event-topic:{row['id']}",
            "kind": "event",
            "title": row["title"],
            "subtitle": f"{row['start']} · {row['venue']}",
            "topic": topic,
            "target_kind": "event",
            "target_ref": row["id"],
            "priority": score,
            "reason": _reason(code, topic),
        })

    # 4) Experts followed by the participant -> connected Studio/session.
    session_speakers = {}
    for link in prog.get("session_speakers", []):
        session_speakers.setdefault(link["id"], set()).add(link["item_id"])
    for ep in cont.get("studio_episodes", []):
        if ep.get("speaker_id") in follows:
            items.append({
                "id": f"studio:{ep['id']}",
                "kind": "studio",
                "title": ep["title"],
                "subtitle": ep.get("dek") or "",
                "topic": ep.get("topic") or "",
                "target_kind": "studio",
                "target_ref": ep["id"],
                "priority": 92,
                "reason": _reason("follows_expert", ep.get("speaker_name") or ""),
            })

    # 5) Replay / continuation after booked or attended sessions.
    program_by_id = {x["id"]: x for x in prog.get("program", [])}
    for item_id in sorted(attended | booked):
        row = program_by_id.get(item_id)
        if not row or not int(row.get("replay") or 0):
            continue
        code = "attended_related_session" if item_id in attended else "booked_related_session"
        items.append({
            "id": f"replay:{item_id}",
            "kind": "replay",
            "title": f"Replay · {row['title']}",
            "subtitle": "Вернуться к записи и тезисам",
            "topic": row.get("track") or "",
            "target_kind": "replay",
            "target_ref": item_id,
            "priority": 94 if item_id in attended else 82,
            "reason": _reason(code, row.get("track") or ""),
        })

    # 6) If user has little explicit history, add one deterministic editorial item.
    if len(items) < 3:
        published = next(
            (x for x in cont.get("content_catalog", []) if x.get("status") == "published"),
            None,
        )
        if published:
            items.append({
                "id": f"editorial:{published['id']}",
                "kind": "content",
                "title": published["title"],
                "subtitle": published.get("dek") or "",
                "topic": published.get("theme") or "",
                "target_kind": "content",
                "target_ref": published["id"],
                "priority": 50,
                "reason": _reason("editorial_default", "Fallback без персональных медицинских выводов"),
            })

    # De-duplicate by target and keep deterministic order.
    seen = set()
    ranked = []
    for row in sorted(items, key=lambda x: (-int(x["priority"]), x["id"])):
        key = (row["target_kind"], row["target_ref"])
        if key in seen:
            continue
        seen.add(key)
        ranked.append(row)
        if len(ranked) == 6:
            break

    return {
        "personalization_mode": "deterministic_rules_v1",
        "personalization_relationship_stage": p.get("relationship_stage", "registered"),
        "personalization_signals": {
            "interest_count": len(interests),
            "subscription_count": len(subscriptions),
            "follow_count": len(follows),
            "attended_count": len(attended),
            "booked_count": len(booked),
            "active_learning_count": len(enrollments),
            "saved_discovery_count": len(saved_rows),
        },
        "personalized_items": ranked,
        "personalization_reason_codes": REASON_LABELS,
        "personalization_medical_inference": False,
        "personalization_forbidden_outputs": [
            "diagnosis",
            "treatment recommendation",
            "drug recommendation",
            "individual health-risk score",
        ],
    }
