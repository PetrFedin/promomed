CREATE TABLE IF NOT EXISTS institutional_memberships(
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  account_email TEXT NOT NULL,
  member_role TEXT NOT NULL CHECK(member_role IN ('contributor','operator','administrator')),
  status TEXT NOT NULL CHECK(status IN ('active','suspended','revoked','expired')),
  effective_at INTEGER NOT NULL,
  expires_at INTEGER,
  verified_by TEXT NOT NULL,
  verification_ref TEXT NOT NULL DEFAULT '',
  demo_only INTEGER NOT NULL DEFAULT 0,
  UNIQUE(organization_id,account_email,member_role)
);

CREATE TABLE IF NOT EXISTS syndication_partner_qualifications(
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('pending','qualified','requalification_due','suspended','revoked','expired')),
  qualification_version TEXT NOT NULL,
  effective_at INTEGER,
  valid_until INTEGER,
  next_requalification_at INTEGER,
  qualified_by TEXT,
  suspended_at INTEGER,
  suspended_by TEXT,
  revoked_at INTEGER,
  revoked_by TEXT,
  reason TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL,
  created_by TEXT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS syndication_conformance_checks(
  id TEXT PRIMARY KEY,
  qualification_id TEXT NOT NULL,
  scope_key TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('pending','passed','failed','waived')),
  evidence_ref TEXT NOT NULL DEFAULT '',
  checked_at INTEGER,
  checked_by TEXT,
  expires_at INTEGER,
  details TEXT NOT NULL DEFAULT '',
  demo_only INTEGER NOT NULL DEFAULT 0,
  UNIQUE(qualification_id,scope_key)
);

CREATE TABLE IF NOT EXISTS syndication_subscriptions(
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  subscription_scope TEXT NOT NULL,
  scope_ref TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('active','paused','revoked','expired')),
  update_sla_seconds INTEGER NOT NULL,
  withdrawal_sla_seconds INTEGER NOT NULL,
  effective_at INTEGER NOT NULL,
  expires_at INTEGER,
  created_at INTEGER NOT NULL,
  created_by TEXT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0,
  UNIQUE(organization_id,subscription_scope,scope_ref)
);

CREATE TABLE IF NOT EXISTS syndication_delivery_obligations(
  id TEXT PRIMARY KEY,
  delivery_id TEXT NOT NULL,
  obligation_type TEXT NOT NULL CHECK(obligation_type IN ('update','withdrawal')),
  due_at INTEGER NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('pending','acknowledged','breached','cancelled')),
  acknowledged_at INTEGER,
  evidence_ref TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0,
  UNIQUE(delivery_id,obligation_type)
);

CREATE TABLE IF NOT EXISTS external_contributions(
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  contribution_type TEXT NOT NULL CHECK(contribution_type IN ('source_recommendation','review_input','disclosure_record','programme_material','correction_notice','institutional_metadata')),
  title TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK(status IN ('submitted','editorial_review','scientific_review','review_ready','changes_requested','rejected','admitted','withdrawn')),
  submitted_by TEXT NOT NULL,
  submitted_at INTEGER NOT NULL,
  admitted_at INTEGER,
  admitted_by TEXT,
  withdrawn_at INTEGER,
  withdrawal_reason TEXT,
  demo_only INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS external_contribution_reviews(
  id TEXT PRIMARY KEY,
  contribution_id TEXT NOT NULL,
  review_role TEXT NOT NULL CHECK(review_role IN ('editorial','scientific')),
  reviewer TEXT NOT NULL,
  decision TEXT NOT NULL CHECK(decision IN ('accept','reject','request_changes')),
  rationale TEXT NOT NULL,
  conflict_state TEXT NOT NULL CHECK(conflict_state IN ('none','potential','material')),
  reviewed_at INTEGER NOT NULL,
  review_digest TEXT NOT NULL UNIQUE,
  demo_only INTEGER NOT NULL DEFAULT 0,
  UNIQUE(contribution_id,review_role)
);

CREATE TABLE IF NOT EXISTS external_contribution_admission_receipts(
  id TEXT PRIMARY KEY,
  contribution_id TEXT NOT NULL UNIQUE,
  receipt_sha256 TEXT NOT NULL UNIQUE,
  envelope_json TEXT NOT NULL,
  admitted_at INTEGER NOT NULL,
  admitted_by TEXT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_institutional_membership_account
  ON institutional_memberships(account_email,status,organization_id);

CREATE INDEX IF NOT EXISTS idx_syndication_qualification_org
  ON syndication_partner_qualifications(organization_id,status,valid_until);

CREATE INDEX IF NOT EXISTS idx_syndication_subscription_org
  ON syndication_subscriptions(organization_id,status,subscription_scope);

CREATE INDEX IF NOT EXISTS idx_syndication_obligation_due
  ON syndication_delivery_obligations(status,due_at);

CREATE INDEX IF NOT EXISTS idx_external_contribution_org
  ON external_contributions(organization_id,status,submitted_at);

CREATE INDEX IF NOT EXISTS idx_external_contribution_review
  ON external_contribution_reviews(contribution_id,review_role);
