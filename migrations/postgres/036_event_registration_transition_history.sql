-- REG-03 PostgreSQL 17 source-observed registration transitions.
-- No retrospective event is invented; rows predating this migration have no log.
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
CREATE OR REPLACE FUNCTION promomed_event_registration_transition_record()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE next_no INTEGER;
BEGIN
 IF TG_OP='UPDATE' AND NEW.status IS NOT DISTINCT FROM OLD.status THEN
   RETURN NEW;
 END IF;
 SELECT COALESCE(MAX(transition_no),0)+1 INTO next_no
 FROM event_registration_transitions_v1
 WHERE event_id=NEW.event_id AND email=NEW.email;
 INSERT INTO event_registration_transitions_v1
   (event_id,email,transition_no,previous_status,next_status,observed_at,source)
 VALUES
   (NEW.event_id,NEW.email,next_no,
    CASE WHEN TG_OP='INSERT' THEN NULL ELSE OLD.status END,
    NEW.status,EXTRACT(EPOCH FROM clock_timestamp())::BIGINT,'db_trigger');
 RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS event_registration_transition_insert ON participant_event_registrations_v1;
CREATE TRIGGER event_registration_transition_insert
AFTER INSERT ON participant_event_registrations_v1
FOR EACH ROW EXECUTE FUNCTION promomed_event_registration_transition_record();
DROP TRIGGER IF EXISTS event_registration_transition_status_update ON participant_event_registrations_v1;
CREATE TRIGGER event_registration_transition_status_update
AFTER UPDATE OF status ON participant_event_registrations_v1
FOR EACH ROW EXECUTE FUNCTION promomed_event_registration_transition_record();
CREATE OR REPLACE FUNCTION promomed_event_registration_transition_no_update()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'registration_history_append_only';
END;
$$;
DROP TRIGGER IF EXISTS event_registration_transition_no_update ON event_registration_transitions_v1;
CREATE TRIGGER event_registration_transition_no_update
BEFORE UPDATE ON event_registration_transitions_v1
FOR EACH ROW EXECUTE FUNCTION promomed_event_registration_transition_no_update();
-- Parent deletion legally erases owner records via ON DELETE CASCADE.
-- This is an append-only operational history, not a tamper-proof external ledger.
