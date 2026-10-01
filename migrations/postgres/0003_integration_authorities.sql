CREATE TABLE IF NOT EXISTS publication_versions(
 id TEXT PRIMARY KEY,publication_key TEXT NOT NULL,version INTEGER NOT NULL,source_type TEXT,source_ref TEXT,
 title TEXT NOT NULL,body TEXT,author TEXT,disclosure TEXT,state TEXT NOT NULL,snapshot_hash TEXT,
 scheduled_at BIGINT,published_at BIGINT,corrected_at BIGINT,created_at BIGINT NOT NULL,updated_at BIGINT NOT NULL,
 UNIQUE(publication_key,version)
);
CREATE INDEX IF NOT EXISTS idx_publication_key_state ON publication_versions(publication_key,state,version);
CREATE TABLE IF NOT EXISTS editorial_reviews(
 id TEXT PRIMARY KEY,publication_id TEXT NOT NULL,review_kind TEXT NOT NULL,reviewer TEXT NOT NULL,
 decision TEXT NOT NULL,notes TEXT,created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_sources(
 id TEXT PRIMARY KEY,kind TEXT NOT NULL,title TEXT NOT NULL,authors TEXT,identifier TEXT,url TEXT,
 published_date TEXT,imported_from TEXT,metadata_json TEXT,review_status TEXT NOT NULL,created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS citations(
 id TEXT PRIMARY KEY,publication_id TEXT NOT NULL,source_id TEXT NOT NULL,locator TEXT,label TEXT,status TEXT NOT NULL,created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS claim_evidence_links(
 id TEXT PRIMARY KEY,publication_id TEXT NOT NULL,claim_key TEXT NOT NULL,claim_text TEXT NOT NULL,
 source_id TEXT NOT NULL,citation_id TEXT,reviewer_status TEXT NOT NULL,created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviewer_notes(
 id TEXT PRIMARY KEY,publication_id TEXT NOT NULL,source_id TEXT,note TEXT NOT NULL,reviewer TEXT NOT NULL,status TEXT NOT NULL,created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS search_documents(
 document_id TEXT PRIMARY KEY,kind TEXT NOT NULL,title TEXT NOT NULL,body TEXT,topic TEXT,expert_id TEXT,
 event_id TEXT,partner TEXT,review_status TEXT,availability TEXT,updated_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_search_kind_topic ON search_documents(kind,topic);
CREATE TABLE IF NOT EXISTS recommendation_impressions(
 id TEXT PRIMARY KEY,email TEXT NOT NULL,entity_kind TEXT NOT NULL,entity_id TEXT NOT NULL,
 reason_code TEXT NOT NULL,position INTEGER NOT NULL,created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS media_broadcasts(
 id TEXT PRIMARY KEY,item_id TEXT,studio_id TEXT,provider TEXT NOT NULL,provider_broadcast_id TEXT,
 state TEXT NOT NULL,playback_url TEXT,health TEXT,started_at BIGINT,ended_at BIGINT,updated_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS replay_progress(
 email TEXT NOT NULL,item_id TEXT NOT NULL,position_sec INTEGER NOT NULL,duration_sec INTEGER,updated_at BIGINT NOT NULL,
 PRIMARY KEY(email,item_id)
);
CREATE TABLE IF NOT EXISTS transcript_jobs(
 id TEXT PRIMARY KEY,media_id TEXT NOT NULL,provider TEXT NOT NULL,state TEXT NOT NULL,source_ref TEXT,
 checksum TEXT,created_at BIGINT NOT NULL,updated_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS transcript_segments(
 id TEXT PRIMARY KEY,job_id TEXT NOT NULL,start_ms INTEGER NOT NULL,end_ms INTEGER NOT NULL,
 speaker TEXT,text TEXT NOT NULL,source_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS generated_takeaways(
 id TEXT PRIMARY KEY,job_id TEXT NOT NULL,start_ms INTEGER NOT NULL,end_ms INTEGER NOT NULL,
 text TEXT NOT NULL,state TEXT NOT NULL,reviewed_by TEXT,reviewed_at BIGINT
);
CREATE TABLE IF NOT EXISTS virtual_rooms(
 id TEXT PRIMARY KEY,item_id TEXT,provider TEXT NOT NULL,room_ref TEXT NOT NULL,title TEXT NOT NULL,
 state TEXT NOT NULL,capacity INTEGER,starts_at BIGINT,ends_at BIGINT,created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS virtual_room_bookings(
 email TEXT NOT NULL,room_id TEXT NOT NULL,status TEXT NOT NULL,consent_version TEXT NOT NULL,created_at BIGINT NOT NULL,
 PRIMARY KEY(email,room_id)
);
CREATE TABLE IF NOT EXISTS virtual_room_attendance(
 email TEXT NOT NULL,room_id TEXT NOT NULL,status TEXT NOT NULL,joined_at BIGINT,left_at BIGINT,
 PRIMARY KEY(email,room_id)
);
CREATE TABLE IF NOT EXISTS programme_proposals(
 id TEXT PRIMARY KEY,topic TEXT NOT NULL,title TEXT NOT NULL,format TEXT,proposer TEXT,state TEXT NOT NULL,
 disclosure TEXT,created_at BIGINT NOT NULL,updated_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS speaker_invitations(
 id TEXT PRIMARY KEY,proposal_id TEXT NOT NULL,speaker_id TEXT,email TEXT,state TEXT NOT NULL,conflict_disclosure TEXT,updated_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS production_checklists(
 id TEXT PRIMARY KEY,proposal_id TEXT NOT NULL,item_key TEXT NOT NULL,status TEXT NOT NULL,owner TEXT,deadline TEXT,updated_at BIGINT NOT NULL,
 UNIQUE(proposal_id,item_key)
);
CREATE TABLE IF NOT EXISTS programme_revisions(
 id TEXT PRIMARY KEY,revision_no INTEGER NOT NULL,state TEXT NOT NULL,snapshot_json TEXT NOT NULL,snapshot_hash TEXT NOT NULL,
 approved_by TEXT,created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS expert_qualifications(
 id TEXT PRIMARY KEY,speaker_id TEXT NOT NULL,qualification TEXT NOT NULL,organisation TEXT,source_id TEXT,
 review_state TEXT NOT NULL,created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS expert_disclosures(
 id TEXT PRIMARY KEY,speaker_id TEXT NOT NULL,declaration TEXT NOT NULL,state TEXT NOT NULL,valid_from TEXT,valid_to TEXT,updated_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS expert_publications(
 id TEXT PRIMARY KEY,speaker_id TEXT NOT NULL,source_id TEXT NOT NULL,relationship TEXT NOT NULL,review_state TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS expert_profile_versions(
 id TEXT PRIMARY KEY,speaker_id TEXT NOT NULL,version INTEGER NOT NULL,state TEXT NOT NULL,snapshot_json TEXT NOT NULL,
 snapshot_hash TEXT NOT NULL,reviewed_by TEXT,created_at BIGINT NOT NULL,UNIQUE(speaker_id,version)
);
CREATE TABLE IF NOT EXISTS partner_contacts(
 id TEXT PRIMARY KEY,partner_id TEXT NOT NULL,name TEXT NOT NULL,role TEXT,email TEXT,phone TEXT,state TEXT NOT NULL,updated_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS partner_commitments(
 id TEXT PRIMARY KEY,partner_id TEXT NOT NULL,package_id TEXT,commitment TEXT NOT NULL,state TEXT NOT NULL,owner TEXT,deadline TEXT,updated_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS partner_workspace_deliverables(
 id TEXT PRIMARY KEY,partner_id TEXT NOT NULL,commitment_id TEXT,label TEXT NOT NULL,state TEXT NOT NULL,evidence_id TEXT,updated_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS partner_evidence(
 id TEXT PRIMARY KEY,partner_id TEXT NOT NULL,kind TEXT NOT NULL,ref TEXT,summary TEXT,checksum TEXT,created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS partner_renewals(
 id TEXT PRIMARY KEY,partner_id TEXT NOT NULL,state TEXT NOT NULL,period TEXT,notes TEXT,updated_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS participant_consented_leads(
 id TEXT PRIMARY KEY,partner_id TEXT,email TEXT NOT NULL,purpose TEXT NOT NULL,consent_version TEXT NOT NULL,
 state TEXT NOT NULL,created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS notification_deliveries(
 id TEXT PRIMARY KEY,notification_id TEXT,email TEXT NOT NULL,provider TEXT NOT NULL,template_key TEXT NOT NULL,
 state TEXT NOT NULL,correlation_id TEXT NOT NULL UNIQUE,attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT,updated_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS venue_assets(
 id TEXT PRIMARY KEY,version INTEGER NOT NULL,geojson TEXT NOT NULL,asset_hash TEXT NOT NULL,state TEXT NOT NULL,created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS venue_pois(
 id TEXT PRIMARY KEY,asset_id TEXT NOT NULL,kind TEXT NOT NULL,label TEXT NOT NULL,properties_json TEXT,created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS webhook_receipts(
 provider TEXT NOT NULL,event_id TEXT NOT NULL,checksum TEXT NOT NULL,status TEXT NOT NULL,processed_at BIGINT NOT NULL,
 PRIMARY KEY(provider,event_id)
);
CREATE TABLE IF NOT EXISTS integration_gates(
 gate_key TEXT PRIMARY KEY,status TEXT NOT NULL,rationale TEXT NOT NULL,updated_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS public_web_events(
 id TEXT PRIMARY KEY,event_name TEXT NOT NULL,path TEXT,source TEXT,campaign TEXT,anonymous_session_hash TEXT,created_at BIGINT NOT NULL
);
