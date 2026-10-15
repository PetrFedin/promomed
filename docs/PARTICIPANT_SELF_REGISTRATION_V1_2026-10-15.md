# PARTICIPANT SELF-REGISTRATION V1 — verification boundary (2026-10-15)

Status: Draft source candidate stacked after PR #103. Not deployed. No existing participant identity is modified.

## Goal

Enable a real participant to create a Promomed/СОСТОЯНИЕ account without a demo identity while preventing:

- activation of an account for an email the person does not control;
- account-existence enumeration;
- implicit event registration, partner marketing consent or medical consent;
- plaintext verification-code storage;
- indefinite duplicate storage of password/verification hashes.

## Public endpoints

### POST /api/participant-registration/v1/request
Exact JSON fields: `email`, `name`, `password`.

Validation:
- normalized lowercase email, maximum 254 chars;
- participant name 1–80 chars, no control characters;
- password 14–256 chars and at least three character classes;
- `@demo.ru` identities rejected outside demo mode.

Production behavior:
- requires `PROMOMED_REGISTRATION_CODE_SECRET`;
- requires configured SMTP host + from address;
- stores only a pending scrypt password hash and HMAC-SHA256 verification hash;
- sends a 6-digit one-time code over TLS SMTP;
- returns the same accepted/check-email response shape for a new email, an existing account, or an active cooldown case. A fake opaque request id is used where there is no real pending request so the endpoint cannot be used as an account lookup.

Demo behavior:
- may return `demoVerificationCode` for CI/browser qualification only;
- this field must never appear in non-demo runtime.

### POST /api/participant-registration/v1/verify
Exact JSON fields: `request_id`, `code`.

- request id is 32 lowercase hex chars;
- code is exactly six ASCII digits;
- pending request expires after 10 minutes;
- five failed verification attempts permanently block the request;
- only a successful pending request creates an active `participant` account;
- successful verification issues a server session;
- **no row is inserted into event `registrations`**. Event registration remains a separate authenticated action.

## Secret lifecycle

Migration `032_participant_self_registration` enforces:

- `password_hash` + `verification_hash` are non-empty only while status is `pending`;
- terminal statuses `verified`, `expired`, `blocked` require both fields to be empty;
- only one pending request per email;
- verified state requires `verified_at`.

Thus the pending table is not a second long-lived credential store after verification.

## Delivery

`app/registration_delivery.py` uses Python SMTP with STARTTLS. Host/from/user/password are server environment configuration. Password/code values are not logged by the module.

This is a transport contract, not proof that Promomed has selected/configured a real mail provider. Production registration remains fail-closed with HTTP 503 until the delivery settings and server secret are present and separately accepted.

## Qualification

SQLite:
- pending-only request;
- correct verification creates participant account + session;
- event registration is not auto-created;
- existing-account response shape is indistinguishable from accepted request;
- provider failure rolls back the pending write;
- missing delivery/secret returns 503 without DB write;
- five bad codes block;
- expiration blocks;
- terminal states purge password/code hashes;
- public HTTP dispatch occurs before authentication.

PostgreSQL 17:
- request creates only one pending record;
- verification creates one active participant account/session;
- no event-registration row;
- terminal registration record has no retained credential/code hashes.

Migration upgrade and source/restore fingerprint are extended through migration 032.

## Not solved by this slice

- actual provider credentials / inbox delivery proof;
- CAPTCHA / bot defense and network-level rate limiting;
- password recovery;
- email change;
- duplicate human/person resolution across different emails;
- event registration capacity/waitlist UX;
- public content governance UI;
- production Render/PostgreSQL admission;
- independent privacy/security review.

Dependencies remain #64, #65, #94, #98, #100 and PR stack #92→#93→#96→#99→#101→#102→#103.
