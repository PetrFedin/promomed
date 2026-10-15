-- Participant self-registration requests. No account exists until verification succeeds.
CREATE TABLE IF NOT EXISTS participant_registration_requests (
    id TEXT PRIMARY KEY CHECK (length(id)=32),
    email TEXT NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    verification_hash TEXT NOT NULL CHECK (length(verification_hash)=64),
    status TEXT NOT NULL CHECK (status IN ('pending','verified','expired','blocked')),
    created_at BIGINT NOT NULL CHECK (created_at>0),
    expires_at BIGINT NOT NULL CHECK (expires_at>created_at),
    verified_at BIGINT,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts>=0),
    demo_only INTEGER NOT NULL DEFAULT 0 CHECK (demo_only IN (0,1)),
    CHECK (
      (status='verified' AND verified_at IS NOT NULL)
      OR (status<>'verified' AND verified_at IS NULL)
    )
);
CREATE UNIQUE INDEX IF NOT EXISTS participant_registration_pending_email
ON participant_registration_requests(email)
WHERE status='pending';
CREATE INDEX IF NOT EXISTS participant_registration_expiry
ON participant_registration_requests(status,expires_at);
