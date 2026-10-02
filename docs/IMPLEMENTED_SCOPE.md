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
