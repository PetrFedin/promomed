CREATE TABLE IF NOT EXISTS institutional_federated_anchors(
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  anchor_version TEXT NOT NULL,
  issuer_id TEXT NOT NULL,
  key_id TEXT NOT NULL,
  alg TEXT NOT NULL CHECK(alg='Ed25519'),
  public_key_b64 TEXT NOT NULL,
  proof_challenge TEXT NOT NULL,
  source_ref TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  rotated_from_anchor_id TEXT,
  created_at INTEGER NOT NULL,
  created_by TEXT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0,
  UNIQUE(organization_id,issuer_id,key_id)
);

CREATE TABLE IF NOT EXISTS institutional_federated_anchor_state(
  anchor_id TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK(status IN (
    'pending_proof','pending_governance','active','retired','suspended','revoked'
  )),
  proof_verified_at INTEGER,
  proof_signature_b64 TEXT,
  valid_from INTEGER,
  valid_until INTEGER,
  activated_at INTEGER,
  activated_by TEXT,
  retired_at INTEGER,
  suspended_at INTEGER,
  suspended_by TEXT,
  suspension_reason TEXT NOT NULL DEFAULT '',
  revoked_at INTEGER,
  revoked_by TEXT,
  revocation_reason TEXT NOT NULL DEFAULT '',
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS institutional_federated_anchor_events(
  id TEXT PRIMARY KEY,
  anchor_id TEXT NOT NULL,
  event_type TEXT NOT NULL CHECK(event_type IN (
    'proposed','proof_verified','activated','retired','suspended','revoked'
  )),
  actor TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  event_sha256 TEXT NOT NULL UNIQUE,
  created_at INTEGER NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS institutional_signed_verification_receipts(
  id TEXT PRIMARY KEY,
  receipt_version TEXT NOT NULL,
  bundle_id TEXT NOT NULL,
  verifier_organization_id TEXT NOT NULL,
  anchor_id TEXT NOT NULL,
  issuer_id TEXT NOT NULL,
  key_id TEXT NOT NULL,
  verification_status TEXT NOT NULL,
  receipt_body_json TEXT NOT NULL,
  receipt_sha256 TEXT NOT NULL UNIQUE,
  signature_b64 TEXT NOT NULL,
  verified_at INTEGER NOT NULL,
  admitted_at INTEGER NOT NULL,
  submitted_by TEXT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0,
  UNIQUE(bundle_id,verifier_organization_id,receipt_sha256)
);

CREATE INDEX IF NOT EXISTS idx_federated_anchor_org
  ON institutional_federated_anchors(organization_id,created_at);

CREATE INDEX IF NOT EXISTS idx_federated_anchor_state
  ON institutional_federated_anchor_state(status,updated_at);

CREATE INDEX IF NOT EXISTS idx_federated_anchor_event
  ON institutional_federated_anchor_events(anchor_id,created_at);

CREATE INDEX IF NOT EXISTS idx_signed_verification_receipt_org
  ON institutional_signed_verification_receipts(verifier_organization_id,verified_at);

CREATE TRIGGER IF NOT EXISTS institutional_federated_anchors_no_update
BEFORE UPDATE ON institutional_federated_anchors
BEGIN SELECT RAISE(ABORT,'immutable_institutional_federated_anchor'); END;

CREATE TRIGGER IF NOT EXISTS institutional_federated_anchors_no_delete
BEFORE DELETE ON institutional_federated_anchors
BEGIN SELECT RAISE(ABORT,'immutable_institutional_federated_anchor'); END;

CREATE TRIGGER IF NOT EXISTS institutional_federated_anchor_events_no_update
BEFORE UPDATE ON institutional_federated_anchor_events
BEGIN SELECT RAISE(ABORT,'immutable_institutional_federated_anchor_event'); END;

CREATE TRIGGER IF NOT EXISTS institutional_federated_anchor_events_no_delete
BEFORE DELETE ON institutional_federated_anchor_events
BEGIN SELECT RAISE(ABORT,'immutable_institutional_federated_anchor_event'); END;

CREATE TRIGGER IF NOT EXISTS institutional_signed_verification_receipts_no_update
BEFORE UPDATE ON institutional_signed_verification_receipts
BEGIN SELECT RAISE(ABORT,'immutable_institution_signed_verification_receipt'); END;

CREATE TRIGGER IF NOT EXISTS institutional_signed_verification_receipts_no_delete
BEFORE DELETE ON institutional_signed_verification_receipts
BEGIN SELECT RAISE(ABORT,'immutable_institution_signed_verification_receipt'); END;
