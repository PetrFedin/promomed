# Architecture — v2.0 Integration Authority Candidate

## Runtime model

СОСТОЯНИЕ остаётся одним deployable Python web service с iPhone-first frontend, но новая интеграционная логика больше не наращивается внутри монолитного `server.py`.

Canonical production path:

`HTTP/API -> Promomed bounded context -> PostgreSQL authority -> replaceable sidecar/provider`

Demo/dev fallback:

`HTTP/API -> same Promomed bounded context -> SQLite`

SQLite разрешён только как demo/dev fallback. `GET /ready` становится успешным только при PostgreSQL authority без pending migrations.

## Persistence and identity

- `DATABASE_URL` выбирает PostgreSQL; без него используется explicit SQLite fallback.
- Versioned migrations: `migrations/postgres/0001..0003`.
- Durable `accounts`, password hashes, sessions, consent records and audit/business events live in the database.
- `/health` exposes backend/durability/migration state.
- `/ready` is the production-admission gate.
- `scripts/backup_postgres.sh` and `scripts/restore_postgres.sh` are exercised in CI against PostgreSQL 17.

## Bounded contexts

New integration code is split into:

- `app/db/` — database adapter and migrations;
- `app/auth/` — durable identity/session authority;
- `app/content/` — publication versions and review state machine;
- `app/evidence/` — sources, citations and claim lineage;
- `app/search/` — rebuildable search projections and semantic adapter;
- `app/recommendations/` — explainable non-medical ranking;
- `app/media/` — broadcasts, replay progress, transcript jobs and Expert Rooms;
- `app/programme/` — programme production and expert authority;
- `app/partners/` — commercial workspace and consent-separated leads;
- `app/notifications/` — delivery orchestration;
- `app/venue/` — versioned venue geometry and live overlays;
- `app/analytics/` — anonymous public acquisition telemetry only;
- `app/gates/` — explicit deferred/reference integration decisions;
- `app/integration_api.py` — bounded integration router;
- `app/providers.py` — failure-safe provider adapter.

Legacy participant/event/operations/community/learning APIs remain compatible while their new extensions are routed through bounded contexts. This is a code-organisation migration, not a microservice mandate.

## Content and evidence authority

Publication workflow:

`draft -> editorial_review -> medical_review -> compliance_review -> approved -> scheduled/published -> corrected/retracted`

Promomed stores a versioned publication snapshot and hash. A Directus payload may be imported only through the Promomed adapter; an approved/published import requires an explicit editorial + medical + compliance review chain.

Evidence is stored separately from claims. A DOI/URL/source record never automatically becomes proof of a medical statement. Claim-to-source links retain reviewer state.

## Search and personalisation

Meilisearch is a rebuildable search sidecar over `search_documents`; canonical records stay in Promomed.

Semantic retrieval is a replaceable PostgreSQL-compatible/provider adapter with deterministic term-overlap fallback. sqlite-vec is not introduced as a permanent authority after PostgreSQL migration.

Metarank is optional. Recommendations are accepted only with allow-listed reason codes:

- `follows_expert`;
- `subscribed_topic`;
- `attended_related_session`;
- `continue_learning_track`;
- `popular_in_selected_topic`.

No recommendation path may emit diagnosis, treatment, drug recommendation or health-risk classification.

## Media and transcript pipeline

`broadcast/provider -> Promomed media state -> replay -> transcript job -> timecoded segments -> generated takeaway -> human review -> published/visible takeaway`

Owncast is a media provider boundary only. Video.js is the playback UI. A generated takeaway cannot be treated as approved expertise until a human reviewer approves it, and every takeaway must resolve to a transcript time range.

Jitsi is media transport for AMA/office-hours sessions only. Room listing, eligibility, booking, consent and attendance remain Promomed authority; the feature is not telemedicine.

## Programme and experts

pretalx may supply an approved, versioned upstream snapshot. Public `program_items`, participant bookings and attendance remain Promomed authority.

Expert qualifications and disclosures are stored as reviewed records. Qualifications are never generated from biography text.

## Partner and notification boundaries

Partner commercial contacts, participant consented leads and aggregate measurement are distinct entities. CRM-style tooling cannot override participant consent.

Notification business semantics are created inside Promomed. Novu, when configured, only delivers an already-authorised Promomed notification using a correlation ID. In-app delivery remains the fallback.

## Venue and analytics

MapLibre renders versioned Promomed GeoJSON. Occupancy/incidents are read from the existing command authority and are not stored by the map renderer.

Public analytics accepts only anonymous acquisition events (`page_view`, `landing_conversion`, `campaign_landing`). It does not replace Customer Intelligence, attendance, partner attribution or Owner Control Tower.

## Explicit integration gates

- Discourse/community scale — deferred;
- Moodle/full LMS — deferred;
- wger wellness routines — reference only;
- FHIR/Medplum — deferred until a formally authorised clinical use case exists;
- Umami — optional anonymous public telemetry.

## Verification

GitHub Actions verifies:

1. Python compile;
2. database compatibility contracts;
3. PostgreSQL 17 migrations and deterministic seed;
4. integration authority/RBAC/consent/webhook/transcript contracts;
5. SQLite demo fallback;
6. iPhone/static frontend contract and inline JavaScript syntax;
7. PostgreSQL backup and restore.

## Production boundary

Code-level PostgreSQL admission is implemented and CI-proven. The release is not production-admitted until the authoritative Render service receives a dedicated durable PostgreSQL `DATABASE_URL`, `/ready` returns 200 on the deployed exact SHA, and deployment evidence is recorded in `docs/DEPLOYMENT_STATE.md`.
