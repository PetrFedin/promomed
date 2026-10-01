CREATE TABLE IF NOT EXISTS accounts(
 email TEXT PRIMARY KEY,
 password_hash TEXT NOT NULL,
 role TEXT NOT NULL,
 name TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'active',
 created_at BIGINT NOT NULL,
 updated_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions(
 token_hash TEXT PRIMARY KEY,
 email TEXT NOT NULL REFERENCES accounts(email),
 role TEXT NOT NULL,
 name TEXT NOT NULL,
 created_at BIGINT NOT NULL,
 expires_at BIGINT NOT NULL,
 revoked_at BIGINT
);
CREATE INDEX IF NOT EXISTS idx_sessions_email ON sessions(email);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
CREATE TABLE IF NOT EXISTS consent_records(
 id BIGSERIAL PRIMARY KEY,
 email TEXT NOT NULL,
 purpose TEXT NOT NULL,
 consent_version TEXT NOT NULL,
 granted INTEGER NOT NULL,
 source TEXT NOT NULL,
 business_ref TEXT,
 ts BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_consent_email_purpose ON consent_records(email,purpose,ts);
