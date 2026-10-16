# REG-03: Database-observed registration transitions

Draft / source-only. No production deployment or legacy history backfill.

## Authority and semantics

The table `event_registration_transitions_v1` is created in migration 036 (SQLite and PostgreSQL). Database triggers capture insertion and **actual status changes** on `participant_event_registrations_v1`, including waiter promotions that occur inside another participant's cancellation transaction. Replays and updates to timestamps without status changes do not create fictitious transitions. Sequence number is scoped to (event_id, email). Parent event and owner deletion erase these records, because containing email makes history personal data.

The `observed_at` timestamp is captured at the database using the statement/trigger clock; it is a **database-observed timestamp**, not a notarized timestamp or externally signed evidence. No retrospective history is guessed for rows that pre-date migration 036.

Client365 prefers the latest recorded transition into `confirmed` when a current canonical registration is confirmed. If no usable history exists, it falls back to provisional `updated_at`, which remains an explicitly less-trustworthy origin. Waitlisted, withdrawn and cancelled-edition registrations are never treated as confirmed or proof of attendance.

## Qualify

- SQLite: insert -> waitlist -> promotion, replay, cancellation, update immutability, owner erasure.
- PostgreSQL 17: concurrent competition for last seat and resulting transition rows.
- All source+projection changes must pass exact-HEAD UI/architecture and migration/restore tests before merge.
- Registration != attendance, self report != verified attendance, and lead != marketing consent.
- No merge/deploy until independent review and isolated Render/PostgreSQL governance gates.

## Known limitations

- The operational history is append-only for normal row edits, **not** tamper-evident or externally certified.
- Existing records have no validated transition events until their next status change; the system does not backdate confirmations.
- DB administrators and backups may expose or remove personal data; privacy and retention policy still needs explicit governance.
