CREATE TABLE IF NOT EXISTS pilot_charters(
  id TEXT PRIMARY KEY,
  version INTEGER NOT NULL,
  status TEXT NOT NULL,
  title TEXT NOT NULL,
  objective TEXT NOT NULL,
  decision_owner_role TEXT NOT NULL,
  sponsor_role TEXT NOT NULL,
  operations_owner_role TEXT NOT NULL,
  created_by TEXT NOT NULL,
  approved_by TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  approved_at INTEGER,
  locked_at INTEGER
);

CREATE TABLE IF NOT EXISTS pilot_kpis(
  id TEXT PRIMARY KEY,
  charter_id TEXT NOT NULL,
  name TEXT NOT NULL,
  formula TEXT NOT NULL,
  source TEXT NOT NULL,
  target TEXT NOT NULL,
  status TEXT NOT NULL,
  required INTEGER NOT NULL DEFAULT 1,
  baseline_version INTEGER NOT NULL DEFAULT 1,
  approved_by TEXT,
  approved_at INTEGER,
  actual_value TEXT,
  actual_source TEXT,
  actual_updated_at INTEGER
);

CREATE TABLE IF NOT EXISTS pilot_deliverables(
  id TEXT PRIMARY KEY,
  charter_id TEXT NOT NULL,
  label TEXT NOT NULL,
  acceptance_criterion TEXT NOT NULL,
  evidence_required TEXT NOT NULL,
  owner_role TEXT NOT NULL,
  acceptor_role TEXT NOT NULL,
  status TEXT NOT NULL,
  evidence TEXT,
  accepted_by TEXT,
  accepted_at INTEGER
);

CREATE TABLE IF NOT EXISTS pilot_signoffs(
  id TEXT PRIMARY KEY,
  charter_id TEXT NOT NULL,
  role TEXT NOT NULL,
  status TEXT NOT NULL,
  actor TEXT,
  signed_at INTEGER
);

CREATE TABLE IF NOT EXISTS pilot_changes(
  id TEXT PRIMARY KEY,
  charter_id TEXT NOT NULL,
  item_type TEXT NOT NULL,
  item_id TEXT NOT NULL,
  field_name TEXT NOT NULL,
  old_value TEXT,
  new_value TEXT NOT NULL,
  rationale TEXT NOT NULL,
  actor TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  resolved_by TEXT,
  resolved_at INTEGER
);

CREATE TABLE IF NOT EXISTS pilot_decisions(
  id TEXT PRIMARY KEY,
  charter_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  rationale TEXT NOT NULL,
  actor TEXT NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pilot_kpis_charter ON pilot_kpis(charter_id);
CREATE INDEX IF NOT EXISTS idx_pilot_deliverables_charter ON pilot_deliverables(charter_id);
CREATE INDEX IF NOT EXISTS idx_pilot_signoffs_charter ON pilot_signoffs(charter_id);
CREATE INDEX IF NOT EXISTS idx_pilot_changes_charter ON pilot_changes(charter_id);
CREATE INDEX IF NOT EXISTS idx_pilot_decisions_charter ON pilot_decisions(charter_id);
