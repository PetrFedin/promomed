import time


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
    d["program"] = [dict(r) for r in c.execute("SELECT * FROM program_items ORDER BY start,venue")]
    d["speakers"] = [dict(r) for r in c.execute("SELECT * FROM speakers ORDER BY name")]
    d["partners"] = [dict(r) for r in c.execute("SELECT * FROM partners ORDER BY name")]
    d["products"] = [dict(r) for r in c.execute("SELECT * FROM product_catalog ORDER BY id")]
    d["content_catalog"] = [dict(r) for r in c.execute("SELECT * FROM content_catalog ORDER BY id")]
    d["partner_packages"] = [dict(r) for r in c.execute("SELECT * FROM partner_packages ORDER BY id")]
    d["studio_episodes"] = [dict(r) for r in c.execute(
        "SELECT e.*,s.name speaker_name,s.role speaker_role FROM studio_episodes e LEFT JOIN speakers s ON s.id=e.speaker_id ORDER BY e.id"
    )]
    d["community_threads"] = [dict(r) for r in c.execute(
        "SELECT t.*,COUNT(p.id) post_count FROM community_threads t LEFT JOIN community_posts p ON p.thread_id=t.id AND p.status IN ('published_demo','pending_moderation') GROUP BY t.id ORDER BY t.id"
    )]
    d["learning_tracks"] = [dict(r) for r in c.execute("SELECT * FROM learning_tracks ORDER BY id")]
    d["learning_steps"] = [dict(r) for r in c.execute("SELECT * FROM learning_steps ORDER BY track_id,step_no")]
    d["session_speakers"] = [dict(r) for r in c.execute(
        "SELECT ss.item_id,s.id,s.name,s.role,s.org,s.kind FROM session_speakers ss JOIN speakers s ON s.id=ss.speaker_id ORDER BY ss.item_id,s.name"
    )]
    d["appointment_slots"] = [dict(r) for r in c.execute(
        'SELECT a.*,p.name partner_name FROM appointment_slots a LEFT JOIN partners p ON p.id=a.partner_id ORDER BY a.start'
    )]
    d["venue_state"] = [dict(r) for r in c.execute(
        "SELECT venue,capacity,occupied,status,next_change,updated FROM venue_state ORDER BY venue"
    )]
    d["stream_state"] = [dict(r) for r in c.execute(
        "SELECT item_id,status,health,delay_sec,updated FROM stream_state ORDER BY item_id"
    )]
    d["incidents"] = [dict(r) for r in c.execute(
        "SELECT id,venue,severity,title,status,recovery,ts,resolved FROM incidents ORDER BY id DESC LIMIT 20"
    )]
    d["staff_assignments"] = [dict(r) for r in c.execute(
        "SELECT id,staff_name,role,venue,shift_start,shift_end,status,updated FROM staff_assignments ORDER BY venue,role"
    )]
    d["speaker_readiness"] = [dict(r) for r in c.execute(
        "SELECT r.speaker_id,r.item_id,r.status,r.checkin,r.briefed,r.mic,r.slides,r.updated,s.name,p.title,p.start,p.venue FROM speaker_readiness r JOIN speakers s ON s.id=r.speaker_id JOIN program_items p ON p.id=r.item_id ORDER BY p.start,s.name"
    )]
    d["ops_broadcasts"] = [dict(r) for r in c.execute(
        "SELECT id,audience,venue,title,body,status,ts FROM ops_broadcasts ORDER BY id DESC LIMIT 12"
    )]
    if email:
        d["takeaways"] = [dict(r) for r in c.execute(
            "SELECT id,session_id,note,source,ts FROM takeaways WHERE email=? ORDER BY id DESC LIMIT 8", (email,)
        )]
        d["meeting_items"] = [dict(r) for r in c.execute(
            "SELECT id,target,slot,place,status,ts FROM meetings WHERE requester=? ORDER BY id DESC LIMIT 8", (email,)
        )]
        d["mutual_meetings"] = [dict(r) for r in c.execute(
            "SELECT id,requester,target_email,target_name,slot,place,status,requester_ok,target_ok,ts FROM mutual_meetings WHERE requester=? OR target_email=? ORDER BY id DESC LIMIT 12",
            (email, email),
        )]
        d["product_interests"] = [dict(r) for r in c.execute(
            "SELECT id,track,context,consent_version,status,ts FROM product_interests WHERE email=? ORDER BY id DESC LIMIT 8", (email,)
        )]
        d["followups"] = [dict(r) for r in c.execute(
            "SELECT day,track,status,ts FROM followups WHERE email=? ORDER BY day,id", (email,)
        )]
        d["activity_bookings"] = [dict(r) for r in c.execute(
            'SELECT b.item_id,b.status,p.start,p."end",p.venue,p.title,p.format FROM activity_bookings b JOIN program_items p ON p.id=b.item_id WHERE b.email=? ORDER BY p.start',
            (email,),
        )]
        d["appointment_bookings"] = [dict(r) for r in c.execute(
            'SELECT b.slot_id,b.status,a.item_id,a.start,a."end",p.name partner_name FROM appointment_bookings b JOIN appointment_slots a ON a.id=b.slot_id LEFT JOIN partners p ON p.id=a.partner_id WHERE b.email=? ORDER BY a.start',
            (email,),
        )]
        d["appointment_history"] = [dict(r) for r in c.execute(
            "SELECT action,from_slot,to_slot,ts FROM appointment_history WHERE email=? ORDER BY id DESC LIMIT 10", (email,)
        )]
        d["session_attendance"] = [dict(r) for r in c.execute(
            "SELECT a.item_id,a.status,a.checkin_ts,a.checkout_ts,a.source,p.title,p.venue,p.track FROM session_attendance a JOIN program_items p ON p.id=a.item_id WHERE a.email=? ORDER BY a.checkin_ts DESC",
            (email,),
        )]
        d["partner_engagement"] = [dict(r) for r in c.execute(
            "SELECT partner,kind,ref_id,consent,ts FROM partner_engagement WHERE email=? ORDER BY id DESC LIMIT 12", (email,)
        )]
        d["challenges"] = [dict(r) for r in c.execute(
            "SELECT challenge_id,status,days_required,started,verified,reward FROM challenges WHERE email=?", (email,)
        )]
        d["challenge_actions"] = [dict(r) for r in c.execute(
            "SELECT challenge_id,action_id,label,status,ts FROM challenge_actions WHERE email=? ORDER BY action_id", (email,)
        )]
        d["topic_subscriptions"] = [dict(r) for r in c.execute(
            "SELECT topic,status,ts FROM topic_subscriptions WHERE email=? ORDER BY topic", (email,)
        )]
        d["expert_follows"] = [dict(r) for r in c.execute(
            "SELECT f.speaker_id,f.status,f.ts,s.name,s.role,s.org FROM expert_follows f JOIN speakers s ON s.id=f.speaker_id WHERE f.email=? ORDER BY s.name",
            (email,),
        )]
        d["learning_enrollments"] = [dict(r) for r in c.execute(
            "SELECT e.track_id,e.status,e.current_step,e.started,e.updated,t.title,t.duration_days,t.topic,(SELECT COUNT(*) FROM learning_steps ls WHERE ls.track_id=e.track_id) total_steps FROM learning_enrollments e JOIN learning_tracks t ON t.id=e.track_id WHERE e.email=? ORDER BY e.updated DESC",
            (email,),
        )]
        d["community_posts"] = [dict(r) for r in c.execute(
            "SELECT id,thread_id,body,status,ts FROM community_posts WHERE email=? ORDER BY id DESC LIMIT 12", (email,)
        )]
        d["direct_messages"] = [dict(r) for r in c.execute(
            "SELECT id,sender,recipient,context,body,status,ts FROM direct_messages WHERE sender=? OR recipient=? ORDER BY id DESC LIMIT 40",
            (email, email),
        )]
        rel = "registered"
        if c.execute("SELECT 1 FROM checkins WHERE ticket='DEMO-2027-001'").fetchone():
            rel = "attended"
        if c.execute("SELECT 1 FROM journeys WHERE email=? AND (replay=1 OR club=1)", (email,)).fetchone():
            rel = "continuing"
        if c.execute("SELECT 1 FROM product_interests WHERE email=?", (email,)).fetchone():
            rel = "consented_interest"
        d["relationship_stage"] = rel
    p = c.execute("SELECT status,name FROM placements WHERE id=1").fetchone()
    d["placement_status"] = p["status"] if p else "contracted"
    row = c.execute("SELECT status,version FROM cms WHERE id='A-014'").fetchone()
    d["cms_status"] = row["status"]
    d["cms_version"] = row["version"]
    if email:
        b = c.execute("SELECT status FROM bookings WHERE email=? AND session_id='S2'", (email,)).fetchone()
        d["my_booking"] = b["status"] if b else None
        n = c.execute(
            "SELECT id,kind,title,body,seen,ts FROM notifications WHERE email=? ORDER BY id DESC LIMIT 5", (email,)
        )
        d["notifications"] = [dict(x) for x in n]
        pr = c.execute(
            "SELECT intent,interests,networking,visibility FROM attendee_profiles WHERE email=?", (email,)
        ).fetchone()
        d["profile"] = dict(pr) if pr else None
        pp = c.execute("SELECT content,event,network,partner FROM passport WHERE email=?", (email,)).fetchone()
        d["passport"] = dict(pp) if pp else {"content": 0, "event": 0, "network": 0, "partner": 0}
        d["meetings"] = c.execute(
            "SELECT COUNT(*) n FROM meetings WHERE requester=? AND status IN ('requested','confirmed')", (email,)
        ).fetchone()["n"]
    d["server_time"] = int(time.time())
    return d
