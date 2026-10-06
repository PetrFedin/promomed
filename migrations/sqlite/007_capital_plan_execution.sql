CREATE TABLE IF NOT EXISTS capital_plan_execution(
  id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  package_id TEXT NOT NULL,
  owner TEXT NOT NULL,
  status TEXT NOT NULL,
  planned_rub BIGINT NOT NULL,
  committed_rub BIGINT NOT NULL DEFAULT 0,
  actual_rub BIGINT NOT NULL DEFAULT 0,
  evidence_status TEXT NOT NULL DEFAULT 'awaiting',
  evidence_ref TEXT NOT NULL DEFAULT '',
  unlocked_value_rub BIGINT NOT NULL DEFAULT 0,
  note TEXT NOT NULL DEFAULT '',
  updated_by TEXT NOT NULL,
  updated_at BIGINT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 1,
  UNIQUE(scenario_id, package_id)
);

CREATE INDEX IF NOT EXISTS idx_capital_plan_execution_status
ON capital_plan_execution(scenario_id,status,evidence_status);
