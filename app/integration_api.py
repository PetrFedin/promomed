import os
import secrets
from urllib.parse import parse_qs, urlparse

from app import analytics as public_analytics
from app import evidence
from app import media
from app import notifications
from app import partners
from app import programme
from app import recommendations
from app import search
from app.content import create_publication, import_snapshot, list_publications, transition
from app.gates import list_gates, set_gate
from app.providers import env_status
from app.venue import add_poi, create_asset, get_asset

def _q(raw_path):
    parsed=urlparse(raw_path)
    return parsed.path,{k:v[-1] for k,v in parse_qs(parsed.query).items() if v}

def _allowed(auth,*roles):
    return bool(auth and auth[0] in roles)

def _result(status,payload):
    return {"status":status,"payload":payload}

def _error(exc):
    if isinstance(exc,LookupError):
        return _result(404,{"error":str(exc)})
    if isinstance(exc,ValueError):
        return _result(422,{"error":str(exc)})
    return _result(500,{"error":"integration_error"})

def handle_get(raw_path,auth,c):
    path,q=_q(raw_path)
    try:
        if path=="/api/integrations/status":
            return _result(200,{"providers":env_status(),"gates":list_gates(c)})
        if path=="/api/publications":
            public_only=not _allowed(auth,"editor","organizer","sales")
            return _result(200,{"items":list_publications(c,public_only=public_only)})
        if path=="/api/evidence":
            pid=q.get("publication_id","")
            return _result(200,{"publication_id":pid,"sources":evidence.sources_for_publication(c,pid)})
        if path=="/api/search":
            items=search.query(
                c,q=q.get("q",""),kind=q.get("kind"),topic=q.get("topic"),
                review_status=q.get("review_status"),availability=q.get("availability"),
                limit=int(q.get("limit","30") or 30)
            )
            return _result(200,{"items":items,"provider":search.provider_status()})
        if path=="/api/search/semantic":
            return _result(200,{"items":search.semantic(c,q.get("q",""),limit=int(q.get("limit","12") or 12)),"provider":search.provider_status()["semantic"]})
        if path=="/api/recommendations":
            if not _allowed(auth,"participant"): return _result(403,{"error":"forbidden"})
            return _result(200,{"items":recommendations.recommend(c,auth[2],limit=int(q.get("limit","16") or 16),record=True)})
        if path=="/api/media/broadcasts":
            rows=[dict(r) for r in c.execute("SELECT * FROM media_broadcasts ORDER BY updated_at DESC")]
            return _result(200,{"items":rows,"provider":media.provider_status()})
        if path=="/api/transcript":
            job_id=q.get("job_id","")
            job=c.execute("SELECT * FROM transcript_jobs WHERE id=?",(job_id,)).fetchone()
            if not job:return _result(404,{"error":"job_not_found"})
            segments=[dict(r) for r in c.execute("SELECT * FROM transcript_segments WHERE job_id=? ORDER BY start_ms",(job_id,))]
            takeaways=[dict(r) for r in c.execute("SELECT * FROM generated_takeaways WHERE job_id=? ORDER BY start_ms",(job_id,))]
            return _result(200,{"job":dict(job),"segments":segments,"takeaways":takeaways})
        if path=="/api/virtual-rooms":
            rows=[media.room(c,r["id"],auth[2] if auth else None) for r in c.execute("SELECT id FROM virtual_rooms ORDER BY starts_at,id")]
            return _result(200,{"items":rows})
        if path=="/api/programme-production":
            if not _allowed(auth,"editor","organizer","sales"): return _result(403,{"error":"forbidden"})
            rows=[programme.get_proposal(c,r["id"]) for r in c.execute("SELECT id FROM programme_proposals ORDER BY updated_at DESC")]
            revisions=[dict(r) for r in c.execute("SELECT * FROM programme_revisions ORDER BY revision_no DESC")]
            return _result(200,{"proposals":rows,"revisions":revisions})
        if path=="/api/expert":
            sid=q.get("speaker_id","")
            item=programme.profile(c,sid)
            return _result(200,{"expert":item}) if item else _result(404,{"error":"speaker_not_found"})
        if path=="/api/partner-workspace":
            if not _allowed(auth,"partner","organizer","sales"): return _result(403,{"error":"forbidden"})
            item=partners.workspace(c,q.get("partner_id",""))
            return _result(200,{"workspace":item}) if item else _result(404,{"error":"partner_not_found"})
        if path=="/api/notification-deliveries":
            if not _allowed(auth,"organizer","sales"): return _result(403,{"error":"forbidden"})
            rows=[dict(r) for r in c.execute("SELECT * FROM notification_deliveries ORDER BY updated_at DESC LIMIT 100")]
            return _result(200,{"items":rows})
        if path=="/api/venue-map":
            return _result(200,{"asset":get_asset(c,q.get("asset_id"))})
        if path=="/api/integration-gates":
            return _result(200,{"items":list_gates(c)})
        if path=="/api/public-analytics":
            if not _allowed(auth,"organizer","sales"): return _result(403,{"error":"forbidden"})
            return _result(200,{"items":public_analytics.summary(c)})
        if path=="/api/integration-proof":
            if not _allowed(auth,"organizer","sales","editor"): return _result(403,{"error":"forbidden"})
            counts={}
            for name in (
                "publication_versions","evidence_sources","search_documents","recommendation_impressions",
                "media_broadcasts","transcript_jobs","virtual_rooms","programme_proposals",
                "expert_profile_versions","partner_commitments","notification_deliveries",
                "venue_assets","integration_gates","public_web_events"
            ):
                counts[name]=c.execute("SELECT COUNT(*) n FROM "+name).fetchone()["n"]
            return _result(200,{"ok":True,"contract":"PROMOMED_INTEGRATION_MASTER_PLAN_2026-10-01","counts":counts,"providers":env_status(),"gates":list_gates(c)})
        return None
    except Exception as exc:
        return _error(exc)

def handle_public_post(raw_path,data,headers,c):
    path,_=_q(raw_path)
    try:
        if path=="/api/public-analytics/capture":
            return _result(200,public_analytics.capture(c,data))
        if path.startswith("/api/provider-webhook/"):
            configured=os.environ.get("PROMOMED_WEBHOOK_SECRET","")
            supplied=headers.get("X-Promomed-Webhook-Secret","")
            if not configured or not supplied or not secrets.compare_digest(configured,supplied):
                return _result(401,{"error":"invalid_webhook_secret"})
            provider=path.rsplit("/",1)[-1]
            event_id=str(data.get("event_id") or data.get("id") or "")
            if not event_id:return _result(422,{"error":"event_id_required"})
            if provider in ("owncast","media"):
                return _result(200,media.media_webhook(c,provider,event_id,data))
            from app.domain import record_webhook
            return _result(200,record_webhook(c,provider,event_id,data))
        return None
    except Exception as exc:
        return _error(exc)

def handle_post(raw_path,data,auth,c):
    path,_=_q(raw_path)
    try:
        actor=auth[2] if auth else "anonymous"
        role=auth[0] if auth else None
        if path=="/api/publications/create":
            if role not in ("editor","organizer"): return _result(403,{"error":"forbidden"})
            return _result(201,create_publication(c,data,actor))
        if path=="/api/publications/transition":
            if role not in ("editor","organizer"): return _result(403,{"error":"forbidden"})
            return _result(200,transition(c,str(data.get("publication_id") or ""),str(data.get("target") or ""),actor,data.get("review_kind"),data.get("notes","")))
        if path=="/api/publications/import":
            if role not in ("editor","organizer"): return _result(403,{"error":"forbidden"})
            return _result(200,import_snapshot(c,data,actor))
        if path=="/api/evidence/source":
            if role not in ("editor","organizer"): return _result(403,{"error":"forbidden"})
            return _result(201,evidence.add_source(c,data,actor))
        if path=="/api/evidence/link":
            if role not in ("editor","organizer"): return _result(403,{"error":"forbidden"})
            return _result(201,evidence.link_claim(c,data,actor))
        if path=="/api/search/rebuild":
            if role not in ("editor","organizer"): return _result(403,{"error":"forbidden"})
            return _result(200,{"indexed":search.rebuild(c),"provider":search.provider_status()})
        if path=="/api/media/broadcast":
            if role!="organizer": return _result(403,{"error":"forbidden"})
            return _result(200,media.upsert_broadcast(c,data,actor))
        if path=="/api/replay-progress":
            if role!="participant": return _result(403,{"error":"forbidden"})
            media.save_progress(c,actor,str(data.get("item_id") or ""),data.get("position_sec",0),data.get("duration_sec",0))
            return _result(200,{"ok":True})
        if path=="/api/transcript/job":
            if role not in ("editor","organizer"): return _result(403,{"error":"forbidden"})
            return _result(201,media.create_transcript_job(c,data,actor))
        if path=="/api/transcript/segment":
            if role not in ("editor","organizer"): return _result(403,{"error":"forbidden"})
            return _result(201,media.add_segment(c,str(data.get("job_id") or ""),data,actor))
        if path=="/api/transcript/takeaway":
            if role not in ("editor","organizer"): return _result(403,{"error":"forbidden"})
            return _result(201,media.create_takeaway(c,str(data.get("job_id") or ""),data,actor))
        if path=="/api/transcript/takeaway-review":
            if role not in ("editor","organizer"): return _result(403,{"error":"forbidden"})
            return _result(200,media.review_takeaway(c,str(data.get("takeaway_id") or ""),str(data.get("decision") or ""),actor))
        if path=="/api/virtual-room":
            if role!="organizer": return _result(403,{"error":"forbidden"})
            return _result(201,media.create_room(c,data,actor))
        if path=="/api/virtual-room/book":
            if role!="participant": return _result(403,{"error":"forbidden"})
            if data.get("consent") is not True:return _result(422,{"error":"consent_required"})
            media.book_room(c,actor,str(data.get("room_id") or ""),str(data.get("consent_version") or "expert-room-v1"))
            return _result(200,{"ok":True})
        if path=="/api/programme/proposal":
            if role not in ("editor","organizer"): return _result(403,{"error":"forbidden"})
            return _result(201,programme.create_proposal(c,data,actor))
        if path=="/api/programme/state":
            if role not in ("editor","organizer"): return _result(403,{"error":"forbidden"})
            return _result(200,programme.set_proposal_state(c,str(data.get("proposal_id") or ""),str(data.get("state") or ""),actor))
        if path=="/api/programme/checklist":
            if role not in ("editor","organizer"): return _result(403,{"error":"forbidden"})
            programme.checklist(c,str(data.get("proposal_id") or ""),str(data.get("item_key") or ""),str(data.get("status") or "pending"),actor,str(data.get("owner") or ""),str(data.get("deadline") or ""))
            return _result(200,{"ok":True})
        if path=="/api/programme/invite":
            if role not in ("editor","organizer"): return _result(403,{"error":"forbidden"})
            return _result(201,{"id":programme.invite_speaker(c,str(data.get("proposal_id") or ""),data,actor)})
        if path=="/api/programme/revision":
            if role!="organizer": return _result(403,{"error":"forbidden"})
            return _result(201,programme.create_revision(c,actor))
        if path=="/api/expert/qualification":
            if role not in ("editor","organizer"): return _result(403,{"error":"forbidden"})
            return _result(201,{"id":programme.add_qualification(c,str(data.get("speaker_id") or ""),data,actor)})
        if path=="/api/expert/disclosure":
            if role not in ("editor","organizer"): return _result(403,{"error":"forbidden"})
            return _result(201,{"id":programme.add_disclosure(c,str(data.get("speaker_id") or ""),data,actor)})
        if path=="/api/expert/version":
            if role not in ("editor","organizer"): return _result(403,{"error":"forbidden"})
            return _result(201,programme.version_profile(c,str(data.get("speaker_id") or ""),actor))
        if path=="/api/partner/contact":
            if role not in ("partner","organizer","sales"): return _result(403,{"error":"forbidden"})
            return _result(200,{"id":partners.upsert_contact(c,str(data.get("partner_id") or ""),data,actor)})
        if path=="/api/partner/commitment":
            if role not in ("partner","organizer","sales"): return _result(403,{"error":"forbidden"})
            return _result(201,{"id":partners.create_commitment(c,str(data.get("partner_id") or ""),data,actor)})
        if path=="/api/partner/evidence":
            if role not in ("partner","organizer","sales"): return _result(403,{"error":"forbidden"})
            return _result(201,{"id":partners.add_evidence(c,str(data.get("partner_id") or ""),data,actor)})
        if path=="/api/partner/lead":
            if role!="participant": return _result(403,{"error":"forbidden"})
            if data.get("consent") is not True:return _result(422,{"error":"consent_required"})
            lid=partners.create_consented_lead(c,actor,str(data.get("partner_id") or ""),str(data.get("purpose") or "materials"),str(data.get("consent_version") or "partner-lead-v1"))
            return _result(201,{"id":lid})
        if path=="/api/notifications/dispatch":
            if role not in ("organizer","sales"): return _result(403,{"error":"forbidden"})
            return _result(200,{"items":notifications.dispatch(c,int(data.get("limit") or 20))})
        if path=="/api/venue-map/asset":
            if role!="organizer": return _result(403,{"error":"forbidden"})
            return _result(201,create_asset(c,data,actor))
        if path=="/api/venue-map/poi":
            if role!="organizer": return _result(403,{"error":"forbidden"})
            return _result(201,{"id":add_poi(c,str(data.get("asset_id") or ""),data,actor)})
        if path=="/api/integration-gate":
            if role!="organizer": return _result(403,{"error":"forbidden"})
            return _result(200,set_gate(c,str(data.get("gate_key") or ""),str(data.get("status") or ""),str(data.get("rationale") or ""),actor))
        return None
    except Exception as exc:
        return _error(exc)
