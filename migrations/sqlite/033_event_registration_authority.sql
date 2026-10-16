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

-- SQLite runtime does not globally enable PRAGMA foreign_keys, so the authority
-- enforces both parent references explicitly as well as with declared FKs.
CREATE TRIGGER IF NOT EXISTS participant_event_registration_parent_insert
BEFORE INSERT ON participant_event_registrations_v1
BEGIN
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM event_editions_v1 WHERE id=NEW.event_id
  ) THEN RAISE(ABORT,'event_registration_event_missing') END;
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM accounts WHERE email=NEW.email
  ) THEN RAISE(ABORT,'event_registration_account_missing') END;
END;
CREATE TRIGGER IF NOT EXISTS participant_event_registration_parent_update
BEFORE UPDATE OF event_id,email ON participant_event_registrations_v1
BEGIN
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM event_editions_v1 WHERE id=NEW.event_id
  ) THEN RAISE(ABORT,'event_registration_event_missing') END;
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM accounts WHERE email=NEW.email
  ) THEN RAISE(ABORT,'event_registration_account_missing') END;
END;

CREATE TRIGGER IF NOT EXISTS participant_event_registration_account_delete
AFTER DELETE ON accounts
BEGIN
  DELETE FROM participant_event_registrations_v1 WHERE email=OLD.email;
END;
CREATE TRIGGER IF NOT EXISTS participant_event_registration_event_delete
AFTER DELETE ON event_editions_v1
BEGIN
  DELETE FROM participant_event_registrations_v1 WHERE event_id=OLD.id;
END;
