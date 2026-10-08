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
  created_at BIGINT NOT NULL,
  created_by TEXT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0,
  UNIQUE(organization_id,issuer_id,key_id)
);

CREATE TABLE IF NOT EXISTS institutional_federated_anchor_state(
  anchor_id TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK(status IN (
    'pending_proof','pending_governance','active','retired','suspended','revoked'
  )),
  proof_verified_at BIGINT,
  proof_signature_b64 TEXT,
  valid_from BIGINT,
  valid_until BIGINT,
  activated_at BIGINT,
  activated_by TEXT,
  retired_at BIGINT,
  suspended_at BIGINT,
  suspended_by TEXT,
  suspension_reason TEXT NOT NULL DEFAULT '',
  revoked_at BIGINT,
  revoked_by TEXT,
  revocation_reason TEXT NOT NULL DEFAULT '',
  updated_at BIGINT NOT NULL
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
  created_at BIGINT NOT NULL,
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
  verified_at BIGINT NOT NULL,
  admitted_at BIGINT NOT NULL,
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

CREATE OR REPLACE FUNCTION promomed_block_federated_trust_audit_mutation()
RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'immutable_federated_trust_audit';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS institutional_federated_anchors_no_update ON institutional_federated_anchors;
CREATE TRIGGER institutional_federated_anchors_no_update
BEFORE UPDATE OR DELETE ON institutional_federated_anchors
FOR EACH ROW EXECUTE FUNCTION promomed_block_federated_trust_audit_mutation();

DROP TRIGGER IF EXISTS institutional_federated_anchor_events_no_update ON institutional_federated_anchor_events;
CREATE TRIGGER institutional_federated_anchor_events_no_update
BEFORE UPDATE OR DELETE ON institutional_federated_anchor_events
FOR EACH ROW EXECUTE FUNCTION promomed_block_federated_trust_audit_mutation();

DROP TRIGGER IF EXISTS institutional_signed_verification_receipts_no_update ON institutional_signed_verification_receipts;
CREATE TRIGGER institutional_signed_verification_receipts_no_update
BEFORE UPDATE OR DELETE ON institutional_signed_verification_receipts
FOR EACH ROW EXECUTE FUNCTION promomed_block_federated_trust_audit_mutation();
