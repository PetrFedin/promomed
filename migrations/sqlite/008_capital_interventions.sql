CREATE TABLE IF NOT EXISTS capital_interventions(
  id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  package_id TEXT NOT NULL,
  intervention_type TEXT NOT NULL,
  status TEXT NOT NULL,
  owner TEXT NOT NULL,
  reason TEXT NOT NULL,
  freeze_new_commitments INTEGER NOT NULL DEFAULT 0,
  reallocation_candidate_rub BIGINT NOT NULL DEFAULT 0,
  capital_at_risk_rub BIGINT NOT NULL DEFAULT 0,
  downstream_value_at_risk_rub BIGINT NOT NULL DEFAULT 0,
  note TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at BIGINT NOT NULL,
  resolved_by TEXT,
  resolved_at BIGINT,
  demo_only INTEGER NOT NULL DEFAULT 1,
  UNIQUE(scenario_id, package_id, intervention_type, status)
);

CREATE INDEX IF NOT EXISTS idx_capital_interventions_scope
ON capital_interventions(scenario_id,status,package_id);
