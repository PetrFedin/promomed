-- Scope partner demo planning to governance-registered institutions.
-- Project 026 and task execution 027 migrations MUST remain checksum-stable.
-- Immutable scope: never silently transfer one partner's project to another institution.
CREATE TABLE IF NOT EXISTS partner_collab_project_scopes (
  project_id TEXT PRIMARY KEY REFERENCES partner_collab_projects(id),
  organization_id TEXT NOT NULL REFERENCES institutional_organizations(id),
  demo_only INTEGER NOT NULL CHECK(demo_only IN (0,1)),
  linked_by TEXT NOT NULL,
  created_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_partner_collab_project_scope_org
  ON partner_collab_project_scopes(organization_id,created_at,project_id);
DROP TRIGGER IF EXISTS partner_collab_project_scopes_immutable ON partner_collab_project_scopes;
CREATE TRIGGER partner_collab_project_scopes_immutable
 BEFORE UPDATE OR DELETE ON partner_collab_project_scopes
 FOR EACH ROW EXECUTE FUNCTION promomed_block_partner_collab_ledger_mutation();
