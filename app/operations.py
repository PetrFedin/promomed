def snapshot(c):
    return {
        "venue_state": [dict(r) for r in c.execute(
            "SELECT venue,capacity,occupied,status,next_change,updated FROM venue_state ORDER BY venue"
        )],
        "stream_state": [dict(r) for r in c.execute(
            "SELECT item_id,status,health,delay_sec,updated FROM stream_state ORDER BY item_id"
        )],
        "incidents": [dict(r) for r in c.execute(
            "SELECT id,venue,severity,title,status,recovery,ts,resolved FROM incidents ORDER BY id DESC LIMIT 20"
        )],
        "staff_assignments": [dict(r) for r in c.execute(
            "SELECT id,staff_name,role,venue,shift_start,shift_end,status,updated FROM staff_assignments ORDER BY venue,role"
        )],
        "speaker_readiness": [dict(r) for r in c.execute(
            "SELECT r.speaker_id,r.item_id,r.status,r.checkin,r.briefed,r.mic,r.slides,r.updated,s.name,p.title,p.start,p.venue FROM speaker_readiness r JOIN speakers s ON s.id=r.speaker_id JOIN program_items p ON p.id=r.item_id ORDER BY p.start,s.name"
        )],
        "ops_broadcasts": [dict(r) for r in c.execute(
            "SELECT id,audience,venue,title,body,status,ts FROM ops_broadcasts ORDER BY id DESC LIMIT 12"
        )],
    }
