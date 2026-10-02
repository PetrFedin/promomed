def snapshot(c, email=None):
    if not email:
        return {}
    d = {
        "takeaways": [dict(r) for r in c.execute(
            "SELECT id,session_id,note,source,ts FROM takeaways WHERE email=? ORDER BY id DESC LIMIT 8", (email,)
        )],
        "followups": [dict(r) for r in c.execute(
            "SELECT day,track,status,ts FROM followups WHERE email=? ORDER BY day,id", (email,)
        )],
        "notifications": [dict(r) for r in c.execute(
            "SELECT id,kind,title,body,seen,ts FROM notifications WHERE email=? ORDER BY id DESC LIMIT 5", (email,)
        )],
    }
    profile = c.execute(
        "SELECT intent,interests,networking,visibility FROM attendee_profiles WHERE email=?", (email,)
    ).fetchone()
    d["profile"] = dict(profile) if profile else None
    passport = c.execute("SELECT content,event,network,partner FROM passport WHERE email=?", (email,)).fetchone()
    d["passport"] = dict(passport) if passport else {"content": 0, "event": 0, "network": 0, "partner": 0}
    rel = "registered"
    if c.execute("SELECT 1 FROM checkins WHERE ticket='DEMO-2027-001'").fetchone():
        rel = "attended"
    if c.execute("SELECT 1 FROM journeys WHERE email=? AND (replay=1 OR club=1)", (email,)).fetchone():
        rel = "continuing"
    if c.execute("SELECT 1 FROM product_interests WHERE email=?", (email,)).fetchone():
        rel = "consented_interest"
    d["relationship_stage"] = rel
    return d
