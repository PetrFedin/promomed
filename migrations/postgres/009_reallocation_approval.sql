CREATE TABLE IF NOT EXISTS capital_reallocation_proposals(
  id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  source_capacity_rub BIGINT NOT NULL,
  finance_target_rub BIGINT NOT NULL,
  governance_target_rub BIGINT NOT NULL,
  status TEXT NOT NULL,
  reason TEXT NOT NULL,
  proposed_by TEXT NOT NULL,
  proposed_at BIGINT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS capital_reallocation_approvals(
  id TEXT PRIMARY KEY,
  proposal_id TEXT NOT NULL,
  approval_role TEXT NOT NULL,
  status TEXT NOT NULL,
  actor TEXT,
  accepted_at BIGINT,
  note TEXT NOT NULL DEFAULT '',
  demo_only INTEGER NOT NULL DEFAULT 1,
  UNIQUE(proposal_id, approval_role)
);

CREATE INDEX IF NOT EXISTS idx_capital_reallocation_approvals
ON capital_reallocation_approvals(proposal_id,status);
