# Implemented Scope — v2.0 Integration Candidate

> This document describes code implemented on the integration candidate. Live deployment truth remains in `docs/DEPLOYMENT_STATE.md`.

## Existing product graph preserved

- year-round health media/product/conference experience;
- 42-event programme across seven venues;
- registration/profile/programme/Smart Route/ticket/QR/booking/waitlist;
- live/replay, venue operations, incidents/SLA, staff and speaker readiness;
- attendance/check-in;
- Partner Cockpit and Appointment Desk;
- Customer Intelligence and Owner Control Tower;
- native community, subscriptions/follows and learning tracks.

## PROMO-INT-00 — durable persistence

Implemented:

- PostgreSQL 17 schema and versioned migrations;
- SQLite demo/dev compatibility adapter;
- deterministic legacy seed on PostgreSQL;
- durable database sessions and password hashes;
- durable consent and audit/business-event state;
- `/health` durability visibility and `/ready` production gate;
- backup/restore scripts and CI proof.

Production activation still requires a real durable `DATABASE_URL` on the authoritative Render service.

## PROMO-INT-01 — bounded contexts

New functionality is separated under `app/` rather than extending one monolithic route file. Existing public APIs remain compatible.

## PROMO-INT-02/03 — editorial review and evidence

- versioned publications and immutable snapshot hashes;
- editorial -> medical -> compliance -> approval/publish workflow;
- correction/retraction states;
- Directus import boundary with mandatory review chain for approved publication;
- evidence sources, citations, claim-to-evidence links and reviewer state;
- source/review surfaces in the iPhone UI.

## PROMO-INT-04/05/06 — discovery and personalisation

- rebuildable search projection across content, Studio, experts, sessions, partners, products and learning;
- Meilisearch adapter with native fallback;
- semantic-provider adapter with deterministic fallback;
- explainable personalised Continue Journey;
- Metarank adapter with allow-listed non-medical reason codes;
- recommendation impression audit.

## PROMO-INT-07/08/09 — media and expert rooms

- provider broadcast authority;
- Owncast-compatible webhook/state boundary;
- Video.js replay surface;
- replay progress;
- transcript processing jobs;
- timecoded source segments and source hashes;
- generated takeaways requiring human approval;
- Jitsi Expert Room listing/booking/consent boundary.

No clinical telemedicine semantics are implemented.

## PROMO-INT-10/11 — programme and experts

- programme proposals, speaker invitations, production checklist and approved revisions;
- pretalx approved-snapshot import;
- expert qualifications, disclosures, publications, appearances and versioned profiles;
- qualifications are never inferred automatically.

## PROMO-INT-12/13 — partner workspace and delivery

- partner contacts, commitments, deliverables, evidence and renewal lifecycle;
- separate participant consented leads;
- notification delivery records with unique correlation IDs;
- Novu delivery adapter and in-app fallback.

## PROMO-INT-14 — venue map

- versioned Promomed GeoJSON assets/POIs;
- MapLibre frontend renderer;
- live occupancy/incidents read from command authority;
- abstract demo geometry explicitly marked as illustrative.

## PROMO-INT-15/16/17 — explicit non-integrations

The following remain explicit gates rather than hidden second authorities:

- Discourse/community scale — deferred;
- Moodle/full LMS — deferred;
- wellness routine database — reference only; native challenges/actions remain canonical;
- FHIR/Medplum — deferred pending real authorised clinical use case.

## PROMO-INT-18 — public analytics

- anonymous acquisition event model;
- optional Umami forwarding;
- only page view / landing conversion / campaign landing events;
- cannot replace business/customer/attendance/partner evidence.

## iPhone surfaces

Added:

- Continue Journey with reason codes;
- integrated search;
- Sources/claim-lineage view;
- Video.js replay with chapters/transcript/reviewed takeaways;
- Expert Rooms;
- MapLibre venue map;
- Programme Production Desk;
- Expert Authority;
- Partner Workspace Authority;
- Integration Control Tower.

## CI acceptance

The integration candidate is checked against PostgreSQL 17 and includes RBAC-negative, consent, duplicate-webhook, transcript-lineage, provider-fallback, deterministic-ranking, SQLite-fallback and frontend-JavaScript contracts.

## Not claimed as live

Provider configuration is optional and currently must be evidenced from environment/runtime. This repository does not claim Directus, Meilisearch, Metarank, Owncast, Jitsi, pretalx, Novu or Umami are live merely because adapters exist.

The production release is complete only after exact-head Render deployment with durable PostgreSQL and `/ready == 200`.
