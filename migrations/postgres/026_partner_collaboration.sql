-- Partner collaboration v1: internal planning, NOT a signed agreement or customer evidence.
CREATE TABLE IF NOT EXISTS partner_collab_projects(
  id TEXT PRIMARY KEY,
  owner_email TEXT NOT NULL,
  title TEXT NOT NULL,
  objective TEXT NOT NULL DEFAULT '',
  format TEXT NOT NULL CHECK(format IN ('event','studio','content','learning','experience')),
  status TEXT NOT NULL CHECK(status IN ('draft','review_requested','changes_requested','internally_reviewed','archived')),
  version INTEGER NOT NULL DEFAULT 1 CHECK(version>0),
  demo_only INTEGER NOT NULL DEFAULT 1 CHECK(demo_only IN (0,1)),
  created_at BIGINT NOT NULL,
  updated_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_partner_collab_owner ON partner_collab_projects(owner_email,updated_at);
CREATE INDEX IF NOT EXISTS idx_partner_collab_status ON partner_collab_projects(status,updated_at);
CREATE TABLE IF NOT EXISTS partner_collab_tasks(
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES partner_collab_projects(id),
  title TEXT NOT NULL,
  lane TEXT NOT NULL CHECK(lane IN ('partner','platform')),
  status TEXT NOT NULL CHECK(status IN ('todo','in_progress','done')),
  version INTEGER NOT NULL DEFAULT 1 CHECK(version>0),
  created_by TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  created_at BIGINT NOT NULL,
  updated_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_partner_collab_task_project ON partner_collab_tasks(project_id,updated_at);
CREATE TABLE IF NOT EXISTS partner_collab_events(
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES partner_collab_projects(id),
  actor_email TEXT NOT NULL,
  actor_role TEXT NOT NULL,
  kind TEXT NOT NULL,
  detail TEXT NOT NULL,
  created_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_partner_collab_event_project ON partner_collab_events(project_id,created_at);
CREATE TABLE IF NOT EXISTS partner_collab_operations(
  actor_email TEXT NOT NULL,
  operation_id TEXT NOT NULL,
  route TEXT NOT NULL,
  request_sha256 TEXT NOT NULL,
  result_json TEXT NOT NULL,
  created_at BIGINT NOT NULL,
  PRIMARY KEY(actor_email,operation_id)
);

CREATE OR REPLACE FUNCTION promomed_block_partner_collab_ledger_mutation()
RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'immutable_partner_collab_ledger';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS partner_collab_events_immutable ON partner_collab_events;
CREATE TRIGGER partner_collab_events_immutable BEFORE UPDATE OR DELETE ON partner_collab_events
FOR EACH ROW EXECUTE FUNCTION promomed_block_partner_collab_ledger_mutation();
DROP TRIGGER IF EXISTS partner_collab_operations_immutable ON partner_collab_operations;
CREATE TRIGGER partner_collab_operations_immutable BEFORE UPDATE OR DELETE ON partner_collab_operations
FOR EACH ROW EXECUTE FUNCTION promomed_block_partner_collab_ledger_mutation();
