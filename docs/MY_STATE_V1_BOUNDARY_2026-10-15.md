# MY STATE V1 — participant-owned workspace boundary (2026-10-15)

Status: source candidate only, stacked after Draft PR #99. Not deployed and not a production/pilot acceptance claim.

## Purpose
Replace one part of the blocked legacy global `/api/state` with an account-owned projection.

### Read surface
`GET /api/my-state/v1`
- current active participant account only;
- own registration row;
- own activity bookings, capped at 50 with explicit truncation flag;
- own personal notes, 20 per page with opaque owner-scoped cursor;
- no public catalogue titles, partner analytics, medical inference, attendance inference, revenue, retention or cross-account selectors.

`GET /api/my-state/v1/notes/before/<note_id>`
- cursor must belong to current account;
- missing and foreign cursors both return the same 404 shape;
- query-string account selectors are rejected at the server composition layer.

### Write surface
`POST /api/my-state/v1/notes`
- participant only;
- exact `text` + 32-hex `request_id`;
- 2,000-character maximum;
- same request + same text returns original note; same key + different text returns 409.

`POST /api/my-state/v1/notes/delete`
- owner-scoped;
- text is erased from active DB row while the idempotency tombstone remains to prevent retry resurrection;
- this is NOT proof that historical backups were physically purged.

`POST /api/my-state/v1/logout-all`
- revokes all live sessions of the authenticated account only.

## Persistence
Migration `030_personal_workspace_notes` exists for SQLite and PostgreSQL. PostgreSQL uses FK ON DELETE CASCADE. SQLite additionally uses an account-delete trigger because the legacy connection factory does not globally enable `PRAGMA foreign_keys`.

## Required release evidence
1. Exact-SHA SQLite and PostgreSQL CI.
2. Isolated 001–025 -> 026/027/028/029/030 upgrade proof and reapply.
3. Source/restore fingerprint includes `personal_notes_v1`.
4. Authenticated HTTP selector-denial regression.
5. Independent privacy/security review.
6. Non-demo browser flow only after Issue #65 isolated PostgreSQL and Issue #64 actual Render admission.
7. UI must fence stale async responses on account switch/logout and never persist bearer tokens to localStorage/sessionStorage.
8. Backup retention/deletion policy remains separate governance work.

This surface does not unblock public discovery (#98), organization analytics (#97 C/E), legacy global POST commands (#100), or production readiness by itself.
