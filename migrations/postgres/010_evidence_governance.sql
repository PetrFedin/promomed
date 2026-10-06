ALTER TABLE content_catalog ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
CREATE TABLE IF NOT EXISTS evidence_sources(
  id TEXT PRIMARY KEY,content_id TEXT NOT NULL REFERENCES content_catalog(id),content_version INTEGER NOT NULL,
  source_type TEXT NOT NULL,source_ref TEXT NOT NULL,source_date TEXT,metadata_json TEXT NOT NULL DEFAULT '{}',created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_reviews(
  id TEXT PRIMARY KEY,content_id TEXT NOT NULL REFERENCES content_catalog(id),content_version INTEGER NOT NULL,
  source_id TEXT NOT NULL REFERENCES evidence_sources(id),reviewer_email TEXT NOT NULL,reviewer_role TEXT NOT NULL,
  disclosure TEXT NOT NULL,decision TEXT NOT NULL CHECK(decision IN ('approved','rejected','needs_changes')),
  reviewed_at BIGINT NOT NULL,valid_until BIGINT,superseded_at BIGINT
);
CREATE INDEX IF NOT EXISTS idx_evidence_sources_content ON evidence_sources(content_id,content_version,created_at);
CREATE INDEX IF NOT EXISTS idx_evidence_reviews_content ON evidence_reviews(content_id,content_version,reviewed_at);
