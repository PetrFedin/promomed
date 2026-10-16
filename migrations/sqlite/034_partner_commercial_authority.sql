-- Organization-scoped partner commercial authority.
CREATE TABLE IF NOT EXISTS partner_commercial_placements_v1 (
  organization_id TEXT PRIMARY KEY REFERENCES institutional_organizations(id),
  status TEXT NOT NULL CHECK(status IN ('planned','contracted','active','ended')),
  version INTEGER NOT NULL CHECK(version>=1),
  updated_at BIGINT NOT NULL CHECK(updated_at>0),
  updated_by TEXT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0 CHECK(demo_only IN (0,1))
);
CREATE TABLE IF NOT EXISTS participant_partner_leads_v1 (
  id TEXT PRIMARY KEY CHECK(length(id)=32),
  organization_id TEXT NOT NULL REFERENCES institutional_organizations(id),
  email TEXT NOT NULL REFERENCES accounts(email),
  request_key TEXT NOT NULL CHECK(length(request_key)=32),
  kind TEXT NOT NULL CHECK(length(trim(kind)) BETWEEN 1 AND 80),
  status TEXT NOT NULL CHECK(status IN ('submitted','withdrawn')),
  consent_at BIGINT NOT NULL CHECK(consent_at>0),
  created_at BIGINT NOT NULL CHECK(created_at>0),
  withdrawn_at BIGINT,
  demo_only INTEGER NOT NULL DEFAULT 0 CHECK(demo_only IN (0,1)),
  UNIQUE(email,request_key),
  CHECK(
    (status='submitted' AND withdrawn_at IS NULL)
    OR (status='withdrawn' AND withdrawn_at IS NOT NULL AND withdrawn_at>=created_at)
  )
);
CREATE INDEX IF NOT EXISTS idx_partner_commercial_lead_org
  ON participant_partner_leads_v1(organization_id,status,created_at,id);
CREATE INDEX IF NOT EXISTS idx_partner_commercial_lead_owner
  ON participant_partner_leads_v1(email,status,created_at,id);

-- SQLite runtime does not globally enable PRAGMA foreign_keys.
CREATE TRIGGER IF NOT EXISTS partner_commercial_placement_parent_insert
BEFORE INSERT ON partner_commercial_placements_v1
BEGIN
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM institutional_organizations
    WHERE id=NEW.organization_id AND demo_only=NEW.demo_only
  ) THEN RAISE(ABORT,'partner_commercial_org_missing') END;
END;
CREATE TRIGGER IF NOT EXISTS partner_commercial_placement_parent_update
BEFORE UPDATE OF organization_id,demo_only ON partner_commercial_placements_v1
BEGIN
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM institutional_organizations
    WHERE id=NEW.organization_id AND demo_only=NEW.demo_only
  ) THEN RAISE(ABORT,'partner_commercial_org_missing') END;
END;
CREATE TRIGGER IF NOT EXISTS partner_commercial_lead_parent_insert
BEFORE INSERT ON participant_partner_leads_v1
BEGIN
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM institutional_organizations
    WHERE id=NEW.organization_id AND demo_only=NEW.demo_only
  ) THEN RAISE(ABORT,'partner_commercial_org_missing') END;
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM accounts
    WHERE email=NEW.email AND role='participant' AND status='active'
  ) THEN RAISE(ABORT,'partner_commercial_participant_missing') END;
END;
CREATE TRIGGER IF NOT EXISTS partner_commercial_lead_parent_update
BEFORE UPDATE OF organization_id,email,demo_only ON participant_partner_leads_v1
BEGIN
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM institutional_organizations
    WHERE id=NEW.organization_id AND demo_only=NEW.demo_only
  ) THEN RAISE(ABORT,'partner_commercial_org_missing') END;
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM accounts
    WHERE email=NEW.email AND role='participant' AND status='active'
  ) THEN RAISE(ABORT,'partner_commercial_participant_missing') END;
END;
