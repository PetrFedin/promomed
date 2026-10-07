CREATE TABLE IF NOT EXISTS evidence_checkpoint_revocations(
  checkpoint_sha256 TEXT PRIMARY KEY,
  artifact_kind TEXT NOT NULL,
  artifact_ref TEXT NOT NULL,
  reason TEXT NOT NULL,
  revoked_by TEXT NOT NULL,
  revoked_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_checkpoint_revocations_artifact
  ON evidence_checkpoint_revocations(artifact_kind,artifact_ref,revoked_at);
