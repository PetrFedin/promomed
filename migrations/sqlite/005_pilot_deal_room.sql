CREATE TABLE IF NOT EXISTS deal_obligation_records(
  id TEXT PRIMARY KEY,
  tranche_id TEXT NOT NULL,
  milestone_id TEXT NOT NULL,
  obligation_id TEXT NOT NULL,
  owner TEXT NOT NULL,
  status TEXT NOT NULL,
  evidence_ref TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '',
  accepted_by TEXT,
  accepted_at BIGINT,
  updated_at BIGINT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 1,
  UNIQUE(tranche_id, milestone_id, obligation_id)
);

CREATE INDEX IF NOT EXISTS idx_deal_obligation_records_scope
ON deal_obligation_records(tranche_id, milestone_id, status);

CREATE TABLE IF NOT EXISTS deal_issues(
  id TEXT PRIMARY KEY,
  tranche_id TEXT NOT NULL,
  milestone_id TEXT NOT NULL,
  obligation_id TEXT NOT NULL,
  severity TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL,
  remediation TEXT NOT NULL DEFAULT '',
  owner TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at BIGINT NOT NULL,
  resolved_by TEXT,
  resolved_at BIGINT,
  demo_only INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_deal_issues_scope
ON deal_issues(tranche_id, milestone_id, status);
