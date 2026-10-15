# PARTICIPANT INVITE V1 — controlled onboarding boundary (2026-10-15)

Status: Draft source candidate stacked after public-state PR #103. Not deployed; not open self-registration.

## Goal

Complete the first controlled guest → registered participant path without exposing an unrestricted account-creation endpoint.

### Organizer authority

`POST /api/participant-invite/create`
- authenticated organizer only;
- exact body: `email`, `name`;
- non-demo runtime rejects `@demo.ru` identities;
- fixed 72-hour lifetime;
- one pending invite per email;
- expired pending invite is closed before a replacement is issued;
- raw invite token is returned once and **never stored**; DB stores SHA-256 only;
- audit event contains invite ID but not token.

`POST /api/participant-invite/revoke`
- organizer can revoke only an invite created by that same organizer;
- foreign/missing invite uses the same 404 shape.

### Public activation

`POST /api/participant-invite/accept`
- intentionally public because the high-entropy one-time token is the authority;
- exact body: `token`, `password`; no email/name selector;
- query parameters are rejected before body parsing/auth;
- password >=14 chars and at least three character classes;
- token lookup is hash-only;
- SQLite uses `BEGIN IMMEDIATE`; PostgreSQL locks the invite row `FOR UPDATE`;
- acceptance atomically creates an active participant account + confirmed registration + consumes invite;
- **no session is created automatically**; user must subsequently use normal `/api/login`;
- replayed, expired, revoked and unknown tokens use `404 invalid_or_expired_invite`.

The participant account is still the existing Promomed account authority; this feature does not create a parallel identity system.

## Guest UI

`/join/` accepts a token through URL **fragment** (`#token=...`), never query string. Browser fragments are not sent in HTTP request targets. The page immediately removes the fragment from the visible URL with `history.replaceState`.

The page:
- does not ask for email/name;
- does not use localStorage/sessionStorage/cookies;
- keeps token/password in page memory only;
- clears fields on pagehide;
- sends only token + password to activation;
- after success routes to the existing `/personal/` login;
- does not automatically log the participant in.

## Migration 032

`032_participant_invite_onboarding` adds `participant_invites`:
- raw token absent;
- one active pending invite per email;
- explicit pending/accepted/revoked lifecycle;
- expiry and consumed timestamps;
- no invite is seeded by migrations.

Legacy upgrade and source/restore fingerprint now include this authority; total migration files per backend become 33 because both 026 stems are intentionally distinct.

## Qualification

SQLite:
- raw token absent from DB/audit;
- role/demo-identity controls;
- account + registration creation without session;
- one-time replay semantics;
- 8-way parallel acceptance -> exactly one account/registration;
- creator-scoped revoke;
- expired/weak-password denial;
- expired invite replacement;
- account-created-after-invite race.

PostgreSQL 17:
- 8-way parallel acceptance -> one 201, remaining invalid-token responses;
- parallel organizer creation -> exactly one pending invite, second 409;
- acceptance creates no auth session and normal login remains required.

HTTP/UI:
- public accept dispatches before authentication;
- organizer creation requires current authenticated actor;
- query selector rejected before body/auth;
- fragment-only/no-storage source contract;
- responsive browser golden path creates organizer invite, activates it, logs in at `/personal/`, sees confirmed registration and proves invite replay fails.

## Deliberate limitations

- No email/SMS provider or automatic invite delivery; response says `manual_secure_channel_required`.
- No open self-registration.
- No password reset/recovery flow.
- No distributed rate limiter or login throttling yet.
- No event-specific multi-event registration schema; current `registrations` table remains the single-event MVP authority.
- No proof of real attendee identity.
- No production deployment, real participant data or production Render/PostgreSQL admission.
- Organizer tenancy itself still needs the broader authorization work in #100/#97 before multi-organization production.

Dependencies remain #64, #65, #94, #98, #100 and independent review. Green CI qualifies candidate behavior only.
