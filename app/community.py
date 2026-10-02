def snapshot(c, email=None):
    d = {
        "community_threads": [dict(r) for r in c.execute(
            "SELECT t.*,COUNT(p.id) post_count FROM community_threads t LEFT JOIN community_posts p ON p.thread_id=t.id AND p.status IN ('published_demo','pending_moderation') GROUP BY t.id ORDER BY t.id"
        )],
    }
    if email:
        d["mutual_meetings"] = [dict(r) for r in c.execute(
            "SELECT id,requester,target_email,target_name,slot,place,status,requester_ok,target_ok,ts FROM mutual_meetings WHERE requester=? OR target_email=? ORDER BY id DESC LIMIT 12",
            (email, email),
        )]
        d["topic_subscriptions"] = [dict(r) for r in c.execute(
            "SELECT topic,status,ts FROM topic_subscriptions WHERE email=? ORDER BY topic", (email,)
        )]
        d["expert_follows"] = [dict(r) for r in c.execute(
            "SELECT f.speaker_id,f.status,f.ts,s.name,s.role,s.org FROM expert_follows f JOIN speakers s ON s.id=f.speaker_id WHERE f.email=? ORDER BY s.name",
            (email,),
        )]
        d["community_posts"] = [dict(r) for r in c.execute(
            "SELECT id,thread_id,body,status,ts FROM community_posts WHERE email=? ORDER BY id DESC LIMIT 12", (email,)
        )]
        d["direct_messages"] = [dict(r) for r in c.execute(
            "SELECT id,sender,recipient,context,body,status,ts FROM direct_messages WHERE sender=? OR recipient=? ORDER BY id DESC LIMIT 40",
            (email, email),
        )]
    return d
