# Implemented Scope — through v1.4

## Year-round home & media
Editorial lead; Promomed Today; company/R&D stories; educational product context; health topics; explainers; healthy launches; audio/video/FM; lectorium; curated Box concept; partner ecosystem; 1/7/30 continuation.

## Conference
42 events, seven parallel venues, 09:00–20:00. Keynotes, lectures, debates, panels, roundtables, workshops, practices, appointments, networking, community, partner showcase and B2B salon. Timetable/grid, detail pages, My Schedule, Smart Route conflict resolution, live/replay and venue concierge.

## Experience
Registration, profile, programme, bookings, waitlist, ticket/QR, partner appointments, post-event journey and role-based surfaces.

## Operations
Pilot Command System: floor map, occupancy, queues, venue status, staff assignments, incidents/SLA, speaker readiness, session attendance, stream health and operational participant alerts.

## Partner & commercial
Partner cockpit; contracted/engagement surfaces; appointment desk; consented leads; content/event/attendance signals and partner attribution.

## Intelligence
Customer Intelligence, retention D1/D7/D30, track/partner signals and Owner Control Tower.

## Current live
`PetrFedin/promomed/main` → Render `sostoyanie-promomed-live`.
See `docs/DEPLOYMENT_STATE.md`.

## Production boundaries
Durable PostgreSQL/migrations; production auth/session/consent; real push; signed QR/Wallet; streaming provider; analytics governance; legal/medical review workflow and backup/restore.


## Persistence admission layer — repository scope

Implemented in code, pending production infrastructure admission:

- database adapter for SQLite/PostgreSQL;
- versioned/checksummed migrations;
- durable hashed sessions;
- liveness vs readiness split;
- deterministic seed controls;
- backup/restore utility;
- SQLite and PostgreSQL CI authority tests.

Not yet claimed: public Render exact-SHA deployment or admitted production PostgreSQL.


## Bounded-context foundation — PROMO-INT-01

Implemented in repository:

- authentication/session logic extracted from the HTTP monolith;
- shared audit/notification/state primitives extracted;
- demo orchestration isolated;
- programme, content, community, learning, partner, operations and participant read projections separated;
- analytics now composes projections instead of owning all domain SQL;
- architecture contract prevents extracted functions from silently returning to `server.py`.

The service is still a single deployable application. Write/command route extraction remains incremental work and is not claimed complete.


## Command boundary wave 1 — PROMO-INT-01

Extracted 21 existing POST routes from `server.py` into bounded command handlers for community, learning, participant and programme contexts. HTTP and API semantics remain unchanged.

New CI coverage checks:

- command modules exist and compile;
- extracted routes cannot silently return to the HTTP monolith;
- consent/role negative tests for representative commands;
- existing responsive/browser and PostgreSQL contracts remain mandatory.

Remaining PROMO-INT-01 work: operations, partner/commercial, editor/CMS and demo write-route extraction.


## Command boundary wave 2 — PROMO-INT-01 complete in repository

Extracted the remaining operations, partner/commercial, editorial-demo and demo-control POST routes from `server.py`.

Repository state now has:

- bounded read projections by domain;
- bounded write handlers by domain;
- normalized command outcomes;
- centralized auth/transaction/HTTP composition;
- architecture regression gates;
- representative role, permission and consent negative tests.

`server.py` is ~379 lines versus 942 before PROMO-INT-01.

This is repository completion only. Durable PostgreSQL live admission remains required before Phase 1.


## Phase 0 admission authority — repository scope

Added:

- durable account table migration for SQLite/PostgreSQL;
- salted scrypt password authority;
- database-backed login role/name/status;
- demo identities seeded only in demo mode;
- production readiness rejects demo seed and demo accounts;
- clean PostgreSQL admission probe;
- privacy-safe source/restore catalog fingerprint;
- provider-neutral manual admission workflow;
- clean PostgreSQL 17 admission + backup/restore proof in PR CI.

External durable PostgreSQL is still required before Phase 0 can be marked COMPLETE.


## Production identity bootstrap — Phase 0

Repository scope now includes `ops/provision_account.py` for deliberately creating or rotating non-demo accounts on an admitted PostgreSQL authority.

Guards:

- PostgreSQL-only;
- production readiness required before account write;
- demo seed must be off;
- `@demo.ru` identities rejected;
- salted scrypt password hash;
- no password CLI argument;
- explicit `--rotate` required for replacement;
- rotation revokes existing sessions.

PostgreSQL 17 CI proves create/login/session/rotate/revocation and demo-identity rejection before backup/restore.


## Live admission proof authority — Phase 0

Added two complementary release gates:

- public live proof requires exact SHA and refuses a SQLite runtime that claims production readiness;
- dedicated manual PostgreSQL proof targets the Render admission service and requires durable PostgreSQL, clean migrations, demo seed off, zero demo accounts and `production_ready=true`.

This closes repository-side live verification for PROMO-INT-00. External durable PostgreSQL resource admission remains outstanding.
