CREATE TABLE IF NOT EXISTS federation_interoperability_profiles(
  id TEXT PRIMARY KEY,
  profile_version TEXT NOT NULL UNIQUE,
  profile_sha256 TEXT NOT NULL UNIQUE,
  profile_json TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('active','deprecated','retired')),
  effective_at BIGINT NOT NULL,
  created_at BIGINT NOT NULL,
  created_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS federation_profile_evaluations(
  id TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL,
  organization_id TEXT NOT NULL,
  anchor_id TEXT,
  compatibility_status TEXT NOT NULL CHECK(compatibility_status IN (
    'compatible','compatible_with_warnings','incompatible','no_active_anchor'
  )),
  evaluation_sha256 TEXT NOT NULL UNIQUE,
  evaluation_json TEXT NOT NULL,
  evaluated_at BIGINT NOT NULL,
  evaluated_by TEXT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS federation_discovery_bundles(
  id TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL,
  organization_id TEXT,
  bundle_sha256 TEXT NOT NULL UNIQUE,
  bundle_json TEXT NOT NULL,
  issued_at BIGINT NOT NULL,
  valid_until BIGINT NOT NULL,
  created_by TEXT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_federation_profile_eval_org
  ON federation_profile_evaluations(organization_id,evaluated_at);

CREATE INDEX IF NOT EXISTS idx_federation_discovery_bundle_org
  ON federation_discovery_bundles(organization_id,issued_at);

CREATE OR REPLACE FUNCTION promomed_block_federation_interop_audit_mutation()
RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'immutable_federation_interop_audit';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS federation_interoperability_profiles_no_update ON federation_interoperability_profiles;
CREATE TRIGGER federation_interoperability_profiles_no_update
BEFORE UPDATE OR DELETE ON federation_interoperability_profiles
FOR EACH ROW EXECUTE FUNCTION promomed_block_federation_interop_audit_mutation();

DROP TRIGGER IF EXISTS federation_profile_evaluations_no_update ON federation_profile_evaluations;
CREATE TRIGGER federation_profile_evaluations_no_update
BEFORE UPDATE OR DELETE ON federation_profile_evaluations
FOR EACH ROW EXECUTE FUNCTION promomed_block_federation_interop_audit_mutation();

DROP TRIGGER IF EXISTS federation_discovery_bundles_no_update ON federation_discovery_bundles;
CREATE TRIGGER federation_discovery_bundles_no_update
BEFORE UPDATE OR DELETE ON federation_discovery_bundles
FOR EACH ROW EXECUTE FUNCTION promomed_block_federation_interop_audit_mutation();
