# ACTIVITY BOOKING — exact public admission boundary (2026-10-16)

Status: Draft source candidate stacked after SEC-11 Draft #112. Not deployed.

## Purpose

Legacy `/api/activity-booking` is the only route removed from the SEC-11 global deny registry in this slice. It may operate outside demo **only** when a new booking targets the exact current `program_items` payload that has an active public admission under `/api/public-state/v1`.

The other 19 legacy global/shared-capacity routes remain fail-closed outside demo.

## New booking rule

For `action=book` all of the following must hold:

1. authenticated role is `participant`;
2. `program_items.id` exists;
3. no active publication hold exists for that event ref;
4. an active `public_artifact_admissions` row exists for the SHA-256 of the exact current public event payload;
5. the admission is valid for the current demo/non-demo boundary.

Missing, withheld, withdrawn and hash-stale event versions all return the same `404 {"error":"program_item_not_found"}`. This prevents the booking endpoint from becoming an oracle for unpublished programme rows.

## Cancellation after withdrawal

The current owner may cancel an existing activity booking even if the event has subsequently been withdrawn or placed on hold. This preserves the participant's ability to remove their own state.

If the cancelled row was `booked`, waitlist promotion occurs **only if the event is still exactly admitted at cancellation time**. Withdrawal therefore cannot silently promote another participant into a no-longer-published event.

## Capacity concurrency

PostgreSQL locks the current `program_items` row with `SELECT ... FOR UPDATE` before capacity is counted or changed. Two simultaneous requests for capacity=1 must therefore serialize to exactly:

- one `booked`;
- one `waitlist`.

SQLite uses `BEGIN IMMEDIATE` when the handler starts outside an existing transaction.

Repeated active `book` is idempotent and does not reset queue time.

## Qualification

SQLite proves:

- unadmitted, held and hash-stale event versions share the same 404;
- exact admission allows booked + waitlist;
- owner cancellation after withdrawal succeeds;
- withdrawal suppresses waitlist promotion;
- admitted cancellation promotes the oldest waitlist;
- repeated active booking is idempotent;
- unsupported action is rejected.

PostgreSQL 17 proves:

- two concurrent requests for the last place cannot both become booked;
- withdrawal still allows owner cancellation;
- withdrawal prevents promotion and blocks a new booking.

## Truth boundary

This slice does **not** claim:

- booking equals attendance;
- waitlist equals confirmation;
- public admission is medical approval;
- session booking creates partner consent or a lead;
- production Render/PostgreSQL has been admitted.

No production data, paid resource or schema migration is changed by this candidate.
