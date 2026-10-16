-- Organization-scoped partner appointment authority.
CREATE TABLE IF NOT EXISTS partner_appointment_slots_v1 (
  id TEXT PRIMARY KEY CHECK(length(id)=32),
  organization_id TEXT NOT NULL REFERENCES institutional_organizations(id),
  starts_at BIGINT NOT NULL CHECK(starts_at>0),
  ends_at BIGINT NOT NULL CHECK(ends_at>starts_at),
  capacity INTEGER NOT NULL CHECK(capacity BETWEEN 1 AND 1000),
  status TEXT NOT NULL CHECK(status IN ('open','closed','cancelled')),
  version INTEGER NOT NULL CHECK(version>=1),
  created_at BIGINT NOT NULL CHECK(created_at>0),
  updated_at BIGINT NOT NULL CHECK(updated_at>=created_at),
  created_by TEXT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 0 CHECK(demo_only IN (0,1))
);
CREATE TABLE IF NOT EXISTS participant_partner_appointments_v1 (
  slot_id TEXT NOT NULL REFERENCES partner_appointment_slots_v1(id),
  email TEXT NOT NULL REFERENCES accounts(email),
  status TEXT NOT NULL CHECK(status IN ('booked','waitlist','cancelled')),
  contact_consent_at BIGINT NOT NULL CHECK(contact_consent_at>0),
  requested_at BIGINT NOT NULL CHECK(requested_at>0),
  updated_at BIGINT NOT NULL CHECK(updated_at>=requested_at),
  PRIMARY KEY(slot_id,email)
);
CREATE INDEX IF NOT EXISTS idx_partner_appointment_slot_org
  ON partner_appointment_slots_v1(organization_id,status,starts_at,id);
CREATE INDEX IF NOT EXISTS idx_partner_appointment_queue
  ON participant_partner_appointments_v1(slot_id,status,requested_at,email);
CREATE INDEX IF NOT EXISTS idx_partner_appointment_owner
  ON participant_partner_appointments_v1(email,status,requested_at,slot_id);

CREATE TRIGGER IF NOT EXISTS partner_appointment_slot_parent_insert
BEFORE INSERT ON partner_appointment_slots_v1
BEGIN
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM institutional_organizations
    WHERE id=NEW.organization_id AND demo_only=NEW.demo_only
  ) THEN RAISE(ABORT,'partner_appointment_org_missing') END;
END;
CREATE TRIGGER IF NOT EXISTS partner_appointment_slot_parent_update
BEFORE UPDATE OF organization_id,demo_only ON partner_appointment_slots_v1
BEGIN
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM institutional_organizations
    WHERE id=NEW.organization_id AND demo_only=NEW.demo_only
  ) THEN RAISE(ABORT,'partner_appointment_org_missing') END;
END;
CREATE TRIGGER IF NOT EXISTS partner_appointment_booking_parent_insert
BEFORE INSERT ON participant_partner_appointments_v1
BEGIN
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM partner_appointment_slots_v1 WHERE id=NEW.slot_id
  ) THEN RAISE(ABORT,'partner_appointment_slot_missing') END;
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM accounts
    WHERE email=NEW.email AND role='participant' AND status='active'
  ) THEN RAISE(ABORT,'partner_appointment_participant_missing') END;
END;
CREATE TRIGGER IF NOT EXISTS partner_appointment_booking_parent_update
BEFORE UPDATE OF slot_id,email ON participant_partner_appointments_v1
BEGIN
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM partner_appointment_slots_v1 WHERE id=NEW.slot_id
  ) THEN RAISE(ABORT,'partner_appointment_slot_missing') END;
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM accounts
    WHERE email=NEW.email AND role='participant' AND status='active'
  ) THEN RAISE(ABORT,'partner_appointment_participant_missing') END;
END;
