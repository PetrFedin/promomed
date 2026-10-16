-- REG-03. Database-observed event-registration transitions.
-- No pre-migration backfill is fabricated. Older current rows remain unproven.
-- History is owner scoped by (event_id,email); records are removed on owner
-- registration deletion for data minimization, rather than retained forever.
CREATE TABLE IF NOT EXISTS event_registration_transitions_v1 (
  event_id TEXT NOT NULL,
  email TEXT NOT NULL,
  transition_no INTEGER NOT NULL CHECK(transition_no>=1),
  previous_status TEXT CHECK(previous_status IS NULL OR previous_status IN ('confirmed','waitlist','cancelled')),
  next_status TEXT NOT NULL CHECK(next_status IN ('confirmed','waitlist','cancelled')),
  observed_at BIGINT NOT NULL CHECK(observed_at>0),
  source TEXT NOT NULL DEFAULT 'db_trigger' CHECK(source='db_trigger'),
  PRIMARY KEY(event_id,email,transition_no),
  FOREIGN KEY(event_id,email) REFERENCES participant_event_registrations_v1(event_id,email) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_event_registration_transitions_owner
  ON event_registration_transitions_v1(email,event_id,transition_no);

-- Both the synchronous participant command and queue promotion use this source.
CREATE TRIGGER IF NOT EXISTS event_registration_transition_insert
AFTER INSERT ON participant_event_registrations_v1
BEGIN
  INSERT INTO event_registration_transitions_v1
  (event_id,email,transition_no,previous_status,next_status,observed_at,source)
  VALUES (
    NEW.event_id,NEW.email,
    COALESCE((SELECT MAX(transition_no) FROM event_registration_transitions_v1
              WHERE event_id=NEW.event_id AND email=NEW.email),0)+1,
    NULL,NEW.status,CAST(strftime('%s','now') AS INTEGER),'db_trigger'
  );
END;
CREATE TRIGGER IF NOT EXISTS event_registration_transition_status_update
AFTER UPDATE OF status ON participant_event_registrations_v1
WHEN OLD.status<>NEW.status
BEGIN
  INSERT INTO event_registration_transitions_v1
  (event_id,email,transition_no,previous_status,next_status,observed_at,source)
  VALUES (
    NEW.event_id,NEW.email,
    COALESCE((SELECT MAX(transition_no) FROM event_registration_transitions_v1
              WHERE event_id=NEW.event_id AND email=NEW.email),0)+1,
    OLD.status,NEW.status,CAST(strftime('%s','now') AS INTEGER),'db_trigger'
  );
END;

-- Normal updates to historical events are forbidden. Explicit parent erasure
-- remains possible; these data are NOT an indestructible or signed ledger.
CREATE TRIGGER IF NOT EXISTS event_registration_transition_no_update
BEFORE UPDATE ON event_registration_transitions_v1
BEGIN SELECT RAISE(ABORT,'registration_history_append_only'); END;
-- SQLite deployments do not universally enable foreign_keys: explicit erasure.
CREATE TRIGGER IF NOT EXISTS event_registration_transition_owner_erasure
AFTER DELETE ON participant_event_registrations_v1
BEGIN
  DELETE FROM event_registration_transitions_v1
  WHERE event_id=OLD.event_id AND email=OLD.email;
END;
CREATE TRIGGER IF NOT EXISTS event_registration_transition_account_erasure
AFTER DELETE ON accounts
BEGIN
  DELETE FROM event_registration_transitions_v1 WHERE email=OLD.email;
END;
CREATE TRIGGER IF NOT EXISTS event_registration_transition_event_erasure
AFTER DELETE ON event_editions_v1
BEGIN
  DELETE FROM event_registration_transitions_v1 WHERE event_id=OLD.id;
END;
