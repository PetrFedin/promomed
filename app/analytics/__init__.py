import os
from app.domain import audit, now, uid
from app.providers import post_json

UMAMI_URL=os.environ.get("UMAMI_API_URL","").rstrip("/")
UMAMI_KEY=os.environ.get("UMAMI_API_KEY","")

ALLOWED_EVENTS={"page_view","landing_conversion","campaign_landing"}

def capture(c,data):
    name=str(data.get("event_name") or "")
    if name not in ALLOWED_EVENTS:
        raise ValueError("event_not_allowed")
    eid=uid("web")
    c.execute("""INSERT INTO public_web_events(id,event_name,path,source,campaign,anonymous_session_hash,created_at)
                 VALUES(?,?,?,?,?,?,?)""",
              (eid,name,str(data.get("path") or "")[:300],str(data.get("source") or "")[:120],
               str(data.get("campaign") or "")[:120],str(data.get("anonymous_session_hash") or "")[:128],now()))
    provider={"ok":False,"error":"provider_not_configured"}
    if UMAMI_URL:
        provider=post_json(UMAMI_URL,{"type":"event","payload":{"name":name,"url":str(data.get("path") or "")}},
                           {"Authorization":"Bearer "+UMAMI_KEY} if UMAMI_KEY else {})
    return {"id":eid,"provider_forwarded":bool(provider.get("ok"))}

def summary(c):
    return [dict(r) for r in c.execute("""SELECT event_name,source,campaign,COUNT(*) events
                                          FROM public_web_events GROUP BY event_name,source,campaign
                                          ORDER BY events DESC,event_name""")]
