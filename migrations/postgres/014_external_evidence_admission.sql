CREATE TABLE IF NOT EXISTS evidence_watch_targets(
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  external_id TEXT NOT NULL,
  canonical_key TEXT NOT NULL,
  source_id TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  created_by TEXT NOT NULL,
  created_at BIGINT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 1,
  UNIQUE(provider,external_id)
);

CREATE TABLE IF NOT EXISTS evidence_provider_snapshots(
  id TEXT PRIMARY KEY,
  target_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  external_id TEXT NOT NULL,
  normalized_json TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  provider_status TEXT NOT NULL,
  version_marker TEXT NOT NULL DEFAULT '',
  fetched_at BIGINT NOT NULL,
  is_current INTEGER NOT NULL DEFAULT 1,
  demo_only INTEGER NOT NULL DEFAULT 1,
  UNIQUE(target_id,payload_hash)
);

CREATE TABLE IF NOT EXISTS evidence_admission_candidates(
  id TEXT PRIMARY KEY,
  target_id TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  change_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  reason TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending_review',
  created_at BIGINT NOT NULL,
  admitted_at BIGINT,
  admitted_by TEXT,
  admitted_source_id TEXT,
  change_event_id TEXT,
  demo_only INTEGER NOT NULL DEFAULT 1,
  UNIQUE(target_id,snapshot_id,change_type)
);

CREATE TABLE IF NOT EXISTS evidence_admission_reviews(
  id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL,
  review_role TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'awaiting',
  reviewer TEXT,
  reviewed_at BIGINT,
  note TEXT NOT NULL DEFAULT '',
  demo_only INTEGER NOT NULL DEFAULT 1,
  UNIQUE(candidate_id,review_role)
);

CREATE INDEX IF NOT EXISTS idx_evidence_watch_targets_key ON evidence_watch_targets(canonical_key,status);
CREATE INDEX IF NOT EXISTS idx_evidence_provider_snapshots_target ON evidence_provider_snapshots(target_id,fetched_at);
CREATE INDEX IF NOT EXISTS idx_evidence_admission_candidates_status ON evidence_admission_candidates(status,severity,created_at);
CREATE INDEX IF NOT EXISTS idx_evidence_admission_reviews_candidate ON evidence_admission_reviews(candidate_id,status);
