# SEC-11 — legacy global write boundary (2026-10-15)

Status: Draft source-only hardening stacked after event-registration authority PR #107. Not deployed.

## Why this exists

Several pre-tenant POST routes mutate singleton/global tables, shared capacity, demo staff state, or globally identified partner/appointment records. Role checks alone do not prove event/organization scope.

Until each route has a versioned tenant/event authority, the following legacy mutations are **demo-only**:

### Operations/global event state
- /api/move-session
- /api/live
- /api/checkin
- /api/staff-assignment
- /api/speaker-readiness
- /api/broadcast
- /api/venue-state
- /api/incident
- /api/stream-control
- /api/venue
- /api/phase

### Partner/shared appointment state
- /api/placement
- /api/lead
- /api/appointment-booking
- /api/appointment-manage

### Legacy programme/shared-capacity paths
- /api/register
- /api/booking
- /api/activity-booking
- /api/replay
- /api/session-attendance

In non-demo runtime, these exact paths return 404 before JSON body parsing, authentication or database access. The same guard is applied inside operations/partner/programme command handlers to prevent direct-call bypass.

## Explicitly not denied

This registry does not block the new qualified/versioned routes:
- /api/my-state/v1/*
- /api/event-registration/v1
- /api/participant-registration/v1/request
- /api/participant-registration/v1/verify
- /api/public-state/v1
- /api/partner-collaboration

New production APIs should never be "unblocked" by deleting a legacy route from this list. They need an explicit authority with negative cross-scope tests.

## What this does NOT solve

- replacement appointment authority;
- tenant-scoped partner placement/lead model;
- scoped staff↔venue/event assignment and check-in;
- activity/session attendance v2;
- anti-abuse/rate limits;
- governance/institutional generic-role scope;
- production Render/PostgreSQL admission.

The legacy demo paths remain available when PROMOMED_SEED_DEMO is enabled so qualification/demo evidence is not silently changed.

## Qualification

- exact registry contains 20 routes;
- non-demo HTTP request to each route is denied before body/auth/db;
- query strings cannot bypass path normalization;
- direct domain-handler calls fail closed;
- demo mode preserves the original role checks;
- versioned production-shaped routes are explicitly outside the registry;
- test module is included in UI Quality and SQLite/PostgreSQL persistence workflows.

No production data, customer identity or paid resource is touched.
