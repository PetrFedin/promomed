import json
import time


def sval(c, k, default=""):
    r = c.execute("SELECT v FROM state WHERE k=?", (k,)).fetchone()
    return r["v"] if r else default


def setv(c, k, v):
    c.execute(
        "INSERT INTO state(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
        (k, str(v)),
    )


def audit(c, kind, actor, payload=None):
    c.execute(
        "INSERT INTO events(kind,actor,payload,ts) VALUES(?,?,?,?)",
        (kind, actor, json.dumps(payload or {}, ensure_ascii=False), int(time.time())),
    )


def notify(c, email, kind, title, body):
    c.execute(
        "INSERT INTO notifications(email,kind,title,body,seen,ts) VALUES(?,?,?,?,0,?)",
        (email, kind, title, body, int(time.time())),
    )
    audit(c, "notification_created", "system", {"email": email, "kind": kind, "title": title})


def promote_waitlist(c, sid="S2"):
    nxt = c.execute(
        "SELECT email FROM bookings WHERE session_id=? AND status='waitlist' ORDER BY ts,email LIMIT 1",
        (sid,),
    ).fetchone()
    if not nxt:
        return None
    c.execute(
        "UPDATE bookings SET status='booked',ts=? WHERE email=? AND session_id=?",
        (int(time.time()), nxt["email"], sid),
    )
    setv(c, "occupied", int(sval(c, "occupied", "0")) + 1)
    notify(
        c,
        nxt["email"],
        "waitlist_promoted",
        "Вы в программе",
        "Освободилось место. Бронь подтверждена автоматически.",
    )
    audit(c, "waitlist_promoted", "system", {"email": nxt["email"], "session_id": sid})
    return nxt["email"]
