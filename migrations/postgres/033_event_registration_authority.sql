-- Capacity-aware participant event registration authority.
CREATE TABLE IF NOT EXISTS event_editions_v1 (
  id TEXT PRIMARY KEY CHECK (length(id) BETWEEN 1 AND 64),
  title TEXT NOT NULL CHECK (length(trim(title))>0),
  starts_at BIGINT NOT NULL CHECK (starts_at>0),
  registration_status TEXT NOT NULL CHECK (registration_status IN ('open','closed','waitlist_only','cancelled')),
  capacity INTEGER NOT NULL CHECK (capacity>=0),
  demo_only INTEGER NOT NULL DEFAULT 0 CHECK (demo_only IN (0,1)),
  created_at BIGINT NOT NULL CHECK (created_at>0),
  updated_at BIGINT NOT NULL CHECK (updated_at>=created_at)
);
CREATE TABLE IF NOT EXISTS participant_event_registrations_v1 (
  event_id TEXT NOT NULL REFERENCES event_editions_v1(id) ON DELETE CASCADE,
  email TEXT NOT NULL REFERENCES accounts(email) ON DELETE CASCADE,
  status TEXT NOT NULL CHECK (status IN ('confirmed','waitlist','cancelled')),
  requested_at BIGINT NOT NULL CHECK (requested_at>0),
  updated_at BIGINT NOT NULL CHECK (updated_at>=requested_at),
  source TEXT NOT NULL DEFAULT 'participant' CHECK (source='participant'),
  PRIMARY KEY(event_id,email)
);
CREATE INDEX IF NOT EXISTS participant_event_registration_queue
ON participant_event_registrations_v1(event_id,status,requested_at,email);
