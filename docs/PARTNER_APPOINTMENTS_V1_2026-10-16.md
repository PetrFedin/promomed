# PARTNER APPOINTMENTS V1 — organization-scoped appointment authority

Status: Draft qualification candidate. Not deployed.

## Purpose

Replace legacy global appointment slot/booking writes with verified organization scope.

Route:
- GET /api/partner-appointments/v1
- POST /api/partner-appointments/v1

Roles:
- partner: create/update slots only for organizations where the authenticated partner has an active verified operator/administrator membership;
- participant: book/cancel only own appointment rows.

## Placement dependency

A slot can be created only while the target organization has Partner Commercial placement status `enabled`.

New participant bookings require:
- active participant account;
- slot status `open`;
- organization placement still `enabled`;
- explicit `contact_consent=true`.

If placement is paused/ended, new bookings return 404-equivalent unavailable semantics. Existing participants can still cancel their own appointment.

## Capacity

Each slot has:
- absolute `starts_at` / `ends_at`;
- capacity;
- state `open / closed / cancelled`;
- optimistic version.

PostgreSQL locks the slot row `FOR UPDATE` before capacity decisions.
SQLite uses `BEGIN IMMEDIATE` when needed.

For capacity=1, two simultaneous requests must produce exactly:
- one `booked`;
- one `waitlist`.

## Waitlist promotion

Cancelling a booked appointment may promote the oldest waitlist entry only while:
- slot remains open;
- organization placement remains enabled;
- capacity is available.

If the placement is paused/ended or the slot is closed/cancelled, owner cancellation succeeds but no waitlist promotion occurs.

The cancelling participant receives only a boolean `queuePromotionOccurred`, never the promoted person's identity.

## Contact visibility

Booking is explicit slot-specific contact sharing.

Partner snapshot shows participant email only for current `booked` or `waitlist` rows within the partner's verified organization.

After participant cancellation:
- participant retains cancelled state in own snapshot;
- partner snapshot no longer contains that participant contact.

This is not marketing consent, medical consent, attendance proof, partner lead conversion, sale or revenue.

## Slot management

Partner may update only slots owned by a verified member organization.

Optimistic `expected_version` prevents lost updates.
Capacity may not be set below the current number of booked participants.
Cancelled slot is terminal.

## Migration 035

Adds:
- `partner_appointment_slots_v1`
- `participant_partner_appointments_v1`

SQLite adds explicit parent-authority triggers because runtime does not globally enable `PRAGMA foreign_keys=ON`.

Parallel migration proof extends to 36 migration files and source/restore fingerprint includes both tables.

## Qualification

SQLite proves:
- partner A cannot create slot for organization B;
- booked/waitlist behavior;
- promotion on active cancellation;
- promotion suppression when placement paused;
- explicit contact consent;
- idempotent active replay;
- partner snapshot tenant isolation;
- cancellation removes contact from partner snapshot;
- participant snapshot owner-only;
- optimistic version/capacity validation;
- query-selector/foreign-role denial.

PostgreSQL 17 proves:
- two concurrent requests serialize the last place;
- membership revocation immediately removes partner visibility/write authority;
- participant owner cancellation remains available after partner membership revocation.

## Not solved

- public discovery of appointment slots;
- participant reschedule as an atomic operation;
- outbound notification after waitlist promotion;
- calendar integration;
- payment/ticketing;
- check-in/attendance;
- backup erasure policy;
- production Render/PostgreSQL admission;
- independent privacy/security review.

Legacy `/api/appointment-booking` and `/api/appointment-manage` remain blocked outside demo.


## APPT-02 lifecycle hardening candidate (2026-10-16)

- A commercial placement is available only while its parent institutional organization remains active, non-demo scope matches, and the partner reference is present. Historical `enabled` placement by itself is not authorization after organization deactivation.
- New `book` requests fail closed when the persisted slot's `ends_at` has passed, including requests from existing waitlisted participants. The failure does not expose another participant's identity.
- Cancelling an existing appointment remains participant-owned even after the time window expires or the organization becomes inactive; neither condition promotes waitlisted participants.
- Partner cannot update a slot to `open` with an already elapsed end timestamp. Existing `closed` and `cancelled` state semantics are unchanged.
- SQLite regressions are included in `tests/test_partner_appointments.py` and in the existing UI / persistence workflow suites. They must pass at the candidate's exact SHA before review.
- No existing migration is rewritten; no schema change, production deployment, Render settings, real account, medical content, or paid resource is touched.

This is a Draft-only source hardening change, not production admission. Independent review, final CI, isolated PostgreSQL source/restore and Render governance remain outstanding.
