# СОСТОЯНИЕ × Promomed — Integration Master Plan

**Document:** `docs/PROMOMED_INTEGRATION_MASTER_PLAN_2026-10-01.md`  
**Status:** IMPLEMENTED IN CODE — integration candidate; production admission pending exact-head durable PostgreSQL deployment  
**Date:** 2026-10-01  
**Repository:** `PetrFedin/promomed`  
**Canonical branch:** `main`

## 1. Purpose

This document consolidates all Promomed / СОСТОЯНИЕ integration and product-strengthening proposals from the 2026-10-01 GitHub portfolio analysis.

A future instruction such as:

> Implement everything approved in `docs/PROMOMED_INTEGRATION_MASTER_PLAN_2026-10-01.md`

means: implement the approved items in the sequence below, preserving the existing participant/conference/operations/partner authorities and the explicit boundary between educational health content and individual medical care.

This file is a roadmap, **not a claim that the integrations already exist**.

## 2. Verified current baseline

The repository already contains:

- year-round health media/product/conference experience;
- 42-event programme across seven venues;
- registration/profile/programme/Smart Route/ticket/QR/booking/waitlist;
- live/replay state boundary;
- floor/occupancy/queues;
- staff assignments;
- incidents/SLA;
- speaker readiness;
- attendance/check-in;
- Partner Cockpit and Appointment Desk;
- consented lead boundary;
- Customer Intelligence and Owner Control Tower;
- content/product/speaker/partner catalogues;
- Studio episodes;
- community threads/posts;
- topic subscriptions and expert follows;
- learning tracks/steps/enrolments;
- replay chapters;
- appointment slots/bookings;
- notifications and audit-style events.

Current production boundary: authoritative state is still SQLite under `/tmp`. `docs/ARCHITECTURE.md` and `docs/IMPLEMENTED_SCOPE.md` already state that production admission requires durable PostgreSQL/migrations/auth/session/consent and backup/restore.

Therefore this plan must **not create more durable business authority on top of ephemeral SQLite**.

## 3. Product and safety boundaries

1. СОСТОЯНИЕ is a health-media, event, education and relationship platform; it is **not** an automated diagnostic or prescribing system.
2. Promomed content/product context must preserve disclosure and source/review boundaries.
3. External CMS/community/LMS/video/CRM systems must not silently become a second source of truth.
4. Personalisation may rank content; it must not generate individual medical treatment advice.
5. FHIR/EHR integration is deferred until there is an actual authorised healthcare-data use case and legal/compliance basis.
6. Existing demo data must never be presented as factual Promomed performance data.
7. Provider credentials and patient-like sensitive data must not be put into public/demo fixtures.

## 4. Integration disposition

Legend:

- **ADOPT** — planned for implementation.
- **ADAPT** — use external project/pattern while keeping Promomed authority.
- **SIDECAR** — separate service behind an adapter.
- **REFERENCE** — use as design/domain reference only.
- **DEFER** — do not implement until stated trigger.

| Capability | External/reference project | Decision | Boundary |
|---|---|---|---|
| Durable PostgreSQL authority | native migration | ADOPT | required before production pilot |
| SQLite replication fallback | Litestream | DEFER/CONDITIONAL | only if PostgreSQL cannot be admitted immediately |
| Structured editorial/medical review | Directus | SIDECAR/ADAPT | authoring workflow, published snapshot to Promomed |
| Editorial/membership patterns | Ghost | REFERENCE | do not run parallel CMS with Directus |
| Evidence/citation library | Zotero patterns/API | ADAPT | bibliography source; Promomed stores publication evidence refs |
| Search | Meilisearch | SIDECAR | rebuildable index, never authority |
| Semantic retrieval | sqlite-vec | CONDITIONAL | SQLite phase only; retire/replace after PostgreSQL migration |
| Personalised ranking | Metarank | SIDECAR/ADAPT | derived ranking, not user-health truth |
| Community at scale | Discourse | DEFER | current native community remains authority |
| Learning/LMS | Moodle | REFERENCE/DEFER | current native learning tracks stay canonical |
| Interactive health-learning patterns | wger | REFERENCE | borrow routine/progress UX only; no medical inference |
| FHIR interoperability | Medplum | DEFER | only with real clinical integration |
| Live Studio | Owncast | SIDECAR | media provider only |
| Replay/player | Video.js | ADOPT | playback UI |
| Virtual expert room | Jitsi Meet | SIDECAR | event/AMA, not default medical consultation |
| Meeting/transcript intelligence | ChatX internal architecture | REUSE/ADAPT | reuse evidence-first pipeline, no shared DB |
| Programme production | pretalx | ADAPT | approved snapshot imported to Promomed |
| Partner CRM workspace | Twenty patterns | ADAPT | Promomed stays source for partner/consent/event facts |
| Notification delivery | Novu | SIDECAR/ADAPT | internal notification semantics remain Promomed |
| Venue/campus mapping | MapLibre GL JS | ADAPT | renderer over Promomed venue authority |
| Public web analytics | Umami | DEFER | anonymous marketing telemetry only |

## 5. Required implementation sequence

### Phase 0 — Production persistence decision

**Preferred path: PostgreSQL.**

Before adding new production state:

1. design PostgreSQL schema for current SQLite entities;
2. create versioned migrations;
3. implement DB adapter/repository layer;
4. migrate/demo-seed deterministically;
5. preserve existing API semantics;
6. move auth/session/consent/audit state to durable storage;
7. prove backup/restore;
8. update `/health` and add readiness checks;
9. deploy exact-head and update `docs/DEPLOYMENT_STATE.md`.

#### Litestream fallback

Repository: https://github.com/benbjohnson/litestream

Use **only** if a near-term pilot must remain on SQLite temporarily.

It may replicate the SQLite file to durable object storage, but:

- it does not solve multi-instance write authority;
- it does not replace migrations/production auth;
- it must be removed or made non-authoritative once PostgreSQL is live.

Do not spend a full product wave on Litestream if PostgreSQL can be admitted directly.

---

### Phase 1 — Editorial & Medical Review Authority

Primary reference/service: https://github.com/directus/directus  
Secondary UX/reference: https://github.com/TryGhost/Ghost

The current `cms`, `content_catalog`, `product_catalog`, `speakers` and Studio entities already prove the product concept. The next step is **controlled authoring**, not a second public content database.

Target workflow:

`draft -> editorial review -> medical/scientific review -> compliance/disclosure check -> approved -> scheduled -> published -> corrected/retracted`

Recommended architecture:

`Directus authoring -> signed/versioned publication payload -> Promomed import -> public surfaces`

Promomed stores:

- publication ID/version;
- source author;
- reviewer(s);
- disclosure;
- evidence/citation refs;
- review timestamps;
- approval/retraction state;
- published snapshot hash.

**Ghost:** use its publishing/membership/newsletter UX as a reference. Do not operate Ghost as a parallel source of truth if Directus is selected. If Directus is rejected, Ghost can be reconsidered for editorial-only use, but the medical-review workflow must still be explicit.

**Acceptance:** public content always resolves to one approved version; correction/retraction never silently overwrites historical evidence.

---

### Phase 2 — Evidence & Citation Library

Reference: https://github.com/zotero/zotero

Create native entities:

- evidence_source;
- citation;
- publication;
- claim_evidence_link;
- reviewer_note;
- evidence_status.

A content/article/session/product-context claim may reference one or more sources.

Zotero may be used as:

- editorial bibliography tool;
- source metadata importer;
- DOI/ISBN/URL organiser.

Promomed remains responsible for the reviewed link between a claim and its evidence.

**Do not:** automatically claim that a publication proves a medical statement merely because a DOI exists.

UI requirements:

- "Sources" block on eligible articles/session replays;
- reviewer/disclosure status;
- correction date;
- source link/identifier where publication rights permit.

---

### Phase 3 — Search and semantic discovery

#### 3.1 Meilisearch

Use as rebuildable full-text/faceted index across:

- articles/content;
- Studio episodes;
- experts/speakers;
- sessions/replays;
- partners;
- products/product context;
- topics/learning tracks.

The index stores IDs and searchable projections. Canonical data stays in Promomed.

Required facets:

- topic;
- content kind;
- expert;
- event/session;
- partner disclosure;
- review status;
- replay/live availability.

#### 3.2 sqlite-vec

Repository: https://github.com/asg017/sqlite-vec

**Conditional only while SQLite remains the runtime.**

Use embeddings for similarity:

`article <-> session <-> expert <-> replay <-> learning step`

Do not store embeddings as source facts.

Once PostgreSQL is canonical, do not keep a second semantic authority solely because sqlite-vec was used in the pilot; migrate the retrieval layer to the chosen PostgreSQL-compatible/vector provider.

---

### Phase 4 — Personalised Home / Continue Journey

Reference: https://github.com/metarank/metarank

Signals:

- explicit interests;
- topic subscriptions;
- expert follows;
- booked/attended sessions;
- replay chapters watched;
- saved takeaways;
- content interaction;
- learning-track progress;
- partner/product interest only where consent permits.

Ranking outputs:

- content;
- sessions;
- experts;
- replays;
- learning steps.

Every recommendation must have a non-medical reason code:

- follows_expert;
- subscribed_topic;
- attended_related_session;
- continue_learning_track;
- popular_in_selected_topic.

**Forbidden:** personalised diagnostic conclusion, drug recommendation, treatment plan or health-risk classification unless a future separately regulated clinical product is explicitly created.

Fallback ranking must be deterministic if Metarank is unavailable.

---

### Phase 5 — Studio LIVE and Replay pipeline

#### 5.1 Owncast

Repository: https://github.com/owncast/owncast

Run as a separate live media service if self-hosted Studio/live sessions are required.

Promomed stores:

- Studio/session ID;
- provider broadcast ID;
- scheduled/live/ended/replay state;
- playback URL/reference;
- health summary;
- timestamps.

#### 5.2 Video.js

Repository: https://github.com/videojs/video.js

Use for public playback:

- captions;
- chapter navigation;
- playback speed;
- responsive/mobile controls;
- accessibility;
- resume position;
- replay analytics events.

Existing `replay_chapters` become the source for chapter markers.

**Order:** provider integration -> authoritative stream-state adapter -> Video.js UI -> replay chapter instrumentation.

---

### Phase 6 — Reuse ChatX Meeting Intelligence

Reuse the architecture already implemented in `PetrFedin/chat`:

`recording -> durable processing job -> timecoded transcript -> summary/takeaways -> source citations -> human review`

Do **not**:

- connect Promomed directly to ChatX database;
- copy demo transcript data;
- let AI-generated takeaways publish without editorial confirmation.

Recommended implementation:

- extract/adapt provider interface and evidence model;
- or expose a bounded internal processing API;
- store Promomed-specific transcript segments, chapters and approved takeaways under Promomed IDs.

Potential uses:

- Studio episode transcripts;
- panel/session transcripts;
- searchable replay chapters;
- editorial article draft support;
- accessibility captions.

**Acceptance:** every generated quote/takeaway can point to an exact transcript time range before publication.

---

### Phase 7 — Virtual Expert Room / AMA

Reference: https://github.com/jitsi/jitsi-meet

Use as a separate real-time video room for:

- speaker AMA;
- partner/expert office hours;
- post-event community session;
- editorial interview.

Promomed authority owns:

- room/session listing;
- eligibility;
- booking;
- participant consent;
- attendance record;
- follow-up.

Jitsi owns media transport only.

**Safety boundary:** this must not be presented as a clinical telemedicine service without a separately designed legal/medical provider contour.

---

### Phase 8 — Programme Production Desk

Reference: https://github.com/pretalx/pretalx

Public `program_items` already exist. Add the upstream production lifecycle:

`proposal/topic -> editorial acceptance -> speaker confirmation -> materials -> moderator brief -> production readiness -> approved programme revision -> public program_items`

Entities should cover:

- programme proposal;
- speaker invitation/acceptance;
- conflict/disclosure;
- deck/material deadline;
- room/format requirements;
- moderator brief;
- production checklist;
- final revision.

If pretalx is used as an external authoring tool, only approved/versioned programme snapshots are imported. Participant bookings and attendance remain Promomed authority.

---

### Phase 9 — Expert Authority

Build natively on existing `speakers`.

Add:

- qualifications/role;
- organisation;
- topics;
- publications/evidence links;
- appearances;
- disclosure/declaration of interests;
- editorial review state;
- profile version.

Do not generate qualifications from text automatically.

This expert profile becomes the linking node:

`expert -> article -> source -> session -> Studio -> replay -> Q&A`.

---

### Phase 10 — Partner CRM / Commercial Workspace

Reference UI/domain patterns: https://github.com/twentyhq/twenty

Promomed already has partners, packages, placements, appointments and consented engagement. Extend them into:

`partner -> package -> contacts -> commitments -> deliverables -> appointments -> consented leads -> evidence -> measurement -> renewal`

Twenty may be used as:

- CRM UX reference;
- optional sales-team mirror later.

It must not become the source of participant consent, attendance or event engagement.

Key distinction:

- partner commercial contact data;
- participant consented lead data;
- aggregate campaign/event measurement.

They must not be collapsed into one table.

---

### Phase 11 — Notification delivery

Reference: https://github.com/novuhq/novu

Promomed already owns the `notifications` concept. Novu may provide delivery/template orchestration for:

- booking confirmation;
- waitlist promotion;
- session move;
- live start;
- replay ready;
- expert response;
- learning continuation;
- partner appointment.

Promomed remains source for:

- why notification is allowed;
- recipient/consent state;
- business event;
- frequency policy;
- delivery correlation ID.

No provider may invent a new notification event without a Promomed business event.

---

### Phase 12 — Venue map upgrade

Reference: https://github.com/maplibre/maplibre-gl-js

Current Pilot Command System already owns venues, occupancy, incidents, staff and queues. MapLibre is only a renderer.

Use it for:

- campus/venue overview;
- entrances;
- halls;
- partner zones;
- route overlays;
- accessibility paths;
- live operational overlays where appropriate.

Indoor geometry should be versioned assets/GeoJSON controlled by Promomed.

Map state must read occupancy/incidents from Promomed command authority, not store them itself.

---

### Phase 13 — Community scale decision

Reference: https://github.com/discourse/discourse

**Do not integrate now.**

Promomed already has `community_threads`, `community_posts`, moderators, subscriptions and expert follows.

Reconsider Discourse only when one of these becomes true:

- moderation queue is operationally insufficient;
- long-running year-round community scale materially exceeds current implementation;
- trust levels, advanced moderation and federation-style forum capabilities become requirements.

If adopted later, choose a clear authority boundary; never run two writable community histories.

---

### Phase 14 — Learning/LMS decision

Reference: https://github.com/moodle/moodle

**Do not replace current learning tracks now.**

Current entities already support tracks, steps and enrolments.

Use Moodle patterns for:

- prerequisites;
- progress;
- assessments;
- completion;
- instructor/editor roles.

Only integrate a full LMS if accredited/enterprise education, complex assessment or certification becomes a contractual requirement.

Certificates must not imply medical qualification unless governed by an authorised certification process.

---

### Phase 15 — Wellness routine reference

Reference: https://github.com/wger-project/wger

**Reference only.**

Possible concepts to borrow:

- routine;
- habit/action;
- completion log;
- streak/progress display;
- user goal.

Do not import workout/nutrition prescriptions as Promomed medical content.

Existing `challenges` and `challenge_actions` should be extended if this capability is needed rather than creating a second wellness database.

---

### Phase 16 — FHIR / clinical interoperability

Reference: https://github.com/medplum/medplum

**Deferred until a real authorised clinical data use case exists.**

Trigger conditions:

- a healthcare provider/system is formally integrated;
- FHIR resources are actually required;
- data-controller/processor roles are approved;
- security/compliance architecture is defined;
- explicit user/legal basis exists.

Until then, do not add FHIR complexity to the health-media/event product.

---

### Phase 17 — Public web analytics

Reference: https://github.com/umami-software/umami

Optional for anonymous/public acquisition surfaces.

Use only for:

- landing source;
- public content page views;
- campaign landing conversions.

Do not use as a replacement for:

- Customer Intelligence;
- attendance;
- partner attribution;
- Owner Control Tower.

## 6. New/extended domain objects expected

Implementation waves are expected to add or formalise:

- publication_versions;
- editorial_reviews;
- evidence_sources;
- citations;
- claim_evidence_links;
- search projections/index events;
- recommendation impressions/reasons;
- media provider/broadcast/replay references;
- transcript segments;
- generated_takeaways + human review state;
- programme proposals/readiness;
- expert disclosures/qualifications;
- partner commitments/deliverables/evidence;
- notification deliveries;
- venue geometry/POIs.

Exact names can change, but **authority separation cannot**.

## 7. API structure recommendation

Do not continue growing one monolithic `server.py` indefinitely.

Before or during PostgreSQL migration, split internal modules by bounded context while preserving one deployable service if desired:

- `app/db/`
- `app/auth/`
- `app/programme/`
- `app/content/`
- `app/evidence/`
- `app/media/`
- `app/community/`
- `app/learning/`
- `app/partners/`
- `app/operations/`
- `app/notifications/`
- `app/analytics/`

This is a code-organisation change, not a microservice mandate.

## 8. Cross-cutting acceptance gates

Every integration wave requires:

1. durable persistence proof;
2. role/permission negative tests;
3. provider unavailable fallback;
4. duplicate/replay-safe webhook handling;
5. audit/business event link;
6. consent enforcement where participant data is used;
7. demo-data disclosure preserved;
8. medical/editorial review state preserved;
9. mobile/iPhone journey test;
10. exact Git SHA + Render deploy evidence.

For AI/transcript/search/personalisation:

11. source lineage;
12. human review where content may be published as expertise;
13. no silent conversion of inferred signals into medical facts;
14. deterministic fallback.

## 9. Explicitly prohibited architecture

Do **not**:

- run Ghost and Directus as simultaneous primary CMS authorities;
- replace native community immediately with Discourse;
- replace native learning tracks immediately with Moodle;
- use wger routines as medical recommendations;
- introduce Medplum/FHIR without a real clinical integration;
- let Jitsi become an undeclared telemedicine service;
- let Owncast/Jitsi/Directus write directly to Promomed DB;
- keep sqlite-vec as a second permanent data authority after PostgreSQL;
- share a database with ChatX to reuse Meeting Intelligence;
- let Metarank/Meilisearch generate source facts;
- let partner CRM override participant consent;
- treat Umami metrics as Owner Control Tower business evidence.

## 10. Suggested implementation issue order

1. PROMO-INT-00 PostgreSQL production authority + migrations + backup/restore.
2. PROMO-INT-01 Codebase bounded-context split during persistence migration.
3. PROMO-INT-02 Editorial/medical review workflow.
4. PROMO-INT-03 Evidence & citation library.
5. PROMO-INT-04 Full-text search.
6. PROMO-INT-05 Semantic discovery / retrieval adapter.
7. PROMO-INT-06 Personalised Home/Continue.
8. PROMO-INT-07 Studio live + replay player.
9. PROMO-INT-08 Transcript/Meeting Intelligence reuse.
10. PROMO-INT-09 Virtual Expert Room.
11. PROMO-INT-10 Programme Production Desk.
12. PROMO-INT-11 Expert Authority expansion.
13. PROMO-INT-12 Partner CRM/commitment/evidence.
14. PROMO-INT-13 Notification delivery adapter.
15. PROMO-INT-14 Venue map upgrade.
16. PROMO-INT-15 Community scale gate.
17. PROMO-INT-16 Learning/LMS scale gate.
18. PROMO-INT-17 Clinical/FHIR gate.
19. PROMO-INT-18 Optional public analytics.

## 11. Definition of complete roadmap integration

The plan is complete only when:

- durable PostgreSQL authority is live and proven;
- every **ADOPT** item is implemented or explicitly superseded with rationale;
- every **ADAPT** item has a bounded Promomed-owned domain model;
- external providers are replaceable and failure-safe;
- current product journeys remain green;
- `docs/IMPLEMENTED_SCOPE.md` reflects completed scope;
- `docs/DEPLOYMENT_STATE.md` records exact SHA/deploy evidence;
- `CHANGELOG.md` records each finished wave;
- no demo/illustrative data is misrepresented as production fact;
- educational health content remains separate from individual diagnosis/treatment.

---

**Implementation instruction:** integrate capabilities around the existing СОСТОЯНИЕ product graph; do not replace working participant, event, operations, partner or intelligence authorities with third-party products merely because those products have broader feature sets.


## 12. Implementation status — 2026-10-01

The implementation described below is present on the integration candidate. This section distinguishes **implemented code** from **live provider activation** and **production admission**.

| Phase | Code status | Production/provider status |
|---|---|---|
| 0 PostgreSQL authority | IMPLEMENTED + CI PROVEN | durable production `DATABASE_URL` still must be admitted on authoritative Render |
| 1 Editorial/medical review | IMPLEMENTED | Directus adapter present; provider is not claimed connected |
| 2 Evidence/citations | IMPLEMENTED | native Promomed authority; external Zotero use optional |
| 3 Search/semantic discovery | IMPLEMENTED | Meilisearch/semantic adapters present with deterministic fallback |
| 4 Personalised Home/Continue | IMPLEMENTED | Metarank adapter optional; deterministic reason-coded fallback active |
| 5 Studio LIVE/replay | IMPLEMENTED | Owncast boundary + Video.js UI; live provider requires configuration |
| 6 Transcript intelligence | IMPLEMENTED | Promomed-local timecoded evidence model; no ChatX DB sharing |
| 7 Virtual Expert Room | IMPLEMENTED | Jitsi transport boundary; not telemedicine |
| 8 Programme Production Desk | IMPLEMENTED | pretalx approved-snapshot adapter available |
| 9 Expert Authority | IMPLEMENTED | qualifications/disclosures require reviewed human-entered evidence |
| 10 Partner CRM workspace | IMPLEMENTED | Promomed owns consent/event facts |
| 11 Notification delivery | IMPLEMENTED | Novu optional; in-app fallback |
| 12 Venue map | IMPLEMENTED | MapLibre renderer + versioned GeoJSON/live overlays |
| 13 Community scale | GATE ENFORCED | Discourse deferred |
| 14 Learning/LMS | GATE ENFORCED | full Moodle integration deferred |
| 15 Wellness routines | REFERENCE GATE | native challenges/actions remain canonical |
| 16 FHIR/clinical | GATE ENFORCED | Medplum/FHIR deferred until authorised clinical use case |
| 17 Public analytics | IMPLEMENTED AS OPTIONAL BOUNDARY | anonymous acquisition only; Umami optional |

### Acceptance evidence in repository

The candidate CI verifies PostgreSQL 17 migrations and seed, role-negative checks, consent recording, replay-safe webhook receipts, provider-unavailable fallback, deterministic recommendation reasons, transcript source-time lineage and human review, SQLite demo fallback, iPhone frontend contract/inline JavaScript syntax, and PostgreSQL backup/restore.

### What remains before the roadmap can be called production-complete

The original definition of complete remains authoritative: merge the candidate to `main`, configure a dedicated durable PostgreSQL `DATABASE_URL` on the authoritative Render service, deploy the exact merged SHA, prove `/ready == 200`, smoke the existing journeys, and record the exact Render deploy evidence in `docs/DEPLOYMENT_STATE.md`.

External sidecars are replaceable and failure-safe. Their adapters being implemented is not evidence that a provider account or credential has been activated.
