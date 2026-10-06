ALTER TABLE content_catalog ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
CREATE TABLE IF NOT EXISTS evidence_sources(
  id TEXT PRIMARY KEY,content_id TEXT NOT NULL,content_version INTEGER NOT NULL,source_type TEXT NOT NULL,
  source_ref TEXT NOT NULL,source_date TEXT,metadata_json TEXT NOT NULL DEFAULT '{}',created_at INTEGER NOT NULL,
  FOREIGN KEY(content_id) REFERENCES content_catalog(id)
);
CREATE TABLE IF NOT EXISTS evidence_reviews(
  id TEXT PRIMARY KEY,content_id TEXT NOT NULL,content_version INTEGER NOT NULL,source_id TEXT NOT NULL,
  reviewer_email TEXT NOT NULL,reviewer_role TEXT NOT NULL,disclosure TEXT NOT NULL,
  decision TEXT NOT NULL CHECK(decision IN ('approved','rejected','needs_changes')),
  reviewed_at INTEGER NOT NULL,valid_until INTEGER,superseded_at INTEGER,
  FOREIGN KEY(content_id) REFERENCES content_catalog(id),FOREIGN KEY(source_id) REFERENCES evidence_sources(id)
);
CREATE INDEX IF NOT EXISTS idx_evidence_sources_content ON evidence_sources(content_id,content_version,created_at);
CREATE INDEX IF NOT EXISTS idx_evidence_reviews_content ON evidence_reviews(content_id,content_version,reviewed_at);
