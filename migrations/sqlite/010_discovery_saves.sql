CREATE TABLE IF NOT EXISTS discovery_saves(
  email TEXT NOT NULL,
  target_kind TEXT NOT NULL,
  target_ref TEXT NOT NULL,
  title TEXT NOT NULL,
  topic TEXT NOT NULL DEFAULT '',
  created_at BIGINT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY(email,target_kind,target_ref)
);

CREATE INDEX IF NOT EXISTS idx_discovery_saves_email_created
ON discovery_saves(email,created_at);
