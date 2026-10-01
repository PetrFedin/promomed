from app.domain import now, uid

REASON_PRIORITY={
    "continue_learning_track":0,
    "follows_expert":1,
    "subscribed_topic":2,
    "attended_related_session":3,
    "popular_in_selected_topic":4,
}

def _interests(c,email):
    topics=set()
    profile=c.execute("SELECT interests FROM attendee_profiles WHERE email=?",(email,)).fetchone()
    if profile and profile["interests"]:
        topics.update(x.strip().lower() for x in profile["interests"].split(",") if x.strip())
    topics.update(r["topic"].strip().lower() for r in c.execute("SELECT topic FROM topic_subscriptions WHERE email=? AND status='active'",(email,)))
    return topics

def recommend(c,email,limit=16,record=True):
    candidates={}
    def add(kind,eid,title,reason,topic=""):
        key=(kind,eid)
        candidate={"entity_kind":kind,"entity_id":eid,"title":title,"reason_code":reason,"topic":topic or ""}
        old=candidates.get(key)
        if old is None or REASON_PRIORITY.get(reason,99)<REASON_PRIORITY.get(old["reason_code"],99):
            candidates[key]=candidate

    for r in c.execute("""SELECT e.track_id,t.title,t.topic FROM learning_enrollments e
                          JOIN learning_tracks t ON t.id=e.track_id
                          WHERE e.email=? AND e.status IN ('active','enrolled') ORDER BY e.updated DESC""",(email,)):
        add("learning",r["track_id"],r["title"],"continue_learning_track",r["topic"])

    for r in c.execute("""SELECT f.speaker_id,s.name,s.topics FROM expert_follows f
                          JOIN speakers s ON s.id=f.speaker_id
                          WHERE f.email=? AND f.status='active' ORDER BY s.name""",(email,)):
        add("expert",r["speaker_id"],r["name"],"follows_expert",r["topics"] or "")

    topics=_interests(c,email)
    docs=[dict(r) for r in c.execute("SELECT * FROM search_documents ORDER BY kind,title")]
    for d in docs:
        dt=(d.get("topic") or "").lower()
        if any(t in dt or t in (d.get("title") or "").lower() for t in topics):
            add(d["kind"],d["document_id"],d["title"],"subscribed_topic",d.get("topic") or "")

    attended={r["item_id"] for r in c.execute("SELECT item_id FROM session_attendance WHERE email=? AND status IN ('present','completed')",(email,))}
    if attended:
        for d in docs:
            if d.get("event_id") in attended:
                add(d["kind"],d["document_id"],d["title"],"attended_related_session",d.get("topic") or "")

    if not candidates:
        for d in docs[:max(1,min(int(limit),16))]:
            add(d["kind"],d["document_id"],d["title"],"popular_in_selected_topic",d.get("topic") or "")

    items=sorted(candidates.values(),key=lambda x:(REASON_PRIORITY.get(x["reason_code"],99),x["entity_kind"],x["entity_id"]))[:max(1,min(int(limit),40))]
    if record:
        ts=now()
        for i,item in enumerate(items,1):
            c.execute("INSERT INTO recommendation_impressions(id,email,entity_kind,entity_id,reason_code,position,created_at) VALUES(?,?,?,?,?,?,?)",
                      (uid("rec"),email,item["entity_kind"],item["entity_id"],item["reason_code"],i,ts))
    return items
