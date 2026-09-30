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
