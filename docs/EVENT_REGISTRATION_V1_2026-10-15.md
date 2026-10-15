# EVENT REGISTRATION V1 — capacity / waitlist authority (2026-10-15)

Status: Draft source candidate stacked after participant self-registration PR #105. Not deployed.

## Why a new authority

Legacy `registrations(email,status,ts)` has no event id, capacity, queue order or concurrency control. It cannot safely represent production admission.

In non-demo runtime, legacy `POST /api/register` is therefore denied with 404. Demo behavior remains for presentation compatibility.

## Data model — migration 033

`event_editions_v1` stores event id, title, start timestamp, registration status (`open | closed | waitlist_only | cancelled`), capacity, demo flag and timestamps.

`participant_event_registrations_v1` uses composite key `(event_id,email)` and status `confirmed | waitlist | cancelled`, with requested/updated timestamps and source fixed to participant.

No attendance, medical consent, marketing consent, partner lead or commercial value is stored in this table.

## Participant API

### GET /api/event-registration/v1

Authenticated active participant only. Returns eligible event editions and only the current account's status. It never returns other participant identities or queue contents.

### POST /api/event-registration/v1

Exact body: `{"event_id":"...","action":"register|cancel"}`.

Register rules:
- `open` + free capacity → `confirmed`;
- full capacity → `waitlist`;
- `waitlist_only` → `waitlist`;
- `closed/cancelled` → 409;
- repeat of an already confirmed/waitlisted registration is idempotent.

Cancel rules:
- own active registration only;
- confirmed cancellation may promote the earliest waitlisted registration;
- response says only whether a promotion occurred, never who was promoted.

## Concurrency

The event row is the serialization boundary: PostgreSQL uses `SELECT ... FOR UPDATE`; SQLite uses `BEGIN IMMEDIATE`. Because this repository does not globally enable SQLite foreign-key enforcement, migration 033 also installs database triggers that reject event-registration rows whose event or account parent does not exist, plus explicit delete cleanup.

The dedicated PostgreSQL 17 qualification starts two registration requests concurrently against capacity=1 and requires exactly one `confirmed` and one `waitlist`.

## My State integration

`/api/my-state/v1` adds owner-scoped `eventRegistrations`. Legacy single `registration` remains temporarily for demo/backward compatibility but is not the production admission authority.

Truth flags explicitly state registration != attendance and waitlist != confirmation.

## Non-demo provisioning

`ops/provision_event.py` is PostgreSQL-only, requires `PROMOMED_REQUIRE_POSTGRES=true`, refuses demo seed mode, requires a production-ready schema, requires timezone-aware `--starts-at`, does not overwrite without `--update`, and refuses capacity below the current confirmed count.

The CLI creates operational event authority. It does not by itself publish an event anonymously; public publication remains governed separately by public-state/publication admission.

## Qualification

- SQLite: confirmed/waitlist/promotion, replay idempotency, closed/waitlist-only semantics, owner-only read, foreign-role denial, legacy route denial.
- PostgreSQL 17: concurrent last-place serialization.
- PostgreSQL CLI: create succeeds, duplicate create fails closed.
- Legacy 001–025 upgrade proof extends through migration 033 (34 migration files total in the fixture).
- Source/restore fingerprint includes both event tables.
- server.py remains below the existing 405-line architecture budget.

## Still required before production

- event-registration UI in /personal/;
- real non-demo account + SMTP proof from PR #105;
- explicit public event publication/governance alignment;
- CAPTCHA/network rate limiting for account signup;
- actual Render/PostgreSQL #64/#65;
- protected main #94;
- independent security/privacy review.

No deployed pilot, attendance or event-demand metric may be inferred from these tests.
