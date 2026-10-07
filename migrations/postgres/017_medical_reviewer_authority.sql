CREATE TABLE IF NOT EXISTS reviewer_profiles(
 id TEXT PRIMARY KEY,
 account_email TEXT NOT NULL UNIQUE REFERENCES accounts(email),
 display_name TEXT NOT NULL,
 reviewer_kind TEXT NOT NULL DEFAULT 'medical_scientific',
 credential_state TEXT NOT NULL DEFAULT 'pending' CHECK(credential_state IN ('pending','demo_attested','verified','revoked')),
 credential_ref TEXT NOT NULL DEFAULT '',
 credential_issuer TEXT NOT NULL DEFAULT '',
 credential_verified_by TEXT,
 credential_verified_at BIGINT,
 valid_until BIGINT,
 independent_attested INTEGER NOT NULL DEFAULT 0,
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','suspended','revoked')),
 created_at BIGINT NOT NULL,
 updated_at BIGINT NOT NULL,
 demo_only INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS reviewer_scopes(
 id TEXT PRIMARY KEY,
 reviewer_id TEXT NOT NULL REFERENCES reviewer_profiles(id),
 scope_key TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','suspended','revoked')),
 verified_by TEXT,
 verified_at BIGINT,
 valid_until BIGINT,
 demo_only INTEGER NOT NULL DEFAULT 0,
 UNIQUE(reviewer_id,scope_key)
);

CREATE TABLE IF NOT EXISTS review_assignments(
 id TEXT PRIMARY KEY,
 candidate_id TEXT NOT NULL REFERENCES evidence_admission_candidates(id),
 review_role TEXT NOT NULL CHECK(review_role IN ('scientific')),
 reviewer_id TEXT NOT NULL REFERENCES reviewer_profiles(id),
 required_scope TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'assigned' CHECK(status IN ('assigned','completed','recused','conflict_hold','cancelled')),
 assigned_by TEXT NOT NULL,
 assigned_at BIGINT NOT NULL,
 completed_at BIGINT,
 demo_only INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_review_assignments_candidate ON review_assignments(candidate_id,review_role,status);

CREATE TABLE IF NOT EXISTS review_conflict_disclosures(
 id TEXT PRIMARY KEY,
 assignment_id TEXT NOT NULL REFERENCES review_assignments(id),
 reviewer_id TEXT NOT NULL REFERENCES reviewer_profiles(id),
 conflict_state TEXT NOT NULL CHECK(conflict_state IN ('none','potential','material')),
 details TEXT NOT NULL DEFAULT '',
 disclosed_at BIGINT NOT NULL,
 demo_only INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_review_conflicts_assignment ON review_conflict_disclosures(assignment_id,disclosed_at);

CREATE TABLE IF NOT EXISTS review_decisions(
 id TEXT PRIMARY KEY,
 assignment_id TEXT NOT NULL UNIQUE REFERENCES review_assignments(id),
 candidate_id TEXT NOT NULL REFERENCES evidence_admission_candidates(id),
 reviewer_id TEXT NOT NULL REFERENCES reviewer_profiles(id),
 decision TEXT NOT NULL CHECK(decision IN ('accept','reject','request_changes')),
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

CREATE OR REPLACE FUNCTION promomed_block_review_audit_mutation()
RETURNS trigger AS $$
BEGIN
 RAISE EXCEPTION 'immutable_review_audit';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS review_decisions_no_update ON review_decisions;
CREATE TRIGGER review_decisions_no_update BEFORE UPDATE OR DELETE ON review_decisions
FOR EACH ROW EXECUTE FUNCTION promomed_block_review_audit_mutation();

DROP TRIGGER IF EXISTS review_authority_events_no_update ON review_authority_events;
CREATE TRIGGER review_authority_events_no_update BEFORE UPDATE OR DELETE ON review_authority_events
FOR EACH ROW EXECUTE FUNCTION promomed_block_review_audit_mutation();
