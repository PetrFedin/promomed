# CL365-02 — Canonical event registration authority integration

Draft candidate; no production release.

## Linked sources
- `participant_event_registrations_v1` joined to `event_editions_v1` is the current source for event registration, with owner email scoping and demo-edition isolation.
- Confirmed, waitlisted, cancelled and cancelled-edition states are represented separately. Only currently confirmed registrations establish a D1/D7/D30 baseline.
- An older `registrations` row is a clearly labeled compatibility fallback **only** when there are no canonical registration rows. Canonical waitlists and cancellations explicitly suppress stale legacy confirmation.
- Baseline timestamps for canonical rows are the most recent `updated_at` status timestamp: this is **not immutable confirmation proof**. It must not be promoted to revenue, externally verified retention or attendance.
- `session_attendance` `participant_self_report` with `self_reported` or `self_reported_complete` appears only as unverified self-attendance, never a staff-verified attendance claim.
- This is a read-only projection; no migration, backfill, implicit registration creation or marketing consent.

## Qualification
Run `tests/test_client365_evidence.py` and core UI tests against SQLite. Final integrated gate additionally needs PostgreSQL, browser owner-scope tests, concurrency and independent security review. Keep Draft PR unmerged until evidence is complete.
