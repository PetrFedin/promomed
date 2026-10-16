# PARTNER APPOINTMENT V1 — organization-scoped authority (2026-10-16)

Status: Draft source candidate stacked after self-attendance Draft #115. Not deployed.

## Why a new authority

Legacy `appointment_slots(id,item_id,start,end,capacity,partner_id)` has no institutional organization scope, no verified membership predicate and no concurrency-safe tenant boundary. Legacy `/api/appointment-booking` and `/api/appointment-manage` therefore remain non-demo denied by SEC-11.

This slice introduces separate versioned authority:

- `POST /api/partner-appointment-slot/v1` — partner slot management;
- `POST /api/partner-appointment-booking/v1` — participant booking/cancel.

## Migration 034

`partner_appointment_slots_v1`

- immutable `organization_id`, `item_id` and `demo_only` scope;
- parent `institutional_organizations` + `program_items`;
- start/end window, capacity, status, version and creator;
- organization/item indexes.

`partner_appointment_bookings_v1`

- primary key `(slot_id,email)`;
- `confirmed | waitlist | cancelled`;
- request/update timestamps;
- queue index.

`partner_appointment_operations_v1`

- actor-bound `request_id`;
- route + request digest + deterministic result;
- protects partner slot mutations from replay/idempotency ambiguity.

SQLite adds explicit parent/cleanup triggers because repository runtime does not globally rely on `PRAGMA foreign_keys=ON`. PostgreSQL uses FKs and immutable-scope trigger.

## Partner slot authority

Partner slot create requires:

1. authenticated active `partner` account;
2. verified active operator/administrator membership returned by server-side `partner_org_scope.member`;
3. organization type exactly `strategic_partner`;
4. organization/demo boundary matching runtime;
5. exact current parent event admitted through public-state v1;
6. slot interval fully inside the admitted parent event;
7. capacity 1–1000;
8. 32-hex `request_id`.

Client-provided organization is used only for create and must pass verified membership. All later update/close/cancel operations load organization scope from the stored slot before membership authorization.

PostgreSQL serializes partner mutation idempotency by locking the authenticated partner account before the operation ledger is checked. SQLite uses `BEGIN IMMEDIATE`. Two simultaneous creates with the same request id must yield one slot and one operation row.

Slot scope cannot be reassigned to another organization/event.

Update requires optimistic `expected_version` and cannot reduce capacity below current confirmed bookings.

Close/cancel remains available to the authorized organization member even after parent event publication withdrawal. Updating a withdrawn event's time/capacity is denied.

## Participant booking authority

Participant request body is exactly:

`{"slot_id":"<24 hex>","action":"book|cancel"}`

There is no organization selector.

New booking requires:

- active participant account;
- stored slot belongs to active organization in current runtime boundary;
- slot is open;
- parent event remains exact-admitted;
- no schedule conflict with own confirmed activity booking or another confirmed v1 appointment.

Capacity allocation is atomic:

- free place → `confirmed`;
- full → `waitlist`;
- PostgreSQL locks slot row `FOR UPDATE OF s`;
- SQLite uses `BEGIN IMMEDIATE`.

Repeated active booking is idempotent and preserves queue timestamp.

Owner cancellation remains available after withdrawal/closure. Promotion occurs only while the stored slot is visible/open and parent event is still exact-admitted.

The cancelling participant receives only `queuePromotionOccurred`, never the promoted participant identity.

## Data minimization / truth boundary

Appointment v1 does not create:

- legacy `partner_engagement`;
- lead;
- marketing consent;
- medical consent;
- attendance;
- revenue evidence.

Booking response explicitly includes:

- `verifiedAttendance=false`;
- `marketingConsent=false`;
- `partnerLead=false`.

`/api/my-state/v1` exposes only current participant's v1 appointment rows and states:

- `partnerAppointmentIsAttendance=false`;
- `partnerAppointmentIsMarketingConsent=false`.

## Qualification

SQLite qualification proves:

- partner create + idempotent replay;
- immutable organization scope;
- cross-organization management denial;
- revoked membership denial;
- non-`strategic_partner` organization denial;
- event withdrawal blocks create/update while owner close stays available;
- capacity=1 → confirmed + waitlist;
- admitted cancel promotes waitlist;
- withdrawal cancel suppresses promotion;
- participant cannot inject organization selector;
- capacity cannot drop below confirmed count;
- no legacy partner engagement write;
- owner-only my-state visibility.

PostgreSQL 17 qualification proves:

- two concurrent participant bookings for capacity=1 serialize to exactly one confirmed + one waitlist;
- two concurrent partner creates with the same request id produce exactly one slot + one operation and return the same slot id;
- withdrawal preserves owner cancel while suppressing promotion.

Legacy migration upgrade / restore proof extends through migration 034 (35 migration files from the 001–025 fixture) and the source/restore fingerprint includes all three appointment v1 tables.

## Not solved

- payment/ticketing;
- appointment check-in or verified attendance;
- automatic partner notifications;
- broader organization types beyond the currently verified `strategic_partner` class;
- production Render/PostgreSQL admission;
- independent security/privacy review.

No production organization, participant data, paid resource or Render configuration is changed by this candidate.
