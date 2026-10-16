-- Partner appointment authority v1: organization-scoped slot + participant-owned booking.
CREATE TABLE IF NOT EXISTS partner_appointment_slots_v1 (
  id TEXT PRIMARY KEY CHECK(length(id)=24),
  organization_id TEXT NOT NULL REFERENCES institutional_organizations(id),
  item_id TEXT NOT NULL REFERENCES program_items(id),
  start TEXT NOT NULL,
  "end" TEXT NOT NULL,
  capacity INTEGER NOT NULL CHECK(capacity>0),
  status TEXT NOT NULL CHECK(status IN ('open','closed','cancelled')),
  version INTEGER NOT NULL DEFAULT 1 CHECK(version>0),
  demo_only INTEGER NOT NULL CHECK(demo_only IN (0,1)),
  created_by TEXT NOT NULL,
  created_at INTEGER NOT NULL CHECK(created_at>0),
  updated_at INTEGER NOT NULL CHECK(updated_at>=created_at)
);
CREATE INDEX IF NOT EXISTS partner_appointment_slots_v1_org
ON partner_appointment_slots_v1(organization_id,status,start,id);
CREATE INDEX IF NOT EXISTS partner_appointment_slots_v1_item
ON partner_appointment_slots_v1(item_id,status,start,id);

CREATE TABLE IF NOT EXISTS partner_appointment_bookings_v1 (
  slot_id TEXT NOT NULL REFERENCES partner_appointment_slots_v1(id),
  email TEXT NOT NULL REFERENCES accounts(email),
  status TEXT NOT NULL CHECK(status IN ('confirmed','waitlist','cancelled')),
  requested_at INTEGER NOT NULL CHECK(requested_at>0),
  updated_at INTEGER NOT NULL CHECK(updated_at>=requested_at),
  PRIMARY KEY(slot_id,email)
);
CREATE INDEX IF NOT EXISTS partner_appointment_bookings_v1_queue
ON partner_appointment_bookings_v1(slot_id,status,requested_at,email);

CREATE TABLE IF NOT EXISTS partner_appointment_operations_v1 (
  actor_email TEXT NOT NULL,
  request_id TEXT NOT NULL CHECK(length(request_id)=32),
  route TEXT NOT NULL,
  request_sha256 TEXT NOT NULL CHECK(length(request_sha256)=64),
  result_json TEXT NOT NULL,
  created_at INTEGER NOT NULL CHECK(created_at>0),
  PRIMARY KEY(actor_email,request_id)
);

CREATE TRIGGER IF NOT EXISTS partner_appointment_slot_parent_insert
BEFORE INSERT ON partner_appointment_slots_v1
BEGIN
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM institutional_organizations WHERE id=NEW.organization_id
  ) THEN RAISE(ABORT,'partner_appointment_org_missing') END;
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM program_items WHERE id=NEW.item_id
  ) THEN RAISE(ABORT,'partner_appointment_item_missing') END;
END;

CREATE TRIGGER IF NOT EXISTS partner_appointment_slot_scope_immutable
BEFORE UPDATE OF organization_id,item_id,demo_only ON partner_appointment_slots_v1
BEGIN
  SELECT RAISE(ABORT,'immutable_partner_appointment_scope');
END;

CREATE TRIGGER IF NOT EXISTS partner_appointment_booking_parent_insert
BEFORE INSERT ON partner_appointment_bookings_v1
BEGIN
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM partner_appointment_slots_v1 WHERE id=NEW.slot_id
  ) THEN RAISE(ABORT,'partner_appointment_slot_missing') END;
  SELECT CASE WHEN NOT EXISTS(
    SELECT 1 FROM accounts WHERE email=NEW.email
  ) THEN RAISE(ABORT,'partner_appointment_account_missing') END;
END;

CREATE TRIGGER IF NOT EXISTS partner_appointment_account_delete
AFTER DELETE ON accounts
BEGIN
  DELETE FROM partner_appointment_bookings_v1 WHERE email=OLD.email;
END;

CREATE TRIGGER IF NOT EXISTS partner_appointment_slot_delete
AFTER DELETE ON partner_appointment_slots_v1
BEGIN
  DELETE FROM partner_appointment_bookings_v1 WHERE slot_id=OLD.id;
END;
