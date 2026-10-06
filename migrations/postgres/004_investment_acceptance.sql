CREATE TABLE IF NOT EXISTS investment_acceptances(
  id TEXT PRIMARY KEY,
  tranche_id TEXT NOT NULL,
  acceptance_key TEXT NOT NULL,
  expected_owner TEXT NOT NULL,
  status TEXT NOT NULL,
  evidence_ref TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '',
  accepted_by TEXT,
  accepted_at BIGINT,
  record_hash TEXT,
  demo_only INTEGER NOT NULL DEFAULT 1,
  UNIQUE(tranche_id, acceptance_key)
);

CREATE INDEX IF NOT EXISTS idx_investment_acceptances_tranche
ON investment_acceptances(tranche_id, status);
