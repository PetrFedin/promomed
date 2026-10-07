CREATE TABLE IF NOT EXISTS institutional_organizations(
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  organization_type TEXT NOT NULL,
  status TEXT NOT NULL,
  external_ref TEXT,
  credential_source TEXT,
  partner_id TEXT,
  created_at INTEGER NOT NULL,
  created_by TEXT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS institutional_role_bindings(
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  role_scope TEXT NOT NULL,
  status TEXT NOT NULL,
  effective_at INTEGER NOT NULL,
  expires_at INTEGER,
  verified_by TEXT NOT NULL,
  verification_ref TEXT,
  demo_only INTEGER NOT NULL DEFAULT 0,
  UNIQUE(organization_id,role_scope)
);

CREATE TABLE IF NOT EXISTS evidence_exchange_packages(
  id TEXT PRIMARY KEY,
  artifact_kind TEXT NOT NULL,
  artifact_ref TEXT NOT NULL,
  profile_version TEXT NOT NULL,
  package_sha256 TEXT NOT NULL UNIQUE,
  checkpoint_sha256 TEXT NOT NULL,
  state TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  created_by TEXT NOT NULL,
  supersedes_package_id TEXT,
  demo_only INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS evidence_exchange_deliveries(
  id TEXT PRIMARY KEY,
  package_id TEXT NOT NULL,
  organization_id TEXT NOT NULL,
  delivery_role TEXT NOT NULL,
  status TEXT NOT NULL,
  delivered_at INTEGER NOT NULL,
  acknowledged_at INTEGER,
  withdrawn_at INTEGER,
  withdrawal_reason TEXT,
  receipt_sha256 TEXT NOT NULL UNIQUE,
  created_by TEXT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_institutional_role_org
  ON institutional_role_bindings(organization_id,status,role_scope);

CREATE INDEX IF NOT EXISTS idx_evidence_exchange_artifact
  ON evidence_exchange_packages(artifact_kind,artifact_ref,created_at);

CREATE INDEX IF NOT EXISTS idx_evidence_exchange_delivery_org
  ON evidence_exchange_deliveries(organization_id,status,delivered_at);
