-- Institution partner binding decisions. Draft governance candidate only.
-- Do not modify previously applied migrations; this revision is append-only.
CREATE TABLE IF NOT EXISTS institutional_partner_binding_revisions_v1 (
  organization_id TEXT PRIMARY KEY REFERENCES institutional_organizations(id),
  version INTEGER NOT NULL CHECK(version>=1),
  updated_at INTEGER NOT NULL CHECK(updated_at>0),
  updated_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS institutional_partner_binding_requests_v1 (
  id TEXT PRIMARY KEY CHECK(length(id)=32),
  organization_id TEXT NOT NULL REFERENCES institutional_organizations(id),
  expected_partner_id TEXT,
  new_partner_id TEXT,
  expected_version INTEGER NOT NULL CHECK(expected_version>=0),
  reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 12 AND 500),
  evidence_ref TEXT NOT NULL CHECK(length(trim(evidence_ref)) BETWEEN 8 AND 200),
  requested_by TEXT NOT NULL,
  requested_at INTEGER NOT NULL CHECK(requested_at>0),
  expires_at INTEGER NOT NULL CHECK(expires_at>requested_at),
  status TEXT NOT NULL CHECK(status IN ('pending','applied','rejected')),
  decision_id TEXT UNIQUE,
  reviewed_by TEXT,
  reviewed_at INTEGER,
  review_reason TEXT,
  demo_only INTEGER NOT NULL CHECK(demo_only IN (0,1)),
  CHECK(
    (expected_partner_id IS NULL AND new_partner_id IS NOT NULL)
    OR (expected_partner_id IS NOT NULL AND new_partner_id IS NULL)
  ),
  CHECK (
    (status='pending' AND reviewed_by IS NULL AND reviewed_at IS NULL AND decision_id IS NULL)
    OR (status IN ('applied','rejected') AND reviewed_by IS NOT NULL
        AND reviewed_at IS NOT NULL AND decision_id IS NOT NULL)
  )
);
CREATE INDEX IF NOT EXISTS idx_institution_partner_binding_requests
  ON institutional_partner_binding_requests_v1(organization_id,status,requested_at,id);

CREATE TABLE IF NOT EXISTS institutional_partner_binding_events_v1 (
  id TEXT PRIMARY KEY CHECK(length(id)=32),
  request_id TEXT NOT NULL REFERENCES institutional_partner_binding_requests_v1(id),
  organization_id TEXT NOT NULL REFERENCES institutional_organizations(id),
  event_no INTEGER NOT NULL CHECK(event_no>=1),
  action TEXT NOT NULL CHECK(action IN ('proposed','applied','rejected')),
  actor TEXT NOT NULL,
  recorded_at INTEGER NOT NULL CHECK(recorded_at>0),
  version_before INTEGER NOT NULL CHECK(version_before>=0),
  version_after INTEGER NOT NULL CHECK(version_after>=version_before),
  receipt_sha256 TEXT NOT NULL CHECK(length(receipt_sha256)=64),
  previous_receipt_sha256 TEXT CHECK(previous_receipt_sha256 IS NULL OR length(previous_receipt_sha256)=64),
  UNIQUE(request_id,action),
  UNIQUE(organization_id,event_no)
);
CREATE INDEX IF NOT EXISTS idx_institution_partner_binding_events
  ON institutional_partner_binding_events_v1(organization_id,recorded_at,id);

-- Do not rewrite prior recorded decisions. External immutability is NOT claimed.
CREATE TRIGGER IF NOT EXISTS institutional_binding_event_immutable_update
BEFORE UPDATE ON institutional_partner_binding_events_v1
BEGIN SELECT RAISE(ABORT,'binding_decision_history_append_only'); END;
