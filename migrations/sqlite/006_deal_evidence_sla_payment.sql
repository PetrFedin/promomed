CREATE TABLE IF NOT EXISTS deal_evidence_documents(
  id TEXT PRIMARY KEY,
  tranche_id TEXT NOT NULL,
  milestone_id TEXT NOT NULL,
  obligation_id TEXT NOT NULL,
  title TEXT NOT NULL,
  document_type TEXT NOT NULL,
  storage_ref TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  status TEXT NOT NULL,
  owner TEXT NOT NULL,
  registered_by TEXT NOT NULL,
  registered_at BIGINT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_deal_evidence_scope
ON deal_evidence_documents(tranche_id,milestone_id,obligation_id,status);

CREATE TABLE IF NOT EXISTS deal_obligation_sla(
  id TEXT PRIMARY KEY,
  tranche_id TEXT NOT NULL,
  milestone_id TEXT NOT NULL,
  obligation_id TEXT NOT NULL,
  owner TEXT NOT NULL,
  due_at BIGINT NOT NULL,
  escalation_owner TEXT NOT NULL,
  escalation_level TEXT NOT NULL DEFAULT 'none',
  escalated_at BIGINT,
  updated_at BIGINT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 1,
  UNIQUE(tranche_id,milestone_id,obligation_id)
);

CREATE INDEX IF NOT EXISTS idx_deal_obligation_sla_due
ON deal_obligation_sla(tranche_id,milestone_id,due_at);

CREATE TABLE IF NOT EXISTS deal_payment_requests(
  id TEXT PRIMARY KEY,
  tranche_id TEXT NOT NULL,
  milestone_id TEXT NOT NULL,
  amount_rub BIGINT NOT NULL,
  status TEXT NOT NULL,
  requested_by TEXT NOT NULL,
  requested_at BIGINT NOT NULL,
  finance_owner TEXT NOT NULL,
  evidence_packet_hash TEXT NOT NULL,
  payment_authorized INTEGER NOT NULL DEFAULT 0,
  demo_only INTEGER NOT NULL DEFAULT 1,
  UNIQUE(tranche_id,milestone_id)
);

CREATE INDEX IF NOT EXISTS idx_deal_payment_requests_scope
ON deal_payment_requests(tranche_id,milestone_id,status);
