from app import learning, participant, personalization, programme


STAGES = [
    {
        "id": "before",
        "label": "BEFORE",
        "title": "Собрать свой маршрут",
        "goal": "Темы, эксперты и программа до события.",
    },
    {
        "id": "event",
        "label": "EVENT DAY",
        "title": "Прожить событие",
        "goal": "Посещение, live/replay, встречи и заметки.",
    },
    {
        "id": "d1",
        "label": "D1",
        "title": "Зафиксировать главное",
        "goal": "Takeaways, replay и первый follow-up.",
    },
    {
        "id": "d7",
        "label": "D7",
        "title": "Продолжить тему",
        "goal": "Learning, Studio, community и эксперты.",
    },
    {
        "id": "d30",
        "label": "D30",
        "title": "Вернуться с новым контекстом",
        "goal": "Повторное использование, progress и следующий тематический цикл.",
    },
]


def _completed_stage_ids(c, email):
    done = set()
    profile = c.execute("SELECT 1 FROM attendee_profiles WHERE email=?", (email,)).fetchone()
    subscriptions = c.execute("SELECT COUNT(*) n FROM topic_subscriptions WHERE email=? AND status='active'", (email,)).fetchone()["n"]
    follows = c.execute("SELECT COUNT(*) n FROM expert_follows WHERE email=? AND status='active'", (email,)).fetchone()["n"]
    bookings = c.execute("SELECT COUNT(*) n FROM activity_bookings WHERE email=? AND status IN ('booked','confirmed')", (email,)).fetchone()["n"]
    if profile and (subscriptions or follows or bookings):
        done.add("before")

    attendance = c.execute("SELECT COUNT(*) n FROM session_attendance WHERE email=? AND status IN ('attended','checked_in','complete')", (email,)).fetchone()["n"]
    takeaways = c.execute("SELECT COUNT(*) n FROM takeaways WHERE email=?", (email,)).fetchone()["n"]
    if attendance or takeaways:
        done.add("event")

    replay = c.execute("SELECT replay FROM journeys WHERE email=?", (email,)).fetchone()
    d1 = c.execute("SELECT COUNT(*) n FROM followups WHERE email=? AND day=1 AND status IN ('done','completed','sent','active')", (email,)).fetchone()["n"]
    if (replay and int(replay["replay"] or 0)) or d1 or takeaways:
        done.add("d1")

    enroll = c.execute("SELECT COUNT(*) n FROM learning_enrollments WHERE email=? AND status IN ('active','completed')", (email,)).fetchone()["n"]
    d7 = c.execute("SELECT COUNT(*) n FROM followups WHERE email=? AND day=7 AND status IN ('done','completed','sent','active')", (email,)).fetchone()["n"]
    community = c.execute("SELECT COUNT(*) n FROM community_posts WHERE email=?", (email,)).fetchone()["n"]
    if enroll or d7 or community:
        done.add("d7")

    d30 = c.execute("SELECT COUNT(*) n FROM followups WHERE email=? AND day=30 AND status IN ('done','completed','sent','active')", (email,)).fetchone()["n"]
    completed_learning = c.execute("SELECT COUNT(*) n FROM learning_enrollments WHERE email=? AND status='completed'", (email,)).fetchone()["n"]
    journey = c.execute("SELECT club FROM journeys WHERE email=?", (email,)).fetchone()
    if d30 or completed_learning or (journey and int(journey["club"] or 0)):
        done.add("d30")
    return done


def _next_stage(done):
    for stage in STAGES:
        if stage["id"] not in done:
            return stage["id"]
    return "d30"


def snapshot(c, email=None):
    if not email:
        return {
            "journey365_mode": "anonymous",
            "journey365_stages": [],
            "journey365_progress_pct": 0,
        }

    done = _completed_stage_ids(c, email)
    current = _next_stage(done)
    p = participant.snapshot(c, email)
    pers = personalization.snapshot(c, email)
    prog = programme.snapshot(c, email)
    learn = learning.snapshot(c, email)

    stages = []
    for stage in STAGES:
        sid = stage["id"]
        if sid in done:
            status = "complete"
        elif sid == current:
            status = "current"
        else:
            status = "upcoming"
        stages.append({**stage, "status": status})

    next_item = (pers.get("personalized_items") or [None])[0]
    active_learning = next(
        (x for x in learn.get("learning_enrollments", []) if x.get("status") == "active"),
        None,
    )
    booked = next(
        (x for x in prog.get("activity_bookings", []) if x.get("status") in ("booked", "confirmed")),
        None,
    )

    if current == "before":
        action = {
            "title": booked["title"] if booked else "Выберите одну тему и добавьте событие в маршрут",
            "kind": "event" if booked else "discovery",
            "ref": booked["item_id"] if booked else "",
        }
    elif current == "event":
        action = {
            "title": booked["title"] if booked else "Откройте программу и отметьте посещённую сессию",
            "kind": "event",
            "ref": booked["item_id"] if booked else "",
        }
    elif current == "d1":
        action = {
            "title": next_item["title"] if next_item else "Вернитесь к replay и сохраните один takeaway",
            "kind": next_item["target_kind"] if next_item else "replay",
            "ref": next_item["target_ref"] if next_item else "",
        }
    elif current == "d7":
        action = {
            "title": active_learning["title"] if active_learning else (next_item["title"] if next_item else "Начните learning-маршрут по интересующей теме"),
            "kind": "learning" if active_learning else (next_item["target_kind"] if next_item else "learning"),
            "ref": active_learning["track_id"] if active_learning else (next_item["target_ref"] if next_item else ""),
        }
    else:
        action = {
            "title": next_item["title"] if next_item else "Выберите следующий тематический цикл",
            "kind": next_item["target_kind"] if next_item else "discovery",
            "ref": next_item["target_ref"] if next_item else "",
        }

    return {
        "journey365_mode": "derived_lifecycle_v1",
        "journey365_relationship_stage": p.get("relationship_stage", "registered"),
        "journey365_current_stage": current,
        "journey365_progress_pct": int(round(len(done) / len(STAGES) * 100)),
        "journey365_stages": stages,
        "journey365_next_action": action,
        "journey365_complete_count": len(done),
        "journey365_truth_boundary": {
            "behavioural_journey_only": True,
            "medical_journey": False,
            "diagnosis_or_treatment": False,
        },
    }
