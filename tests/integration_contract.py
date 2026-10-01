import os
import secrets

import server
from app import analytics, media, notifications, partners, recommendations, search
from app.content import import_snapshot
from app.domain import record_webhook
from app.evidence import add_source, link_claim, sources_for_publication
from app.gates import list_gates
from app.integration_api import handle_post
from app.providers import post_json

ALLOWED_REASONS={
    "follows_expert","subscribed_topic","attended_related_session",
    "continue_learning_track","popular_in_selected_topic",
}

def main():
    c=server.conn()
    suffix=secrets.token_hex(4)
    try:
        denied=handle_post(
            "/api/publications/create",
            {"title":"Forbidden"},
            ("participant","Participant","participant@demo.ru"),
            c,
        )
        assert denied["status"]==403,denied

        missing=handle_post(
            "/api/publications/import",
            {"provider":"directus","external_id":"missing-"+suffix,"version":1,"title":"Draft","state":"published"},
            ("editor","Editor","editor@demo.ru"),
            c,
        )
        assert missing["status"]==422,missing

        pub=import_snapshot(c,{
            "provider":"directus","external_id":"approved-"+suffix,"version":1,
            "title":"Reviewed demo publication",
            "body":"Educational demo content. No individual diagnosis or treatment advice.",
            "disclosure":"DEMO / editorial concept",
            "state":"published",
            "review_chain":[{"kind":"editorial"},{"kind":"medical"},{"kind":"compliance"}],
        },"directus")
        assert pub["state"]=="published" and pub["snapshot_hash"],pub

        src=add_source(c,{
            "id":"source-"+suffix,"kind":"publication","title":"Verified editorial source metadata",
            "identifier":"doi:demo-"+suffix,"review_status":"reviewed","imported_from":"zotero",
        },"editor@demo.ru")
        linked=link_claim(c,{
            "publication_id":pub["id"],"source_id":src["id"],
            "claim_key":"claim-"+suffix,"claim_text":"A reviewed educational claim",
            "reviewer_status":"reviewed",
        },"editor@demo.ru")
        assert linked["citation_id"]
        assert len(sources_for_publication(c,pub["id"]))==1

        indexed=search.rebuild(c)
        assert indexed>0
        recs=recommendations.recommend(c,"participant@demo.ru",limit=8,record=True)
        assert recs and all(x["reason_code"] in ALLOWED_REASONS for x in recs),recs
        assert post_json("",{})["error"]=="provider_not_configured"

        job=media.create_transcript_job(c,{"media_id":"demo-"+suffix,"source_ref":"demo://recording"},"editor@demo.ru")
        bad=handle_post(
            "/api/transcript/takeaway",
            {"job_id":job["id"],"start_ms":0,"end_ms":1000,"text":"No source"},
            ("editor","Editor","editor@demo.ru"),
            c,
        )
        assert bad["status"]==422,bad
        media.add_segment(c,job["id"],{"start_ms":0,"end_ms":5000,"text":"Timecoded source segment"},"editor@demo.ru")
        take=media.create_takeaway(c,job["id"],{"start_ms":1000,"end_ms":3000,"text":"Generated takeaway"},"editor@demo.ru")
        assert take["state"]=="generated"
        reviewed=media.review_takeaway(c,take["id"],"approved","editor@demo.ru")
        assert reviewed["state"]=="approved" and reviewed["reviewed_by"]=="editor@demo.ru"

        event_id="event-"+suffix
        first=record_webhook(c,"test-provider",event_id,{"state":"live"})
        second=record_webhook(c,"test-provider",event_id,{"state":"live"})
        assert first["accepted"] is True and second["accepted"] is False,(first,second)

        lead=partners.create_consented_lead(c,"participant@demo.ru","PR01","materials","partner-lead-v1")
        assert lead
        consent=c.execute(
            "SELECT granted FROM consent_records WHERE email=? AND purpose='partner_lead' ORDER BY ts DESC LIMIT 1",
            ("participant@demo.ru",)
        ).fetchone()
        assert consent and int(consent["granted"])==1

        correlation=notifications.queue(c,"contract-"+suffix,"participant@demo.ru","replay_ready")
        notifications.queue(c,"contract-"+suffix,"participant@demo.ru","replay_ready")
        count=c.execute("SELECT COUNT(*) n FROM notification_deliveries WHERE correlation_id=?",(correlation,)).fetchone()["n"]
        assert count==1,count

        rejected=False
        try:
            analytics.capture(c,{"event_name":"medical_risk_score","path":"/"})
        except ValueError:
            rejected=True
        assert rejected
        analytics.capture(c,{"event_name":"page_view","path":"/media","anonymous_session_hash":"anon-"+suffix})

        gates={x["gate_key"]:x["status"] for x in list_gates(c)}
        assert gates["community_scale"]=="deferred"
        assert gates["learning_lms"]=="deferred"
        assert gates["clinical_fhir"]=="deferred"
        assert gates["wellness_routines"]=="reference"

        print("PROMOMED integration contract PASS")
    finally:
        c.rollback()
        c.close()

if __name__=="__main__":
    main()
