CREATE TABLE IF NOT EXISTS evidence_issuer_keys(
  issuer_id TEXT NOT NULL,
  key_id TEXT NOT NULL,
  alg TEXT NOT NULL,
  public_key_b64 TEXT NOT NULL,
  status TEXT NOT NULL,
  valid_from INTEGER NOT NULL,
  valid_until INTEGER,
  rotated_from_key_id TEXT,
  created_at INTEGER NOT NULL,
  created_by TEXT NOT NULL,
  retired_at INTEGER,
  revoked_at INTEGER,
  revoked_reason TEXT,
  PRIMARY KEY(issuer_id,key_id)
);

CREATE TABLE IF NOT EXISTS evidence_checkpoint_issuance(
  checkpoint_sha256 TEXT PRIMARY KEY,
  issuer_id TEXT NOT NULL,
  key_id TEXT NOT NULL,
  artifact_kind TEXT NOT NULL,
  artifact_ref TEXT NOT NULL,
  issued_at INTEGER NOT NULL,
  seal_sha256 TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  signature_b64 TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_evidence_issuer_keys_status
  ON evidence_issuer_keys(issuer_id,status,valid_from);

CREATE INDEX IF NOT EXISTS idx_evidence_checkpoint_issuance_issuer
  ON evidence_checkpoint_issuance(issuer_id,key_id,issued_at);
