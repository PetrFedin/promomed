import time

from app import community, content, learning, operations, participant, partners, programme


def commercial(c):
    kinds = {r["kind"]: r["n"] for r in c.execute("SELECT kind,COUNT(*) n FROM events GROUP BY kind")}
    regs = c.execute("SELECT COUNT(*) n FROM registrations").fetchone()["n"]
    checkins = c.execute("SELECT COUNT(*) n FROM checkins").fetchone()["n"]
    leads = c.execute("SELECT COUNT(*) n FROM leads WHERE status='new'").fetchone()["n"]
    replay = c.execute("SELECT COUNT(*) n FROM journeys WHERE replay=1").fetchone()["n"]
    wait = c.execute("SELECT COUNT(*) n FROM bookings WHERE status='waitlist'").fetchone()["n"]
    booked = c.execute("SELECT COUNT(*) n FROM bookings WHERE status='booked'").fetchone()["n"]
    return {
        "registrations": regs,
        "attendance": checkins,
        "booked": booked,
        "waitlist": wait,
        "voluntary_leads": leads,
        "post_event_replay": replay,
        "attendance_rate": round(checkins / regs * 100, 1) if regs else 0,
        "lead_rate": round(leads / checkins * 100, 1) if checkins else 0,
        "event_counts": kinds,
    }


def state(c, email=None):
    d = {r["k"]: r["v"] for r in c.execute("SELECT k,v FROM state")}
    d.update(commercial(c))
    d["checkins"] = d["attendance"]
    d["leads"] = d["voluntary_leads"]
    d["post_event"] = d["post_event_replay"]
    d["questions"] = c.execute("SELECT COUNT(*) n FROM questions").fetchone()["n"]

    for projection in (
        content.snapshot(c),
        programme.snapshot(c, email),
        community.snapshot(c, email),
        learning.snapshot(c, email),
        partners.snapshot(c, email),
        operations.snapshot(c),
        participant.snapshot(c, email),
    ):
        d.update(projection)

    d["server_time"] = int(time.time())
    return d
