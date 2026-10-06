import time

from app.core import audit, notify, promote_waitlist, setv, sval

DEMO_STEPS = [
    ("ready", "Исходное состояние подготовлено"),
    ("full", "Зал заполнен: 120 / 120"),
    ("waitlist", "P2 и P3 поставлены в waitlist"),
    ("promoted", "Место освобождено: P2 автоматически повышен"),
    ("hall_move", "Сессия перенесена, участникам создано уведомление"),
    ("pause", "Live переведён в technical pause"),
    ("live", "Эфир восстановлен"),
    ("replay", "Эфир завершён, replay доступен"),
    ("checkin", "QR-билет подтверждён на входе"),
    ("placement", "Contracted placement активирован"),
    ("lead", "Создан добровольный consented lead"),
    ("post_event", "Post-event replay открыт, dashboard готов"),
]


def reset_demo(c, actor):
    for t in (
        "checkins","leads","registrations","bookings","questions","journeys","notifications",
        "direct_messages","events","meetings","session_feedback","takeaways","product_interests",
        "followups","topic_subscriptions","expert_follows","learning_enrollments","community_posts",
        "investment_acceptances","deal_obligation_records","deal_issues",
        "deal_evidence_documents","deal_obligation_sla","deal_payment_requests",
    ):
        c.execute("DELETE FROM " + t)
    for k, v in {
        "session_time":"11:00","session_room":"Лекторий","live_state":"scheduled","occupied":"116",
        "capacity":"120","phase":"before","change_seq":"0","gift_issued":"0","demo_step":"0",
    }.items():
        setv(c, k, v)
    setv(c, "demo_run", int(sval(c, "demo_run", "0")) + 1)
    c.execute("UPDATE placements SET status='contracted',leads=0,ts=? WHERE id=1", (int(time.time()),))
    c.execute("UPDATE deliverables SET status='contracted',evidence='',updated=?", (int(time.time()),))
    c.execute("UPDATE passport SET content=0,event=0,network=0,partner=0,updated=?", (int(time.time()),))
    c.execute("UPDATE cms SET status='medical_review',version=1,updated=? WHERE id='A-014'", (int(time.time()),))
    c.execute(
        "INSERT OR REPLACE INTO registrations(email,status,ts) VALUES('participant@demo.ru','confirmed',?)",
        (int(time.time()),),
    )
    audit(c, "demo_reset", actor, {"run": sval(c, "demo_run")})


def run_demo_step(c, step, actor):
    now = int(time.time())
    if step == 1:
        setv(c, "occupied", 120); setv(c, "capacity", 120); setv(c, "phase", "during")
        audit(c, "venue_full", actor, {"occupied": 120, "capacity": 120})
    elif step == 2:
        for e in ("participant2@demo.ru", "participant3@demo.ru"):
            c.execute("INSERT OR REPLACE INTO registrations(email,status,ts) VALUES(?,'confirmed',?)", (e, now))
            c.execute("INSERT OR REPLACE INTO bookings(email,session_id,status,ts) VALUES(?,'S2','waitlist',?)", (e, now))
            audit(c, "booking_waitlist", e, {"session_id": "S2"})
    elif step == 3:
        setv(c, "occupied", 119); audit(c, "seat_released", actor, {"session_id": "S2"})
        promote_waitlist(c, "S2")
    elif step == 4:
        setv(c, "session_time", "11:30"); setv(c, "session_room", "Зал «Практика»")
        setv(c, "change_seq", int(sval(c, "change_seq", "0")) + 1)
        for e in ("participant@demo.ru", "participant2@demo.ru", "participant3@demo.ru"):
            notify(c, e, "schedule_changed", "Изменение программы", "«Как читать исследования» перенесена на 11:30 · зал «Практика».")
        audit(c, "schedule_changed", actor, {"time": "11:30", "room": "Зал «Практика»"})
    elif step == 5:
        setv(c, "live_state", "pause"); audit(c, "live_state", actor, {"state": "pause"})
    elif step == 6:
        setv(c, "live_state", "live"); audit(c, "live_state", actor, {"state": "live"})
    elif step == 7:
        setv(c, "live_state", "replay"); setv(c, "phase", "after"); audit(c, "live_state", actor, {"state": "replay"})
    elif step == 8:
        c.execute("INSERT OR IGNORE INTO checkins(ticket,ts,staff) VALUES('DEMO-2027-001',?,'staff@demo.ru')", (now,))
        audit(c, "checkin", "staff@demo.ru", {"ticket": "DEMO-2027-001"})
    elif step == 9:
        c.execute("UPDATE placements SET status='active',ts=? WHERE id=1", (now,))
        c.execute("UPDATE deliverables SET status='delivered',evidence='demo_run:event:placement_active',updated=? WHERE id IN ('PL-01','PL-02')", (now,))
        audit(c, "placement_active", "partner@demo.ru", {"placement_id": 1})
    elif step == 10:
        c.execute("INSERT INTO leads(kind,status,ts) VALUES('materials','new',?)", (now,))
        c.execute("UPDATE placements SET leads=leads+1 WHERE id=1")
        c.execute("UPDATE deliverables SET status='delivered',evidence='demo_run:event:voluntary_lead',updated=? WHERE id='PL-04'", (now,))
        audit(c, "voluntary_lead", "participant@demo.ru", {"kind": "materials", "consent": True, "recipient": "demo_partner"})
    elif step == 11:
        c.execute("INSERT OR REPLACE INTO journeys(email,attended,replay,club,updated) VALUES('participant@demo.ru',1,1,0,?)", (now,))
        c.execute("UPDATE deliverables SET status='delivered',evidence='demo_run:event:journey_replay',updated=? WHERE id='PL-03'", (now,))
        audit(c, "journey_attended", "participant@demo.ru", {})
        audit(c, "journey_replay", "participant@demo.ru", {})
    else:
        raise ValueError("bad_step")
    setv(c, "demo_step", step)
