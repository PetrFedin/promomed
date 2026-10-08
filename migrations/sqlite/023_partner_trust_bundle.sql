CREATE TABLE IF NOT EXISTS institutional_status_snapshots(
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  snapshot_sha256 TEXT NOT NULL UNIQUE,
  envelope_json TEXT NOT NULL,
  issued_at INTEGER NOT NULL,
  valid_until INTEGER NOT NULL,
  supersedes_snapshot_id TEXT,
  created_by TEXT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS institutional_status_snapshot_state(
  snapshot_id TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK(status IN ('current','superseded','revoked')),
  revoked_at INTEGER,
  revoked_by TEXT,
  revocation_reason TEXT NOT NULL DEFAULT '',
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS institutional_status_snapshot_events(
  id TEXT PRIMARY KEY,
  snapshot_id TEXT NOT NULL,
  event_type TEXT NOT NULL CHECK(event_type IN ('issued','superseded','revoked')),
  actor TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  event_sha256 TEXT NOT NULL UNIQUE,
  created_at INTEGER NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS institutional_trust_bundles(
  id TEXT PRIMARY KEY,
  snapshot_id TEXT NOT NULL UNIQUE,
  bundle_version TEXT NOT NULL,
  bundle_sha256 TEXT NOT NULL UNIQUE,
  bundle_json TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  created_by TEXT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS institutional_trust_verifications(
  id TEXT PRIMARY KEY,
  bundle_id TEXT NOT NULL,
  verifier_organization_id TEXT NOT NULL,
  verification_status TEXT NOT NULL CHECK(verification_status IN (
    'valid_bundle','invalid_bundle','expired_snapshot','revoked_snapshot',
    'unknown_issuer','revoked_issuer_key','invalid_signature'
  )),
  snapshot_sha256 TEXT NOT NULL,
  bundle_sha256 TEXT NOT NULL,
  verification_digest TEXT NOT NULL UNIQUE,
  details_json TEXT NOT NULL,
  verified_at INTEGER NOT NULL,
  verified_by TEXT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_status_snapshot_org
  ON institutional_status_snapshots(organization_id,issued_at);

CREATE INDEX IF NOT EXISTS idx_status_snapshot_state
  ON institutional_status_snapshot_state(status,updated_at);

CREATE INDEX IF NOT EXISTS idx_status_snapshot_events
  ON institutional_status_snapshot_events(snapshot_id,created_at);

CREATE INDEX IF NOT EXISTS idx_trust_verification_org
  ON institutional_trust_verifications(verifier_organization_id,verified_at);

CREATE TRIGGER IF NOT EXISTS institutional_status_snapshots_no_update
BEFORE UPDATE ON institutional_status_snapshots
BEGIN SELECT RAISE(ABORT,'immutable_institutional_status_snapshot'); END;

CREATE TRIGGER IF NOT EXISTS institutional_status_snapshots_no_delete
BEFORE DELETE ON institutional_status_snapshots
BEGIN SELECT RAISE(ABORT,'immutable_institutional_status_snapshot'); END;

CREATE TRIGGER IF NOT EXISTS institutional_status_snapshot_events_no_update
BEFORE UPDATE ON institutional_status_snapshot_events
BEGIN SELECT RAISE(ABORT,'immutable_institutional_status_snapshot_event'); END;

CREATE TRIGGER IF NOT EXISTS institutional_status_snapshot_events_no_delete
BEFORE DELETE ON institutional_status_snapshot_events
BEGIN SELECT RAISE(ABORT,'immutable_institutional_status_snapshot_event'); END;

CREATE TRIGGER IF NOT EXISTS institutional_trust_bundles_no_update
BEFORE UPDATE ON institutional_trust_bundles
BEGIN SELECT RAISE(ABORT,'immutable_institutional_trust_bundle'); END;

CREATE TRIGGER IF NOT EXISTS institutional_trust_bundles_no_delete
BEFORE DELETE ON institutional_trust_bundles
BEGIN SELECT RAISE(ABORT,'immutable_institutional_trust_bundle'); END;

CREATE TRIGGER IF NOT EXISTS institutional_trust_verifications_no_update
BEFORE UPDATE ON institutional_trust_verifications
BEGIN SELECT RAISE(ABORT,'immutable_institutional_trust_verification'); END;

CREATE TRIGGER IF NOT EXISTS institutional_trust_verifications_no_delete
BEFORE DELETE ON institutional_trust_verifications
BEGIN SELECT RAISE(ABORT,'immutable_institutional_trust_verification'); END;
