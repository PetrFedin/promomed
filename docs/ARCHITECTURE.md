# Architecture — v1.3 Pilot Command System

## Runtime

Один Python web service обслуживает API и статический iPhone-first frontend. Операционная authority хранится в SQLite и защищается process-level lock для demo/pilot runtime.

## Role boundaries

- participant — маршрут, бронирования, attendance-facing journey, consent;
- organizer — venue state, incidents, streams, speaker readiness, staff, broadcasts;
- staff — check-in/operational execution;
- partner — appointment/engagement surfaces;
- sales — контролируемый demonstration route.

## Operational authority

Ключевые сущности: users/tokens, program items, venue state, bookings/waitlist, attendance, incidents, stream state, staff assignments, speaker readiness, appointment slots/bookings, broadcasts, partner engagement, customer signals и audit events.

## Command layer

`GET /api/command` агрегирует live floor state, queues, staff, speaker readiness, incidents/SLA, streams, broadcasts и partner appointment desk для Pilot Command System и Owner Control Tower.

## Production boundaries

Текущий runtime — pilot/demo authority. Для production admission требуются persistent PostgreSQL, migrations, durable auth/session store, rate limiting, secrets management, signed QR/pass authority, provider integrations, observability и backup/restore policy.


## Persistence admission v1.8

Runtime storage is selected through `app/db.py`.

- SQLite remains a demo/local compatibility backend.
- PostgreSQL is the only backend eligible for `production_ready=true`.
- schema authority lives in versioned `migrations/sqlite` and `migrations/postgres`;
- applied migration checksums are recorded in `_schema_migrations`;
- authentication sessions are database-backed as token hashes;
- `/health` is liveness; `/ready` is schema/data/backend admission;
- backup/restore evidence is part of CI.

The service remains one deployable application; this is a bounded persistence layer, not a microservice split.


## Bounded-context application structure — PROMO-INT-01 foundation

The runtime remains one deployable Python service. Internal authority is now separated by bounded context rather than by microservice:

- `app/db.py` — persistence adapter and migration authority;
- `app/auth.py` — durable authentication/session helpers;
- `app/core.py` — shared state, audit and notification primitives;
- `app/demo.py` — isolated sales/demo orchestration;
- `app/programme.py` — programme and attendance read projection;
- `app/content.py` — content/product/speaker/Studio read projection;
- `app/community.py` — community/follow/direct-message read projection;
- `app/learning.py` — learning/challenge projection;
- `app/partners.py` — partner/appointment/consented-interest projection;
- `app/operations.py` — venue/incident/staff/stream projection;
- `app/participant.py` — participant profile/passport/follow-up projection;
- `app/analytics.py` — composition of bounded projections and commercial metrics;
- `server.py` — HTTP composition/dispatch and compatibility surface.

This is deliberately an internal modularisation, not a microservice split. Existing API semantics remain stable.

Remaining PROMO-INT-01 work: move command/write handlers out of `server.py` context by context while preserving one deployment and the same authorization/audit gates.
