CREATE TABLE IF NOT EXISTS webauthn_users(
 email TEXT PRIMARY KEY,
 user_handle BYTEA NOT NULL UNIQUE,
 created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS webauthn_credentials(
 id TEXT PRIMARY KEY,
 email TEXT NOT NULL,
 credential_id BYTEA NOT NULL UNIQUE,
 public_key BYTEA NOT NULL,
 sign_count BIGINT NOT NULL DEFAULT 0,
 transports TEXT,
 device_name TEXT,
 created_at BIGINT NOT NULL,
 last_used_at BIGINT
);
CREATE INDEX IF NOT EXISTS idx_webauthn_credentials_email ON webauthn_credentials(email);
CREATE TABLE IF NOT EXISTS auth_challenges(
 id TEXT PRIMARY KEY,
 email TEXT NOT NULL,
 purpose TEXT NOT NULL,
 challenge BYTEA NOT NULL,
 created_at BIGINT NOT NULL,
 expires_at BIGINT NOT NULL,
 used_at BIGINT
);
CREATE INDEX IF NOT EXISTS idx_auth_challenges_email_purpose ON auth_challenges(email,purpose,created_at);
CREATE TABLE IF NOT EXISTS step_up_sessions(
 token_hash TEXT PRIMARY KEY,
 email TEXT NOT NULL,
 method TEXT NOT NULL,
 created_at BIGINT NOT NULL,
 expires_at BIGINT NOT NULL,
 revoked_at BIGINT
);
CREATE INDEX IF NOT EXISTS idx_step_up_sessions_email_expiry ON step_up_sessions(email,expires_at);
CREATE TABLE IF NOT EXISTS security_events(
 id TEXT PRIMARY KEY,
 email TEXT,
 kind TEXT NOT NULL,
 details_json TEXT NOT NULL,
 ts BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_status_events(
 id TEXT PRIMARY KEY,
 source_id TEXT NOT NULL,
 from_status TEXT,
 to_status TEXT NOT NULL,
 reason TEXT,
 actor TEXT NOT NULL,
 ts BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_status_source_ts ON evidence_status_events(source_id,ts);
