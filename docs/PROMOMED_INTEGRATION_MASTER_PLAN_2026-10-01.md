# СОСТОЯНИЕ × Promomed — Integration Master Plan

**Document:** `docs/PROMOMED_INTEGRATION_MASTER_PLAN_2026-10-01.md`  
**Status:** IN PROGRESS — Phase 0 persistence authority implementation underway  
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

#### Implementation checkpoint — 2026-10-02

Repository implementation now includes:

- dual SQLite/PostgreSQL database adapter;
- versioned migrations with checksum-drift detection;
- PostgreSQL 17 CI contract;
- deterministic seed boundary;
- database-backed hashed sessions;
- `/ready` fail-closed admission state;
- backup/restore proof workflow.

This checkpoint is **not** production admission. Public Render was independently observed serving an older runtime without `git_commit`, and no durable Promomed PostgreSQL has yet been admitted. Phase 0 completes only after exact-SHA live deployment, PostgreSQL `DATABASE_URL`, migrations, `production_ready=true`, and restore evidence on the admitted contour.

Repository foundation was merged to `main` as `adeb0e6e9db24900af33ac96026a4029840b97b2`. Post-merge UI, responsive browser, SQLite persistence and PostgreSQL 17 migration/restore gates all passed. Exact-SHA Render proof still failed: the public service remained on `sostoyanie-v15-product-quality`. Phase 0 therefore remains **LIVE BLOCKED**, not complete.


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

#### Live admission checkpoint — 2026-10-02

Exact-main public deployment is now proven on `c87aa79d775e15ac3ea46f829732ea9d5abe92a5` by GitHub live-proof run `37025984463`. The stale-deploy problem was traced to the existing Render service operating as a Public Git clone without a functioning Git-provider webhook; explicit Render deploy API triggering is the current release path.

Durable PostgreSQL remains blocked under the current zero-cost constraint: Render's only free PostgreSQL slot is occupied by MFW, Supabase's two free project slots are occupied by Antiqua and FLASHIN, and Railway's European region is Amsterdam with trial credits rather than a permanent free Frankfurt database.

The existing Render service also retains an old build command that does not install `requirements.txt`. Therefore Phase 0 is **not complete** until a separate durable PostgreSQL is admitted and the live service build config installs `psycopg`, followed by `/ready -> production_ready=true`, live PostgreSQL smoke and restore evidence.

##### Preferred zero-cost capacity resolution — Neon

Verified 2026-10-02 from Neon public documentation:

- Neon keeps a Free plan suitable for early production/prototype workloads;
- Free supports PostgreSQL 17;
- Neon exposes AWS Europe Central 1 (Frankfurt / `eu-central-1`);
- no existing Promomed-related project must be deleted or paused to use this path.

References:

- https://neon.com/blog/new-usage-based-pricing
- https://neon.com/blog/postgres-17
- https://neon.com/demos/regional-latency

Target admission path:

`Neon Free / eu-central-1 -> DATABASE_URL -> live Render dependency/build admission -> migrations -> /ready production_ready=true -> live PostgreSQL smoke -> backup/restore evidence`

Neon remains an infrastructure provider only. Promomed retains database schema, migration, auth/session/consent and audit authority.

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

### PROMO-INT-01 implementation checkpoint — 2026-10-02

Bounded-context foundation has started while Phase 0 durable infrastructure admission remains gated:

- auth/session, shared core and demo orchestration extracted from `server.py`;
- read projections split into programme/content/community/learning/partners/operations/participant;
- `app/analytics.py` now composes those projections;
- architecture CI contract added;
- API paths and response semantics remain unchanged.

This checkpoint does **not** advance Phase 1. Command/write route extraction is the remaining PROMO-INT-01 work before calling the code-structure issue complete.

#### PROMO-INT-01 write checkpoint — wave 1

21 existing POST routes have been moved behind bounded command handlers for community, learning, participant and programme. A normalized command outcome keeps HTTP formatting and final state composition in the composition layer while domain validation/audit/consent rules live in their contexts.

`server.py` is now approximately 518 lines, down from 942 before PROMO-INT-01. Remaining command extraction: operations, partner/commercial, editor/CMS and demo control routes.

Phase 1 remains gated by Phase 0 durable PostgreSQL live admission.

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

## 12. Additional integration wave — observability, privileged identity and citation rendering

### 12.1 OpenTelemetry production observability — ADOPT

Reference: https://github.com/open-telemetry/opentelemetry-python

After the PostgreSQL/code-structure phase, trace:

`request -> auth/consent -> domain command -> DB -> provider/worker -> notification/media/search -> response`

Record release SHA, correlation ID, bounded entity IDs, provider/result and latency.

Never export medical/free-text content, raw consent payloads, authentication secrets or participant PII in spans.

Use traces to support incident response for booking, waitlist, stream, content publication, Studio processing and partner appointment flows.

### 12.2 Passkeys for privileged operators — ADOPT

Server reference: https://github.com/duo-labs/py_webauthn

Add passkeys first to:

- organiser;
- editor/medical reviewer;
- administrator;
- partner/sales roles that can access consented lead exports.

Require step-up authentication for:

- publication/retraction of reviewed content;
- role changes;
- export of consented participant data;
- partner package/lead administration;
- security configuration.

Passkeys do not change the participant profile authority.

### 12.3 Citation.js rendering layer — ADOPT/ADAPT

Reference: https://github.com/citation-js/citation-js

Use it underneath the Evidence & Citation Library to render source metadata consistently from DOI/CSL/BibTeX-style records.

Flow:

`evidence source -> normalized citation metadata -> reviewed claim link -> Citation.js presentation -> article/session/replay source block`

Citation.js formats references only. It does not decide that a paper supports a claim.

Store the normalized metadata and claim-evidence decision in Promomed; generated citation text is a derivative.

### 12.4 Operational acceptance

- trace sampling/redaction is documented;
- privileged role recovery/step-up flow is auditable;
- source formatting is deterministic and reproducible;
- a retracted/corrected evidence source propagates status to public content without erasing history.

**Sequencing:** observability follows PostgreSQL migration; passkeys follow production auth; citation rendering follows the Evidence Library schema.

## 13. Additional integration wave — scientific claims, disclosure and research evidence

This wave strengthens the platform's most important differentiator: health content that can show **who said what, on what evidence, under which disclosure and review state**.

### 13.1 Scientific Claim Registry — ADOPT

Create a native claim-level authority separate from article prose.

Entity:

- claim ID;
- normalized claim text;
- topic;
- intended audience/context;
- source publication/content version;
- evidence links;
- evidence role (supports / contextual / contradicts / insufficient);
- reviewer;
- review status;
- review date;
- validity/review-until date;
- correction/retraction state.

Flow:

`draft content -> candidate claims -> evidence link -> scientific/medical review -> approved claim version -> published content`

A citation attached to an article does not automatically mean it supports every statement in the article. The Claim Registry records the reviewed relationship.

Public UI may expose a compact "evidence" panel for claims where this materially improves trust.

### 13.2 DOI / PubMed metadata adapters — ADOPT/ADAPT

Add bounded metadata adapters for authoritative identifiers such as DOI and PMID using official Crossref and NCBI/PubMed interfaces.

Import only bibliographic metadata:

- title;
- authors;
- journal/source;
- publication date;
- DOI/PMID;
- abstract where legally/API-permitted;
- correction/retraction indicators where available;
- source URL/identifier.

Flow:

`identifier -> provider lookup -> normalized evidence source -> editorial review -> claim linkage`

Provider metadata is evidence metadata, not a medical conclusion. A successful DOI/PMID resolution must never auto-mark a claim as proven.

Cache/provider records should retain fetched_at + provider/version/source so bibliographic changes are auditable.

### 13.3 Conflict-of-Interest / Disclosure Authority — ADOPT

Extend Expert Authority with versioned declarations:

- expert;
- organisation/employment;
- advisory/consulting relationship;
- research/speaking support;
- partner/product relationship;
- declaration period;
- disclosed_at;
- reviewer/status;
- public-display text;
- superseded version.

Link disclosures to:

- expert profile;
- article;
- session;
- Studio episode;
- product-context content.

If a disclosure changes after publication, public content should resolve to the applicable disclosure version rather than silently rewriting history.

The system records disclosure facts; it does not infer impropriety from the existence of a commercial relationship.

### 13.4 Structured research / survey sidecar — CONDITIONAL SIDECAR

Reference: https://github.com/LimeSurvey/LimeSurvey

Use only for structured research where current lightweight feedback forms are insufficient, for example:

- pre/post conference research;
- health-literacy surveys;
- expert/community research;
- programme evaluation;
- sponsor-funded research with explicit disclosure.

Boundary:

`Promomed study definition + consent/eligibility -> survey provider -> response dataset -> reviewed import/aggregate -> research output`

Promomed remains source for:

- study purpose/version;
- eligibility;
- participant consent;
- linkage permissions;
- publication/disclosure status.

Do not send unnecessary profile/health context to the survey provider. Pseudonymous participant keys are preferred where linkage is required.

### 13.5 Expert Q&A moderation and publication workflow — ADOPT

Build on current expert/community entities:

`question -> moderation -> assigned expert -> draft answer -> evidence/disclosure check where needed -> approved answer -> publish -> correction/version`

Required:

- question source;
- moderator status;
- expert;
- evidence references;
- answer version;
- disclosure snapshot;
- publication status.

Q&A remains educational/general-information content. Do not turn it into individual diagnosis, prescription or treatment advice.

### 13.6 Additional acceptance

- every published reviewed claim can resolve to its evidence and reviewer state;
- DOI/PMID adapters cannot auto-promote evidence quality;
- expert disclosure is versioned and linked to the content/session context;
- research exports identify study/consent version;
- Q&A publication requires explicit moderation/review state;
- no research/survey tool becomes participant identity or health-record authority.

**Sequencing:** Claim Registry + disclosure extend the existing Evidence/Expert phases; DOI/PubMed adapters follow the Evidence Library schema; LimeSurvey remains conditional until a real structured-research need exists.

**Dependency hygiene:** before runtime adoption, pin versions and review current LICENSE/security/data-processing requirements of any sidecar. External evidence APIs and survey tools must remain replaceable.

## 14. Additional integration wave — editorial evidence annotation and evidence freshness watch

This wave strengthens scientific review without moving medical/editorial authority into an annotation product.

### 14.1 Evidence Annotation Workspace — ADAPT/SIDECAR

Reference: https://github.com/hypothesis/h

Use Hypothesis-style web annotation, or a bounded deployment of Hypothesis, for internal editorial/scientific review of:

- journal articles;
- guidelines;
- evidence-source web pages;
- PDF/text extracts where supported;
- Promomed article drafts;
- session/replay transcript segments.

An annotation should reference:

- evidence source ID/version;
- source selector or quoted region;
- reviewer;
- annotation purpose;
- visibility;
- created/updated time;
- resolution/status;
- linked claim ID where applicable.

Useful annotation purposes:

- supports claim;
- contradicts/qualifies;
- methodology concern;
- disclosure concern;
- outdated source;
- editorial note;
- needs re-review.

Annotations are review evidence and discussion. They do not themselves approve a claim for publication.

### 14.2 Evidence Freshness Watch — ADOPT

Build a durable background job over the existing DOI/PMID/evidence-source adapters.

Watch for:

- correction/erratum;
- retraction/withdrawal status where source providers expose it;
- source metadata change;
- publication replaced/superseded;
- evidence review-until date;
- broken/unresolvable source;
- material guideline/source version change.

Flow:

scheduled watch -> provider refresh -> normalized source-status delta -> affected claim/content lookup -> re-review queue -> editor/reviewer decision -> public correction/retraction if required

Never silently remove a historical source or rewrite old approved content.

### 14.3 Claim Coverage Matrix — ADOPT

For reviewed health content, provide an internal matrix:

claim -> supporting/contextual/contradicting sources -> reviewer -> disclosure state -> last reviewed -> next review due

This makes it visible when:

- a strong claim has weak/no reviewed support;
- all sources are old;
- a source was corrected/retracted;
- a disclosure changed;
- content needs re-review.

The matrix is a governance surface, not an automated medical truth score.

### 14.4 Review Queue Prioritisation — ADOPT

Prioritise re-review based on explicit product rules such as:

- source status changed;
- high-audience content;
- product-related content;
- old review date;
- expert disclosure changed;
- frequently viewed claim with weak evidence coverage.

Do not infer medical risk or individual patient risk from content popularity.

### 14.5 Additional acceptance

- every annotation resolves to an exact source/claim/version;
- annotations can be exported/reconciled if the sidecar is replaced;
- source-status changes generate review work rather than silent publication changes;
- corrected/retracted sources remain visible in history;
- public claim status changes require authorised editorial/scientific review.

**Sequencing:** Evidence Library + Claim Registry first -> annotation workspace -> scheduled evidence watch -> claim coverage/review queue.

**Dependency note:** Hypothesis remains a replaceable editorial sidecar; current license/security/privacy behavior must be reviewed before deployment with non-public evidence.

## 15. Additional integration wave — scientific entity tagging and controlled health-topic vocabulary

This wave improves discovery, evidence linking and editorial consistency. It is an NLP-assisted editorial layer, not a diagnostic or clinical inference system.

### Scientific Entity Tagging Worker — ADAPT

Candidate references:

- https://github.com/allenai/scispacy
- https://github.com/medspacy/medspacy

Use a bounded offline/worker pipeline over **approved editorial text, evidence metadata and transcripts** to generate candidate entities such as:

- condition/disease term;
- anatomy;
- procedure;
- drug/substance mention;
- organisation;
- study/publication concept;
- general biomedical topic.

Every candidate record stores:

- content/source ID;
- source text span;
- model/pipeline version;
- candidate normalized term;
- confidence/score where available;
- reviewer state;
- accepted/rejected mapping.

No candidate entity is automatically published into an expert profile, medical claim or participant profile.

### Controlled Topic Vocabulary — ADOPT

Create a Promomed-owned topic vocabulary:

- topic ID;
- RU/EN preferred label;
- synonyms;
- broader/narrower/related relationships;
- domain category;
- deprecated/replacement mapping;
- editorial status/version.

Use it consistently across:

- content;
- sessions;
- experts;
- learning tracks;
- evidence sources;
- search;
- recommendation reasons.

External NLP tools suggest mappings; the vocabulary remains human-governed.

### Evidence / Claim Entity Link — ADOPT

Allow reviewed claims/evidence to carry normalized topic/entity references.

Use cases:

- find all reviewed content concerning one topic;
- identify evidence sources connected to the same normalized concept;
- route content into re-review when a guideline/source changes;
- improve search/faceting and personalised topic continuation.

Do not imply causation or recommendation from entity co-occurrence.

### Product / Partner Mention Disclosure Check — ADOPT

If NLP detects a product/substance/company mention in an article/session transcript that also has a partner/commercial relationship, create an editorial **review flag**.

The flag means:

"check disclosure/context"

It must not assert conflict, bias or wrongdoing automatically.

### Terminology QA — ADOPT

Use the controlled vocabulary to identify:

- inconsistent RU/EN naming;
- obsolete/deprecated terms;
- ambiguous abbreviations;
- article/session tag drift;
- duplicate topic labels.

Corrections require editorial review and versioning.

### Additional acceptance

- every accepted NLP tag traces to exact content version + model version;
- model output cannot create a medical claim or participant-health fact;
- topic vocabulary is versioned and human-governed;
- deprecated terms preserve historical mappings;
- disclosure flags require human review;
- search/recommendation can rebuild from accepted topic mappings.

**Sequencing:** Evidence/Claim/Expert authorities first -> controlled vocabulary -> NLP candidate worker -> review UI -> search/recommendation integration.

**Dependency note:** scispaCy and medspaCy are actively maintained upstream as of this research wave; pin versions and benchmark on RU/EN content because model coverage/language support may differ.

## 16. Premium innovation wave — clinical-trial and evidence-development radar

This wave turns Promomed's evidence layer into a proactive editorial-intelligence product.

### Clinical Study Registry Projection — ADOPT

Primary source: official ClinicalTrials.gov programmatic interfaces.

Create reviewed study records with:

- external study ID;
- title;
- sponsor;
- conditions/topics;
- interventions;
- study type/phase;
- recruitment/status;
- locations;
- start/primary-completion/completion dates;
- results availability;
- last provider update;
- source URL;
- fetched_at;
- topic/claim mapping;
- editorial review state.

A registered or completed study is observed metadata, not evidence of efficacy or safety.

### Evidence Development Timeline — ADOPT

For selected health topics/interventions:

registered study -> status changes -> primary completion -> posted results -> publication(s) -> reviewed evidence/claim change

This lets editors see how the evidence landscape evolves over time.

### Literature Radar — ADOPT/ADAPT

Use approved APIs such as Europe PMC/PubMed-compatible services to watch:

- new publications;
- reviews/meta-analyses;
- cited/citing works;
- corrections/updates;
- topic-relevant evidence.

Every candidate enters the existing Evidence Library review queue. Nothing automatically changes a public medical claim.

### Topic Watchlist — ADOPT

Editors may watch:

- disease/topic;
- intervention/substance;
- expert field;
- partner/product-related topic;
- study;
- guideline/evidence question.

Each watch stores query/version, owner, sources, cadence, last successful check, last material delta and review state.

### Material Evidence Delta — ADOPT

Generate a structured change record:

- what changed;
- source;
- previous state;
- new state;
- potentially affected claims/content;
- review priority;
- reviewer decision.

Never generate an automatic medical recommendation.

### Editorial Intelligence Surface — ADOPT

Provide an expert/editor cockpit showing:

- active/recently completed studies;
- new results/publications;
- claims needing re-review;
- contradictory evidence;
- existing content on the topic;
- disclosure/partner context.

### Additional acceptance

- every external study/publication retains source ID and fetch time;
- trial metadata never becomes efficacy/safety conclusion;
- source changes create review work rather than silent publication edits;
- API outage/staleness is visible;
- claim/content changes require human review;
- participant-facing treatment recommendations remain outside this system.

**Sequencing:** Evidence Library + Claim Registry + controlled vocabulary -> watchlists -> study/literature adapters -> evidence timeline -> editorial cockpit.

**Source rule:** use official ClinicalTrials.gov / Europe PMC / PubMed-compatible programmatic sources rather than scraping public pages.

