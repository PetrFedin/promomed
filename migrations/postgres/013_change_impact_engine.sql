CREATE TABLE IF NOT EXISTS knowledge_change_events(
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  summary TEXT NOT NULL,
  severity_hint TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  detected_at BIGINT NOT NULL,
  created_by TEXT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS knowledge_impacts(
  id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  target_kind TEXT NOT NULL,
  target_ref TEXT NOT NULL,
  impact_reason TEXT NOT NULL,
  severity TEXT NOT NULL,
  owner TEXT NOT NULL,
  deadline_at BIGINT NOT NULL,
  status TEXT NOT NULL DEFAULT 'review_required',
  audience_count INTEGER NOT NULL DEFAULT 0,
  demo_only INTEGER NOT NULL DEFAULT 1,
  UNIQUE(event_id,claim_id,target_kind,target_ref)
);

CREATE TABLE IF NOT EXISTS publication_holds(
  id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL,
  artifact_kind TEXT NOT NULL,
  artifact_ref TEXT NOT NULL,
  reason TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  placed_at BIGINT NOT NULL,
  placed_by TEXT NOT NULL,
  released_at BIGINT,
  released_by TEXT,
  demo_only INTEGER NOT NULL DEFAULT 1,
  UNIQUE(event_id,artifact_kind,artifact_ref)
);

CREATE TABLE IF NOT EXISTS knowledge_review_cases(
  id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL,
  owner TEXT NOT NULL,
  severity TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  deadline_at BIGINT NOT NULL,
  resolution TEXT NOT NULL DEFAULT '',
  resolved_by TEXT,
  resolved_at BIGINT,
  demo_only INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_knowledge_impacts_event_status ON knowledge_impacts(event_id,status,severity);
CREATE INDEX IF NOT EXISTS idx_publication_holds_artifact ON publication_holds(artifact_kind,artifact_ref,status);
CREATE INDEX IF NOT EXISTS idx_knowledge_review_cases_status ON knowledge_review_cases(status,severity,deadline_at);
