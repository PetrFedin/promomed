CREATE TABLE IF NOT EXISTS reviewer_profiles(
 id TEXT PRIMARY KEY,
 account_email TEXT NOT NULL UNIQUE,
 display_name TEXT NOT NULL,
 reviewer_kind TEXT NOT NULL DEFAULT 'medical_scientific',
 credential_state TEXT NOT NULL DEFAULT 'pending',
 credential_ref TEXT NOT NULL DEFAULT '',
 credential_issuer TEXT NOT NULL DEFAULT '',
 credential_verified_by TEXT,
 credential_verified_at BIGINT,
 valid_until BIGINT,
 independent_attested INTEGER NOT NULL DEFAULT 0,
 status TEXT NOT NULL DEFAULT 'active',
 created_at BIGINT NOT NULL,
 updated_at BIGINT NOT NULL,
 demo_only INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS reviewer_scopes(
 id TEXT PRIMARY KEY,
 reviewer_id TEXT NOT NULL,
 scope_key TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'active',
 verified_by TEXT,
 verified_at BIGINT,
 valid_until BIGINT,
 demo_only INTEGER NOT NULL DEFAULT 0,
 UNIQUE(reviewer_id,scope_key)
);

CREATE TABLE IF NOT EXISTS review_assignments(
 id TEXT PRIMARY KEY,
 candidate_id TEXT NOT NULL,
 review_role TEXT NOT NULL,
 reviewer_id TEXT NOT NULL,
 required_scope TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'assigned',
 assigned_by TEXT NOT NULL,
 assigned_at BIGINT NOT NULL,
 completed_at BIGINT,
 demo_only INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_review_assignments_candidate ON review_assignments(candidate_id,review_role,status);

CREATE TABLE IF NOT EXISTS review_conflict_disclosures(
 id TEXT PRIMARY KEY,
 assignment_id TEXT NOT NULL,
 reviewer_id TEXT NOT NULL,
 conflict_state TEXT NOT NULL,
 details TEXT NOT NULL DEFAULT '',
 disclosed_at BIGINT NOT NULL,
 demo_only INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_review_conflicts_assignment ON review_conflict_disclosures(assignment_id,disclosed_at);

CREATE TABLE IF NOT EXISTS review_decisions(
 id TEXT PRIMARY KEY,
 assignment_id TEXT NOT NULL UNIQUE,
 candidate_id TEXT NOT NULL,
 reviewer_id TEXT NOT NULL,
 decision TEXT NOT NULL,
 rationale TEXT NOT NULL,
 evidence_snapshot_hash TEXT NOT NULL,
 attestation_method TEXT NOT NULL,
 decision_digest TEXT NOT NULL UNIQUE,
 signed_at BIGINT NOT NULL,
 demo_only INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS review_authority_events(
 id TEXT PRIMARY KEY,
 event_type TEXT NOT NULL,
 candidate_id TEXT,
 assignment_id TEXT,
 actor TEXT NOT NULL,
 payload_json TEXT NOT NULL,
 prev_hash TEXT NOT NULL DEFAULT '',
 event_hash TEXT NOT NULL UNIQUE,
 created_at BIGINT NOT NULL,
 demo_only INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_review_authority_events_chain ON review_authority_events(created_at,id);

CREATE TRIGGER IF NOT EXISTS review_decisions_no_update
BEFORE UPDATE ON review_decisions
BEGIN SELECT RAISE(ABORT,'immutable_review_decision'); END;
CREATE TRIGGER IF NOT EXISTS review_decisions_no_delete
BEFORE DELETE ON review_decisions
BEGIN SELECT RAISE(ABORT,'immutable_review_decision'); END;
CREATE TRIGGER IF NOT EXISTS review_authority_events_no_update
BEFORE UPDATE ON review_authority_events
BEGIN SELECT RAISE(ABORT,'immutable_review_event'); END;
CREATE TRIGGER IF NOT EXISTS review_authority_events_no_delete
BEFORE DELETE ON review_authority_events
BEGIN SELECT RAISE(ABORT,'immutable_review_event'); END;
