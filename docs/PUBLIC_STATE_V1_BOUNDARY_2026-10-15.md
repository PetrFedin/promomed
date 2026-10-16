# PUBLIC STATE V1 — explicit publication admission boundary (2026-10-15)

Status: Draft source candidate stacked after PR #102. Not deployed. It does not make any existing repository row public by default.

## Purpose

Replace the anonymous portion of blocked legacy `/api/state` with a small, versioned public read model:

- `GET /api/public-state/v1`
- no authentication required;
- no client selectors or query parameters;
- returns only admitted content and agenda entries;
- no account, booking, attendance, notification, partner CRM, commercial KPI, revenue or retention data.

## Admission rule

A canonical content/event row is returned only when all are true:

1. content is already `status='published'` (events rely on the explicit admission table);
2. there is no active `publication_holds` row for its kind/ref;
3. `public_artifact_admissions` contains an active admission for the **SHA-256 of the exact public payload fields**;
4. in a non-demo runtime, the admission is not `demo_only=1`.

Changing a title, summary, schedule, venue, audience, capacity, partner label or other public field changes the payload hash and immediately makes the old admission ineffective. A reviewer/source reference is evidence metadata, not a claim that the reviewer is independently qualified; external reviewer authority remains a separate governance gate.

## Data minimization

### Content fields
`id, kind, theme, title, dek, duration, author, partner` plus admission metadata.

The internal `reviewer` column and workflow `status` are intentionally not returned.

### Agenda fields
`id, start, end, venue, track, format, title, audience, capacity, stream, replay, partner` plus admission metadata.

No participant identity, booking count, occupancy, check-in, lead, consent, private message or analytics value is returned.

## Migration 031

`031_public_artifact_admission` adds a hash-bound admission ledger for `content` and `event`. There is at most one active admission per artifact. Withdrawal requires a withdrawal timestamp. This migration does **not** seed admissions.

A fresh non-demo database therefore serves an empty public-state until governance explicitly admits exact artifact versions.

## Qualification

- SQLite tests prove default-private behavior, exact admission, active-hold denial, draft denial, hash invalidation, withdrawal, demo-only mismatch, zero-query-selector behavior and HTTP dispatch before authentication.
- PostgreSQL 17 test proves an exact admitted content/event version appears, then disappears after payload mutation/withdrawal.
- Existing legacy-upgrade proof is extended from 31 to 32 migration files and checks the new table.
- Source/restore database fingerprint includes `public_artifact_admissions`.
- Server remains under the existing composition-layer line budget.

## Deliberate limitations

This PR does not provide:
- a UI for governance to grant or withdraw admission;
- independently verified medical/legal reviewer credentials;
- self-registration;
- participant booking creation in non-demo;
- organization analytics;
- production Render/PostgreSQL admission;
- evidence that current demo content is suitable for real publication.

Do not manually mark demo rows as real public content to create a showcase. Positive production publication requires authenticated governance workflow, source/reviewer authority and independent review.

Dependencies remain #64, #65, #94, #98, #100 and the PR stack #92→#93→#96→#99→#101→#102.
