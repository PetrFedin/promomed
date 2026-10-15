-- One-time participant onboarding invitation authority. Tokens are stored only as SHA-256.
CREATE TABLE IF NOT EXISTS participant_invites (
    id TEXT PRIMARY KEY CHECK (length(id)=32),
    token_hash TEXT NOT NULL UNIQUE CHECK (length(token_hash)=64),
    email TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','accepted','revoked')),
    created_by TEXT NOT NULL,
    created_at BIGINT NOT NULL CHECK (created_at>0),
    expires_at BIGINT NOT NULL CHECK (expires_at>created_at),
    consumed_at BIGINT,
    CHECK (
      (status='pending' AND consumed_at IS NULL)
      OR (status='accepted' AND consumed_at IS NOT NULL AND consumed_at>=created_at)
      OR (status='revoked' AND consumed_at IS NOT NULL AND consumed_at>=created_at)
    )
);
CREATE UNIQUE INDEX IF NOT EXISTS participant_invites_one_pending_email
ON participant_invites(email) WHERE status='pending';
CREATE INDEX IF NOT EXISTS participant_invites_expiry
ON participant_invites(status,expires_at);
