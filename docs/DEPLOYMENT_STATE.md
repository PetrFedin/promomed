# Render Deployment State

> Operational ledger for СОСТОЯНИЕ / Promomed. Production source-of-truth remains `PetrFedin/promomed/main`.

## Current authoritative live

The last verified live state remains the previously recorded v1.4 deployment until an exact-head v2 candidate is merged and verified.

- Repository: `PetrFedin/promomed`
- Production branch: `main`
- Render service: `sostoyanie-promomed-live`
- Service ID: `srv-daug7pnlot8c73b1aja0`
- URL: https://sostoyanie-promomed-live.onrender.com
- Region: Frankfurt
- Existing plan: free
- Last documented live boundary: SQLite under `/tmp`

Historical v1.4 deployment identifiers remain in Git history. This file intentionally does not fabricate a new deploy ID before a v2 deployment is actually observed.

## v2 integration candidate — 2026-10-01

Branch: `integration/master-plan-2026-10-01`.

Implemented and CI-proven in code:

- PostgreSQL 17 migrations and deterministic legacy seed;
- durable DB auth/session/consent/audit model;
- `/health` backend/migration visibility;
- `/ready` fail-closed production gate;
- PostgreSQL backup and restore proof;
- integration authority contracts and iPhone/static frontend checks;
- provider-failure fallbacks.

### Production admission requirements

A v2 release may be recorded as LIVE only after all of the following are true:

1. integration candidate is merged to `main`;
2. authoritative Render service deploys the exact merged SHA;
3. a dedicated durable PostgreSQL `DATABASE_URL` is configured;
4. migrations 0001–0003 are applied;
5. `GET /health` reports PostgreSQL/durable state;
6. `GET /ready` returns HTTP 200 with no pending migrations;
7. existing participant/organizer/partner journeys smoke successfully;
8. exact Render deploy ID and application SHA are recorded here.

### External providers

No provider is marked live merely from code presence. Directus, Meilisearch, Metarank, Owncast, Jitsi, pretalx, Novu, semantic retrieval and Umami require actual runtime configuration/evidence.

## Legacy services

Historical `sostoyanie-promomed-v06` and `sostoyanie-promomed-preview` are not source-of-truth.

## Release completion rule

Every completed wave records exact Git SHA, Render service/deploy ID, runtime URL, build evidence, health/readiness evidence, datastore authority and remaining provider boundaries.
