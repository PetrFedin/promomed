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
  created_at BIGINT NOT NULL CHECK(created_at>0),
  updated_at BIGINT NOT NULL CHECK(updated_at>=created_at)
);
CREATE INDEX IF NOT EXISTS partner_appointment_slots_v1_org
ON partner_appointment_slots_v1(organization_id,status,start,id);
CREATE INDEX IF NOT EXISTS partner_appointment_slots_v1_item
ON partner_appointment_slots_v1(item_id,status,start,id);

CREATE TABLE IF NOT EXISTS partner_appointment_bookings_v1 (
  slot_id TEXT NOT NULL REFERENCES partner_appointment_slots_v1(id) ON DELETE CASCADE,
  email TEXT NOT NULL REFERENCES accounts(email) ON DELETE CASCADE,
  status TEXT NOT NULL CHECK(status IN ('confirmed','waitlist','cancelled')),
  requested_at BIGINT NOT NULL CHECK(requested_at>0),
  updated_at BIGINT NOT NULL CHECK(updated_at>=requested_at),
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
  created_at BIGINT NOT NULL CHECK(created_at>0),
  PRIMARY KEY(actor_email,request_id)
);

CREATE OR REPLACE FUNCTION promomed_partner_appointment_scope_immutable()
RETURNS trigger AS $$
BEGIN
  IF NEW.organization_id <> OLD.organization_id
     OR NEW.item_id <> OLD.item_id
     OR NEW.demo_only <> OLD.demo_only THEN
    RAISE EXCEPTION 'immutable_partner_appointment_scope';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS partner_appointment_slot_scope_immutable ON partner_appointment_slots_v1;
CREATE TRIGGER partner_appointment_slot_scope_immutable
BEFORE UPDATE OF organization_id,item_id,demo_only ON partner_appointment_slots_v1
FOR EACH ROW EXECUTE FUNCTION promomed_partner_appointment_scope_immutable();
