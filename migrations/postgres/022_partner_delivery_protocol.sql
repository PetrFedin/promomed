CREATE TABLE IF NOT EXISTS syndication_delivery_endpoints(
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  endpoint_url TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('pending_verification','active','suspended','revoked')),
  secret_version BIGINT NOT NULL DEFAULT 1,
  secret_hash TEXT NOT NULL,
  verification_challenge TEXT NOT NULL,
  verified_at BIGINT,
  verified_by TEXT,
  last_rotated_at BIGINT,
  last_rotated_by TEXT,
  created_at BIGINT NOT NULL,
  created_by TEXT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0,
  UNIQUE(organization_id,endpoint_url)
);

CREATE TABLE IF NOT EXISTS syndication_partner_delivery_cursors(
  organization_id TEXT PRIMARY KEY,
  next_sequence BIGINT NOT NULL DEFAULT 1,
  last_acked_sequence BIGINT NOT NULL DEFAULT 0,
  updated_at BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS syndication_delivery_events(
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  endpoint_id TEXT NOT NULL,
  sequence_no BIGINT NOT NULL,
  event_type TEXT NOT NULL CHECK(event_type IN ('package_delivery','package_update','package_withdrawal','contribution_admission','qualification_status')),
  subject_kind TEXT NOT NULL,
  subject_ref TEXT NOT NULL,
  obligation_id TEXT,
  payload_json TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  created_at BIGINT NOT NULL,
  created_by TEXT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0,
  UNIQUE(organization_id,sequence_no),
  UNIQUE(organization_id,event_type,subject_kind,subject_ref,payload_sha256)
);

CREATE TABLE IF NOT EXISTS syndication_delivery_event_state(
  event_id TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK(status IN ('queued','delivered','acknowledged','dead','cancelled')),
  next_attempt_at BIGINT NOT NULL,
  delivered_at BIGINT,
  acknowledged_at BIGINT,
  dead_at BIGINT,
  terminal_reason TEXT NOT NULL DEFAULT '',
  updated_at BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS syndication_delivery_attempts(
  id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL,
  endpoint_id TEXT NOT NULL,
  attempt_no BIGINT NOT NULL,
  secret_version BIGINT NOT NULL,
  request_timestamp BIGINT NOT NULL,
  request_signature TEXT NOT NULL,
  sent_at BIGINT NOT NULL,
  completed_at BIGINT NOT NULL,
  transport_status TEXT NOT NULL CHECK(transport_status IN ('success','retryable_failure','terminal_failure')),
  http_status BIGINT,
  response_sha256 TEXT NOT NULL DEFAULT '',
  error_class TEXT NOT NULL DEFAULT '',
  next_retry_at BIGINT,
  demo_only INTEGER NOT NULL DEFAULT 0,
  UNIQUE(event_id,attempt_no)
);

CREATE TABLE IF NOT EXISTS syndication_delivery_acknowledgements(
  id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL UNIQUE,
  endpoint_id TEXT NOT NULL,
  organization_id TEXT NOT NULL,
  sequence_no BIGINT NOT NULL,
  ack_payload_json TEXT NOT NULL,
  ack_payload_sha256 TEXT NOT NULL,
  ack_timestamp BIGINT NOT NULL,
  ack_signature TEXT NOT NULL,
  received_at BIGINT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS syndication_delivery_observations(
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  event_id TEXT,
  observation_type TEXT NOT NULL CHECK(observation_type IN (
    'delivery_success','delivery_retryable_failure','delivery_terminal_failure',
    'ack_success','ack_late','ack_missing','sla_breach','dead_event'
  )),
  severity TEXT NOT NULL CHECK(severity IN ('info','warning','critical')),
  details_json TEXT NOT NULL,
  observed_at BIGINT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_syndication_delivery_endpoint_org
  ON syndication_delivery_endpoints(organization_id,status);

CREATE INDEX IF NOT EXISTS idx_syndication_delivery_state_due
  ON syndication_delivery_event_state(status,next_attempt_at);

CREATE INDEX IF NOT EXISTS idx_syndication_delivery_attempt_event
  ON syndication_delivery_attempts(event_id,attempt_no);

CREATE INDEX IF NOT EXISTS idx_syndication_delivery_observation_org
  ON syndication_delivery_observations(organization_id,observed_at);

CREATE OR REPLACE FUNCTION promomed_block_syndication_delivery_audit_mutation()
RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'immutable_syndication_delivery_audit';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS syndication_delivery_events_no_update ON syndication_delivery_events;
CREATE TRIGGER syndication_delivery_events_no_update
BEFORE UPDATE OR DELETE ON syndication_delivery_events
FOR EACH ROW EXECUTE FUNCTION promomed_block_syndication_delivery_audit_mutation();

DROP TRIGGER IF EXISTS syndication_delivery_attempts_no_update ON syndication_delivery_attempts;
CREATE TRIGGER syndication_delivery_attempts_no_update
BEFORE UPDATE OR DELETE ON syndication_delivery_attempts
FOR EACH ROW EXECUTE FUNCTION promomed_block_syndication_delivery_audit_mutation();

DROP TRIGGER IF EXISTS syndication_delivery_ack_no_update ON syndication_delivery_acknowledgements;
CREATE TRIGGER syndication_delivery_ack_no_update
BEFORE UPDATE OR DELETE ON syndication_delivery_acknowledgements
FOR EACH ROW EXECUTE FUNCTION promomed_block_syndication_delivery_audit_mutation();

DROP TRIGGER IF EXISTS syndication_delivery_observations_no_update ON syndication_delivery_observations;
CREATE TRIGGER syndication_delivery_observations_no_update
BEFORE UPDATE OR DELETE ON syndication_delivery_observations
FOR EACH ROW EXECUTE FUNCTION promomed_block_syndication_delivery_audit_mutation();
