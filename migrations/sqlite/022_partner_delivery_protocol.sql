CREATE TABLE IF NOT EXISTS syndication_delivery_endpoints(
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  endpoint_url TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('pending_verification','active','suspended','revoked')),
  secret_version INTEGER NOT NULL DEFAULT 1,
  secret_hash TEXT NOT NULL,
  verification_challenge TEXT NOT NULL,
  verified_at INTEGER,
  verified_by TEXT,
  last_rotated_at INTEGER,
  last_rotated_by TEXT,
  created_at INTEGER NOT NULL,
  created_by TEXT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0,
  UNIQUE(organization_id,endpoint_url)
);

CREATE TABLE IF NOT EXISTS syndication_partner_delivery_cursors(
  organization_id TEXT PRIMARY KEY,
  next_sequence INTEGER NOT NULL DEFAULT 1,
  last_acked_sequence INTEGER NOT NULL DEFAULT 0,
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS syndication_delivery_events(
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  endpoint_id TEXT NOT NULL,
  sequence_no INTEGER NOT NULL,
  event_type TEXT NOT NULL CHECK(event_type IN ('package_delivery','package_update','package_withdrawal','contribution_admission','qualification_status')),
  subject_kind TEXT NOT NULL,
  subject_ref TEXT NOT NULL,
  obligation_id TEXT,
  payload_json TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  created_by TEXT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0,
  UNIQUE(organization_id,sequence_no),
  UNIQUE(organization_id,event_type,subject_kind,subject_ref,payload_sha256)
);

CREATE TABLE IF NOT EXISTS syndication_delivery_event_state(
  event_id TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK(status IN ('queued','delivered','acknowledged','dead','cancelled')),
  next_attempt_at INTEGER NOT NULL,
  delivered_at INTEGER,
  acknowledged_at INTEGER,
  dead_at INTEGER,
  terminal_reason TEXT NOT NULL DEFAULT '',
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS syndication_delivery_attempts(
  id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL,
  endpoint_id TEXT NOT NULL,
  attempt_no INTEGER NOT NULL,
  secret_version INTEGER NOT NULL,
  request_timestamp INTEGER NOT NULL,
  request_signature TEXT NOT NULL,
  sent_at INTEGER NOT NULL,
  completed_at INTEGER NOT NULL,
  transport_status TEXT NOT NULL CHECK(transport_status IN ('success','retryable_failure','terminal_failure')),
  http_status INTEGER,
  response_sha256 TEXT NOT NULL DEFAULT '',
  error_class TEXT NOT NULL DEFAULT '',
  next_retry_at INTEGER,
  demo_only INTEGER NOT NULL DEFAULT 0,
  UNIQUE(event_id,attempt_no)
);

CREATE TABLE IF NOT EXISTS syndication_delivery_acknowledgements(
  id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL UNIQUE,
  endpoint_id TEXT NOT NULL,
  organization_id TEXT NOT NULL,
  sequence_no INTEGER NOT NULL,
  ack_payload_json TEXT NOT NULL,
  ack_payload_sha256 TEXT NOT NULL,
  ack_timestamp INTEGER NOT NULL,
  ack_signature TEXT NOT NULL,
  received_at INTEGER NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS syndication_delivery_observations(
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  event_id TEXT,
  observation_type TEXT NOT NULL CHECK(observation_type IN (
    'delivery_success','delivery_retryable_failure','delivery_terminal_failure',
    'ack_success','ack_late','sla_breach','dead_event'
  )),
  severity TEXT NOT NULL CHECK(severity IN ('info','warning','critical')),
  details_json TEXT NOT NULL,
  observed_at INTEGER NOT NULL,
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

CREATE TRIGGER IF NOT EXISTS syndication_delivery_events_no_update
BEFORE UPDATE ON syndication_delivery_events
BEGIN SELECT RAISE(ABORT,'immutable_syndication_delivery_event'); END;

CREATE TRIGGER IF NOT EXISTS syndication_delivery_events_no_delete
BEFORE DELETE ON syndication_delivery_events
BEGIN SELECT RAISE(ABORT,'immutable_syndication_delivery_event'); END;

CREATE TRIGGER IF NOT EXISTS syndication_delivery_attempts_no_update
BEFORE UPDATE ON syndication_delivery_attempts
BEGIN SELECT RAISE(ABORT,'immutable_syndication_delivery_attempt'); END;

CREATE TRIGGER IF NOT EXISTS syndication_delivery_attempts_no_delete
BEFORE DELETE ON syndication_delivery_attempts
BEGIN SELECT RAISE(ABORT,'immutable_syndication_delivery_attempt'); END;

CREATE TRIGGER IF NOT EXISTS syndication_delivery_ack_no_update
BEFORE UPDATE ON syndication_delivery_acknowledgements
BEGIN SELECT RAISE(ABORT,'immutable_syndication_delivery_ack'); END;

CREATE TRIGGER IF NOT EXISTS syndication_delivery_ack_no_delete
BEFORE DELETE ON syndication_delivery_acknowledgements
BEGIN SELECT RAISE(ABORT,'immutable_syndication_delivery_ack'); END;

CREATE TRIGGER IF NOT EXISTS syndication_delivery_observations_no_update
BEFORE UPDATE ON syndication_delivery_observations
BEGIN SELECT RAISE(ABORT,'immutable_syndication_delivery_observation'); END;

CREATE TRIGGER IF NOT EXISTS syndication_delivery_observations_no_delete
BEFORE DELETE ON syndication_delivery_observations
BEGIN SELECT RAISE(ABORT,'immutable_syndication_delivery_observation'); END;
