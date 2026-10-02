# Release Ledger

## 2026-10-02 — v1.8 Phase 0 Persistence Authority — REPOSITORY READY / NOT LIVE

Implemented the repository foundation required by Phase 0 of `docs/PROMOMED_INTEGRATION_MASTER_PLAN_2026-10-01.md`.

- SQLite/PostgreSQL database adapter;
- versioned/checksummed migrations;
- deterministic seed controls;
- durable hashed authentication sessions;
- liveness/readiness separation;
- PostgreSQL-only production readiness;
- backup/restore checksum utility;
- real PostgreSQL 17 migration/state/session/restore CI proof;
- responsive browser QA remains green.

This entry does **not** claim production admission. Public Render exact-SHA deployment and a dedicated durable Promomed PostgreSQL contour remain required before LIVE / `production_ready=true`.

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
