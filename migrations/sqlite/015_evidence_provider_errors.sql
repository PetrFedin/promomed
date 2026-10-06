CREATE TABLE IF NOT EXISTS evidence_provider_errors(
  id TEXT PRIMARY KEY,
  target_id TEXT,
  provider TEXT NOT NULL,
  external_id TEXT NOT NULL,
  error_type TEXT NOT NULL,
  error_message TEXT NOT NULL,
  occurred_at BIGINT NOT NULL,
  resolved_at BIGINT,
  demo_only INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_evidence_provider_errors_target
ON evidence_provider_errors(target_id,occurred_at);
