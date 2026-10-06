CREATE TABLE IF NOT EXISTS evidence_sources(
  id TEXT PRIMARY KEY,
  source_kind TEXT NOT NULL,
  title TEXT NOT NULL,
  publisher TEXT NOT NULL DEFAULT '',
  source_ref TEXT NOT NULL DEFAULT '',
  published_at TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active',
  disclosure TEXT NOT NULL DEFAULT '',
  demo_only INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS evidence_claims(
  id TEXT PRIMARY KEY,
  artifact_kind TEXT NOT NULL,
  artifact_ref TEXT NOT NULL,
  claim_text TEXT NOT NULL,
  topic TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'draft',
  version INTEGER NOT NULL DEFAULT 1,
  reviewer TEXT,
  reviewed_at BIGINT,
  supersedes_claim_id TEXT,
  correction_note TEXT NOT NULL DEFAULT '',
  demo_only INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS evidence_citations(
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  locator TEXT NOT NULL,
  quote_excerpt TEXT NOT NULL DEFAULT '',
  support_type TEXT NOT NULL DEFAULT 'supports',
  status TEXT NOT NULL DEFAULT 'active',
  demo_only INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS evidence_links(
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL,
  target_kind TEXT NOT NULL,
  target_ref TEXT NOT NULL,
  relation TEXT NOT NULL,
  start_sec INTEGER,
  end_sec INTEGER,
  demo_only INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_evidence_claim_artifact ON evidence_claims(artifact_kind,artifact_ref,status);
CREATE INDEX IF NOT EXISTS idx_evidence_citation_claim ON evidence_citations(claim_id,status);
CREATE INDEX IF NOT EXISTS idx_evidence_link_claim ON evidence_links(claim_id,target_kind);
