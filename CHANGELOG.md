# Release Ledger

## 2026-10-01 — v2.0 Integration Authority — CANDIDATE

Integration branch: `integration/master-plan-2026-10-01`.

Implemented the approved sequence from `docs/PROMOMED_INTEGRATION_MASTER_PLAN_2026-10-01.md` without replacing working participant, event, operations, partner, community or learning authorities.

Key changes:

- PostgreSQL 17 migrations, durable DB sessions/consent/audit and production readiness gate;
- backup/restore proof in CI plus SQLite demo fallback;
- bounded integration contexts under `app/`;
- versioned editorial/medical/compliance publication authority;
- evidence/citation/claim lineage;
- rebuildable search + Meilisearch adapter + semantic fallback;
- explainable personalised Continue Journey + Metarank adapter;
- Owncast-compatible media state, Video.js replay and reviewed timecoded transcript pipeline;
- Jitsi Expert Rooms with Promomed-owned booking/consent;
- programme production + approved pretalx snapshot import;
- expert qualifications/disclosure/version authority;
- partner commitment/deliverable/evidence/renewal workspace;
- Novu delivery adapter with in-app fallback and replay-safe correlation IDs;
- MapLibre venue rendering over Promomed operational state;
- explicit deferred gates for Discourse, full LMS and FHIR;
- bounded anonymous public analytics / optional Umami forwarding;
- iPhone surfaces for the new authorities and integration proof.

Acceptance automation covers PostgreSQL migrations+seed, RBAC negative checks, consent, duplicate webhooks, transcript source lineage/human review, provider fallback, deterministic recommendation reasons, SQLite fallback, frontend contract/inline-JS syntax and PostgreSQL backup/restore.

**Not yet claimed LIVE:** production admission requires exact-head deployment to the authoritative Render service with durable PostgreSQL `DATABASE_URL` and `GET /ready == 200`. External sidecars are not claimed connected unless runtime configuration proves it.


## 2026-09-30 — v1.4 Health Media & Conference — LIVE

Authoritative repository: `PetrFedin/promomed/main`.

Expanded СОСТОЯНИЕ from an operational conference MVP into a year-round health-media and relationship platform for Promomed. Homepage now combines editorial themes, Promomed company/R&D stories, product context, health topics, partner ecosystem and conference entry points. Media gained explainers, company stories, launches, audio/video/lectorium and a curated Box boundary.

Conference programme expanded from 18 to 42 sessions across seven parallel spaces and a full 09:00–20:00 day. Existing booking, Smart Route, live/replay, partner appointments, operations, Customer Intelligence and Owner Control Tower remain connected to the same authority.

Render cutover completed to dedicated service `sostoyanie-promomed-live` built directly from `PetrFedin/promomed/main`. Verified application SHA `7315c8036050a85254d91d9504c063f09edeedb6`, deploy `dep-daug9m1srm7s73c59dk0`, status LIVE.

## 2026-09-30 — v1.3 repository consolidation

Complete Pilot Command System consolidated into the dedicated Promomed repository: participant experience, operational backend, floor/occupancy/queues, staff assignments, incidents/SLA, speaker readiness, attendance, partner appointment desk, participant alerts, stream health, Customer Intelligence and Owner Control Tower.

## Historical milestones

- v1.1 — operational pilot control room and appointment lifecycle.
- v1.2 — session attendance, waitlist promotion and partner attribution.
- v1.3 — Pilot Command System and Owner Control Tower.
- v1.4 — year-round Health Media & Conference platform; 42-event multi-track programme; dedicated Promomed Render cutover.
