def snapshot(c, email=None):
    d = {}
    d["program"] = [dict(r) for r in c.execute("SELECT * FROM program_items ORDER BY start,venue")]
    d["session_speakers"] = [dict(r) for r in c.execute(
        "SELECT ss.item_id,s.id,s.name,s.role,s.org,s.kind FROM session_speakers ss JOIN speakers s ON s.id=ss.speaker_id ORDER BY ss.item_id,s.name"
    )]
    if email:
        d["activity_bookings"] = [dict(r) for r in c.execute(
            'SELECT b.item_id,b.status,p.start,p."end",p.venue,p.title,p.format FROM activity_bookings b JOIN program_items p ON p.id=b.item_id WHERE b.email=? ORDER BY p.start',
            (email,),
        )]
        d["session_attendance"] = [dict(r) for r in c.execute(
            "SELECT a.item_id,a.status,a.checkin_ts,a.checkout_ts,a.source,p.title,p.venue,p.track FROM session_attendance a JOIN program_items p ON p.id=a.item_id WHERE a.email=? ORDER BY a.checkin_ts DESC",
            (email,),
        )]
        b = c.execute("SELECT status FROM bookings WHERE email=? AND session_id='S2'", (email,)).fetchone()
        d["my_booking"] = b["status"] if b else None
    return d
