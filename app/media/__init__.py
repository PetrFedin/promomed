import os
from app.domain import audit, consent, hash_text, now, record_webhook, uid

OWNCAST=os.environ.get("OWNCAST_BASE_URL","").rstrip("/")
JITSI=os.environ.get("JITSI_BASE_URL","https://meet.jit.si").rstrip("/")

def provider_status():
    return {"owncast_connected":bool(OWNCAST),"jitsi_base":JITSI,"videojs":"frontend"}

def upsert_broadcast(c,data,actor):
    bid=str(data.get("id") or uid("broadcast"))[:100]
    provider=str(data.get("provider") or "owncast")
    state=str(data.get("state") or "scheduled")
    c.execute("""INSERT INTO media_broadcasts(id,item_id,studio_id,provider,provider_broadcast_id,state,playback_url,health,started_at,ended_at,updated_at)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                 provider_broadcast_id=excluded.provider_broadcast_id,state=excluded.state,playback_url=excluded.playback_url,
                 health=excluded.health,started_at=excluded.started_at,ended_at=excluded.ended_at,updated_at=excluded.updated_at""",
              (bid,str(data.get("item_id") or ""),str(data.get("studio_id") or ""),provider,
               str(data.get("provider_broadcast_id") or ""),state,str(data.get("playback_url") or ""),
               str(data.get("health") or "unknown"),data.get("started_at"),data.get("ended_at"),now()))
    audit(c,"media_broadcast_upserted",actor,{"id":bid,"state":state,"provider":provider})
    return dict(c.execute("SELECT * FROM media_broadcasts WHERE id=?",(bid,)).fetchone())

def media_webhook(c,provider,event_id,payload):
    receipt=record_webhook(c,provider,event_id,payload)
    if not receipt["accepted"]:
        return {"duplicate":True,**receipt}
    ref=str(payload.get("broadcast_id") or payload.get("id") or "")
    state=str(payload.get("state") or "")
    if ref and state:
        c.execute("UPDATE media_broadcasts SET state=?,health=?,updated_at=? WHERE provider_broadcast_id=?",
                  (state,str(payload.get("health") or "unknown"),now(),ref))
    audit(c,"media_provider_webhook",provider,{"event_id":event_id,"state":state})
    return {"duplicate":False,**receipt}

def save_progress(c,email,item_id,position_sec,duration_sec):
    c.execute("""INSERT INTO replay_progress(email,item_id,position_sec,duration_sec,updated_at) VALUES(?,?,?,?,?)
                 ON CONFLICT(email,item_id) DO UPDATE SET position_sec=excluded.position_sec,duration_sec=excluded.duration_sec,updated_at=excluded.updated_at""",
              (email,item_id,max(0,int(position_sec)),max(0,int(duration_sec or 0)),now()))
    audit(c,"replay_progress",email,{"item_id":item_id,"position_sec":max(0,int(position_sec))})

def create_transcript_job(c,data,actor):
    jid=str(data.get("id") or uid("transcript"))
    source_ref=str(data.get("source_ref") or "")
    c.execute("INSERT INTO transcript_jobs(id,media_id,provider,state,source_ref,checksum,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
              (jid,str(data.get("media_id") or ""),str(data.get("provider") or "internal"),"queued",source_ref,hash_text(source_ref),now(),now()))
    audit(c,"transcript_job_created",actor,{"job_id":jid})
    return dict(c.execute("SELECT * FROM transcript_jobs WHERE id=?",(jid,)).fetchone())

def add_segment(c,job_id,data,actor):
    sid=str(data.get("id") or uid("segment"))
    start_ms=max(0,int(data.get("start_ms") or 0)); end_ms=max(start_ms,int(data.get("end_ms") or start_ms))
    text=str(data.get("text") or "").strip()
    if not text: raise ValueError("text_required")
    source_hash=hash_text(f"{job_id}|{start_ms}|{end_ms}|{text}")
    c.execute("INSERT INTO transcript_segments(id,job_id,start_ms,end_ms,speaker,text,source_hash) VALUES(?,?,?,?,?,?,?)",
              (sid,job_id,start_ms,end_ms,str(data.get("speaker") or ""),text,source_hash))
    c.execute("UPDATE transcript_jobs SET state='processing',updated_at=? WHERE id=?",(now(),job_id))
    audit(c,"transcript_segment_added",actor,{"job_id":job_id,"segment_id":sid,"start_ms":start_ms,"end_ms":end_ms})
    return {"id":sid,"source_hash":source_hash}

def create_takeaway(c,job_id,data,actor):
    start_ms=max(0,int(data.get("start_ms") or 0)); end_ms=max(start_ms,int(data.get("end_ms") or start_ms))
    segment=c.execute("SELECT 1 FROM transcript_segments WHERE job_id=? AND start_ms<=? AND end_ms>=? LIMIT 1",(job_id,start_ms,end_ms)).fetchone()
    if not segment: raise ValueError("source_time_range_required")
    tid=uid("takeaway")
    c.execute("INSERT INTO generated_takeaways(id,job_id,start_ms,end_ms,text,state,reviewed_by,reviewed_at) VALUES(?,?,?,?,?,'generated',NULL,NULL)",
              (tid,job_id,start_ms,end_ms,str(data.get("text") or "").strip()))
    audit(c,"generated_takeaway_created",actor,{"takeaway_id":tid,"job_id":job_id,"start_ms":start_ms,"end_ms":end_ms})
    return dict(c.execute("SELECT * FROM generated_takeaways WHERE id=?",(tid,)).fetchone())

def review_takeaway(c,tid,decision,actor):
    if decision not in ("approved","rejected"): raise ValueError("bad_decision")
    c.execute("UPDATE generated_takeaways SET state=?,reviewed_by=?,reviewed_at=? WHERE id=?",(decision,actor,now(),tid))
    audit(c,"generated_takeaway_reviewed",actor,{"takeaway_id":tid,"decision":decision})
    row=c.execute("SELECT * FROM generated_takeaways WHERE id=?",(tid,)).fetchone()
    return dict(row) if row else None

def create_room(c,data,actor):
    rid=str(data.get("id") or uid("room"))
    ref=str(data.get("room_ref") or ("sostoyanie-"+rid))
    c.execute("INSERT INTO virtual_rooms(id,item_id,provider,room_ref,title,state,capacity,starts_at,ends_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
              (rid,str(data.get("item_id") or ""),"jitsi",ref,str(data.get("title") or "Expert AMA"),str(data.get("state") or "scheduled"),
               max(1,int(data.get("capacity") or 40)),data.get("starts_at"),data.get("ends_at"),now()))
    audit(c,"virtual_room_created",actor,{"room_id":rid})
    return room(c,rid,None)

def room(c,rid,email):
    row=c.execute("SELECT * FROM virtual_rooms WHERE id=?",(rid,)).fetchone()
    if not row: return None
    d=dict(row); d["join_url"]=JITSI+"/"+d["room_ref"]
    if email:
        b=c.execute("SELECT status,consent_version FROM virtual_room_bookings WHERE email=? AND room_id=?",(email,rid)).fetchone()
        d["booking"]=dict(b) if b else None
    return d

def book_room(c,email,rid,consent_version):
    if not c.execute("SELECT 1 FROM virtual_rooms WHERE id=?",(rid,)).fetchone(): raise LookupError("room_not_found")
    c.execute("""INSERT INTO virtual_room_bookings(email,room_id,status,consent_version,created_at) VALUES(?,?,'booked',?,?)
                 ON CONFLICT(email,room_id) DO UPDATE SET status='booked',consent_version=excluded.consent_version,created_at=excluded.created_at""",
              (email,rid,consent_version,now()))
    consent(c,email,"virtual_expert_room",consent_version,True,"participant_action",rid)
    audit(c,"virtual_room_booked",email,{"room_id":rid})
