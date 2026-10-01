import os
from app.domain import audit, now, uid
from app.providers import post_json

NOVU_URL=os.environ.get("NOVU_API_URL","").rstrip("/")
NOVU_KEY=os.environ.get("NOVU_API_KEY","")

def queue(c,notification_id,email,template_key):
    correlation="notification:"+str(notification_id)
    did=uid("delivery")
    provider="novu" if NOVU_URL else "in_app"
    c.execute("""INSERT INTO notification_deliveries(id,notification_id,email,provider,template_key,state,correlation_id,attempts,last_error,updated_at)
                 VALUES(?,?,?,?,?,'queued',?,0,NULL,?) ON CONFLICT(correlation_id) DO NOTHING""",
              (did,str(notification_id),email,provider,template_key,correlation,now()))
    return correlation

def dispatch(c,limit=20):
    rows=[dict(r) for r in c.execute("SELECT * FROM notification_deliveries WHERE state='queued' ORDER BY updated_at LIMIT ?",(max(1,min(int(limit),100)),))]
    results=[]
    for row in rows:
        if row["provider"]=="in_app":
            c.execute("UPDATE notification_deliveries SET state='delivered_in_app',attempts=attempts+1,updated_at=? WHERE id=?",(now(),row["id"]))
            results.append({"id":row["id"],"state":"delivered_in_app"})
            continue
        res=post_json(NOVU_URL,{"name":row["template_key"],"to":row["email"],"payload":{"notification_id":row["notification_id"]}},
                      {"Authorization":"ApiKey "+NOVU_KEY} if NOVU_KEY else {})
        state="sent" if res.get("ok") else "retry"
        c.execute("UPDATE notification_deliveries SET state=?,attempts=attempts+1,last_error=?,updated_at=? WHERE id=?",
                  (state,None if res.get("ok") else res.get("error","provider_error"),now(),row["id"]))
        results.append({"id":row["id"],"state":state})
    return results
