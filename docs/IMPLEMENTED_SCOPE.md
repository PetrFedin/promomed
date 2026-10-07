# Implemented Scope — through v1.4

## Year-round home & media
Editorial lead; Promomed Today; company/R&D stories; educational product context; health topics; explainers; healthy launches; audio/video/FM; lectorium; curated Box concept; partner ecosystem; 1/7/30 continuation.

## Conference
42 events, seven parallel venues, 09:00–20:00. Keynotes, lectures, debates, panels, roundtables, workshops, practices, appointments, networking, community, partner showcase and B2B salon. Timetable/grid, detail pages, My Schedule, Smart Route conflict resolution, live/replay and venue concierge.

## Experience
Registration, profile, programme, bookings, waitlist, ticket/QR, partner appointments, post-event journey and role-based surfaces.

## Operations
Pilot Command System: floor map, occupancy, queues, venue status, staff assignments, incidents/SLA, speaker readiness, session attendance, stream health and operational participant alerts.

## Partner & commercial
Partner cockpit; contracted/engagement surfaces; appointment desk; consented leads; content/event/attendance signals and partner attribution.

## Intelligence
Customer Intelligence, retention D1/D7/D30, track/partner signals and Owner Control Tower.

## Current live
`PetrFedin/promomed/main` → Render `sostoyanie-promomed-live`.
See `docs/DEPLOYMENT_STATE.md`.

## Production boundaries
Durable PostgreSQL/migrations; production auth/session/consent; real push; signed QR/Wallet; streaming provider; analytics governance; legal/medical review workflow and backup/restore.


## Persistence admission layer — repository scope

Implemented in code, pending production infrastructure admission:

- database adapter for SQLite/PostgreSQL;
- versioned/checksummed migrations;
- durable hashed sessions;
- liveness vs readiness split;
- deterministic seed controls;
- backup/restore utility;
- SQLite and PostgreSQL CI authority tests.

Not yet claimed: public Render exact-SHA deployment or admitted production PostgreSQL.


## Bounded-context foundation — PROMO-INT-01

Implemented in repository:

- authentication/session logic extracted from the HTTP monolith;
- shared audit/notification/state primitives extracted;
- demo orchestration isolated;
- programme, content, community, learning, partner, operations and participant read projections separated;
- analytics now composes projections instead of owning all domain SQL;
- architecture contract prevents extracted functions from silently returning to `server.py`.

The service is still a single deployable application. Write/command route extraction remains incremental work and is not claimed complete.


## Command boundary wave 1 — PROMO-INT-01

Extracted 21 existing POST routes from `server.py` into bounded command handlers for community, learning, participant and programme contexts. HTTP and API semantics remain unchanged.

New CI coverage checks:

- command modules exist and compile;
- extracted routes cannot silently return to the HTTP monolith;
- consent/role negative tests for representative commands;
- existing responsive/browser and PostgreSQL contracts remain mandatory.

Remaining PROMO-INT-01 work: operations, partner/commercial, editor/CMS and demo write-route extraction.


## Command boundary wave 2 — PROMO-INT-01 complete in repository

Extracted the remaining operations, partner/commercial, editorial-demo and demo-control POST routes from `server.py`.

Repository state now has:

- bounded read projections by domain;
- bounded write handlers by domain;
- normalized command outcomes;
- centralized auth/transaction/HTTP composition;
- architecture regression gates;
- representative role, permission and consent negative tests.

`server.py` is ~379 lines versus 942 before PROMO-INT-01.

This is repository completion only. Durable PostgreSQL live admission remains required before Phase 1.


## Phase 0 admission authority — repository scope

Added:

- durable account table migration for SQLite/PostgreSQL;
- salted scrypt password authority;
- database-backed login role/name/status;
- demo identities seeded only in demo mode;
- production readiness rejects demo seed and demo accounts;
- clean PostgreSQL admission probe;
- privacy-safe source/restore catalog fingerprint;
- provider-neutral manual admission workflow;
- clean PostgreSQL 17 admission + backup/restore proof in PR CI.

External durable PostgreSQL is still required before Phase 0 can be marked COMPLETE.


## Production identity bootstrap — Phase 0

Repository scope now includes `ops/provision_account.py` for deliberately creating or rotating non-demo accounts on an admitted PostgreSQL authority.

Guards:

- PostgreSQL-only;
- production readiness required before account write;
- demo seed must be off;
- `@demo.ru` identities rejected;
- salted scrypt password hash;
- no password CLI argument;
- explicit `--rotate` required for replacement;
- rotation revokes existing sessions.

PostgreSQL 17 CI proves create/login/session/rotate/revocation and demo-identity rejection before backup/restore.


## Live admission proof authority — Phase 0

Added two complementary release gates:

- public live proof requires exact SHA and refuses a SQLite runtime that claims production readiness;
- dedicated manual PostgreSQL proof targets the Render admission service and requires durable PostgreSQL, clean migrations, demo seed off, zero demo accounts and `production_ready=true`.

This closes repository-side live verification for PROMO-INT-00. External durable PostgreSQL resource admission remains outstanding.


## Investor readiness layer — 2026-10-05

Added an evidence-labelled investor surface without opening Phase 1.

Repository/runtime scope:

- bounded `app/investor.py` projection;
- role-limited `/api/investor-proof`;
- LIVE / CI-PROVEN / DEMO / GATED status taxonomy;
- runtime truth: backend, durability, production readiness, demo/non-demo identities;
- product evidence counts;
- revenue architecture without asserted pricing;
- defensibility map;
- infrastructure blocker projection;
- transparent user-input-only Scenario Economics Lab;
- investor objections / due-diligence narrative in `docs/INVESTOR_READINESS_2026-10-05.md`.

The investor layer explicitly distinguishes executable demo mechanics from production authority and future governed modules.

No revenue forecast, valuation, market share or medical outcome is claimed.


## Investment Committee Room — 2026-10-05

Investor Readiness was extended from a pitch surface into a diligence-oriented committee view:

- one consolidated assumption-only Scenario Economics Lab;
- annual revenue, contribution, margin, payback and revenue-line concentration calculations;
- server-owned diligence domains for product, architecture, durability, commercial execution, traction, economics and medical governance;
- explicit risk register with blocker / gated / unproven / measure / demo-proven states;
- strategic scale paths with DEMO vs GATED status;
- committee state that distinguishes current evidence from claims not yet proven.

The current demo runtime is explicitly `pilot_diligence_ready`, not production-medical-ready and not market-traction-proven.

Phase 1 remains gated behind Phase 0 COMPLETE.


## Executive / CVC Decision Room — 2026-10-05

Added a separate corporate decision surface above Investor Proof.

Repository/runtime scope:

- bounded `app/executive.py` projection;
- role-limited `/api/executive-room`;
- four audience lenses: CEO, CVC / Investment Committee, Strategic Partner, Procurement / Security;
- current decision state is fail-closed to `CONTROLLED PILOT ONLY` while Phase 0 is incomplete;
- milestone funding tranches use evidence gates without hard-coded funding amounts;
- pilot contract defines in-scope, out-of-scope, client inputs and GO / ITERATE / STOP exit decision;
- KPI dictionary stores formula + source before target;
- corporate-readiness matrix separates CI-proven, demo and gated controls;
- strategic-partner value exchange explicitly excludes sensitive health-data access, silent contact export and editorial/medical control;
- Data Room index links current evidence and marks missing corporate packs as to-prepare/gated;
- Board Memo can be copied from the UI and the room is print/PDF friendly;
- truth boundary explicitly prevents claims of market traction, validated unit economics or production medical governance.

Specification: `docs/EXECUTIVE_CVC_ROOM_2026-10-05.md`.

Phase 1 remains gated behind Phase 0 COMPLETE.


## Corporate Security / Privacy / Vendor Due Diligence — 2026-10-05

Added a separate corporate diligence layer without claiming certification or production approval:

- bounded `app/corporate.py` projection;
- role-limited `/api/corporate-readiness`;
- evidence-backed control matrix for identity, sessions, authorization, consent, migration integrity, backup/restore and fail-closed release readiness;
- explicit `TO PREPARE` controls for incident response, RTO/RPO, DPA/SLA, encryption evidence, SBOM/CVE scanning, retention/deletion and centralized SIEM;
- data inventory with production retention deliberately left `to_define`;
- privacy-boundary view;
- vendor questionnaire with current answer states;
- procurement gates;
- NIST CSF 2.0 / OWASP ASVS 5.0.0 reference crosswalk, explicitly not a compliance/certification claim;
- mobile/desktop Corporate Security / Procurement Room;
- Security Memo copy surface and print/PDF-friendly layout;
- hardened live Render proof with manual dispatch, longer provider-handoff window and explicit `DEPLOY_HANDOFF_TIMEOUT`.

Diligence pack: `docs/CORPORATE_SECURITY_PRIVACY_VENDOR_PACK_2026-10-05.md`.

Security/privacy approval itself remains open. Phase 1 remains gated behind Phase 0 COMPLETE.


## Personalised Home / Continue Journey — Phase 4 repository checkpoint

Added an explainable participant-facing continuation layer using existing Promomed authority only.

Repository/runtime scope:

- bounded `app/personalization.py` projection;
- deterministic ranking from explicit profile interests, topic subscriptions, expert follows, bookings, attendance and active learning progress;
- participant Home surface with up to six next-best actions;
- reason codes including `continue_learning_track`, `subscribed_topic`, `follows_expert`, `attended_related_session`, `booked_related_session` and `profile_interest`;
- direct continuation into content, expert, event, replay, Studio or community surfaces;
- deterministic fallback when richer behavioural signals do not exist;
- explicit `medical_inference=false` boundary and forbidden outputs for diagnosis, treatment recommendation, drug recommendation and individual health-risk scoring;
- responsive-browser and unit contracts for recommendation determinism and explainability.

This is the native deterministic fallback required by the integration master plan. Metarank is not yet integrated and is not required for the current MVP. Personalisation remains a derived ranking layer and does not become a health-data or medical authority.


## Relationship 365 — participant lifecycle checkpoint

Added a derived participant lifecycle over existing Promomed authority:

`BEFORE -> EVENT DAY -> D1 -> D7 -> D30`.

The projection uses explicit participant state only: profile/topic/follow signals, bookings, attendance, takeaways, replay continuation, learning progress, community activity and follow-up records.

The Home surface shows:

- current lifecycle stage;
- completed/upcoming stages;
- overall progress;
- one concrete next action;
- direct continuation into event, replay, content, expert, Studio, community or learning surfaces.

Boundary: this is a behavioural relationship journey for year-round product retention. It is not a clinical patient journey and does not infer diagnosis, treatment or individual medical risk.


## Discovery & Search Authority — Phase 3 repository checkpoint

Added a native, rebuildable discovery layer over existing Promomed canonical tables.

Search surface now spans:

- editorial/content catalogue;
- experts/speakers;
- programme events;
- Studio episodes;
- replay projections;
- learning tracks;
- derived topics;
- partners;
- product context.

Supported facets:

- kind;
- topic;
- content type;
- expert;
- event;
- replay availability;
- review status.

The native engine provides deterministic explainable scoring and exposes why a result matched. It does not become a second source of truth.

Participant feedback loop:

`Search -> Open -> Save -> Continue Journey -> Relationship 365`.

Saved discovery items are persisted under `discovery_saves`, become an explicit `saved_for_later` signal in Personalised Continue Journey, and count as route-building activity in the BEFORE stage of Relationship 365.

Meilisearch remains an optional future sidecar for scale/performance. The MVP does not require it to prove the search contract. Any future external index must remain rebuildable from Promomed authority.

Medical boundary: search/ranking performs no diagnosis, treatment recommendation, drug recommendation or individual health-risk inference.


## Transcript Intelligence — evidence-first media checkpoint

Added a bounded evidence model for Studio/replay intelligence:

`recording/replay -> timecoded transcript segment -> generated takeaway -> human review -> public takeaway`.

Repository/runtime scope:

- `transcript_segments` with exact start/end time ranges, speaker reference and review state;
- `generated_takeaways` with exact source range, reviewer identity and publication status;
- participant-facing Transcript Intelligence in Studio;
- editor-only approval/rejection command;
- participant API hides unreviewed/generated takeaways;
- Discovery indexes reviewed transcript segments and approved takeaways only;
- search results can navigate back to the source replay;
- Golden Demo reset restores deterministic transcript evidence.

Publication rule: a takeaway is public only after human review and must resolve to an exact transcript time range.

This checkpoint does not claim automated transcription provider integration, production speech-to-text accuracy or automatic medical publication. AI-generated text remains draft evidence until reviewed.


## Claim Evidence Graph — evidence-addressable knowledge checkpoint

Added a machine-checkable trust layer over editorial content:

`article claim -> citation -> source -> reviewer -> transcript/expert/event/replay -> version history`.

Repository/runtime scope:

- `evidence_sources` for typed source records and disclosure;
- `evidence_claims` for claim text, artifact binding, reviewer, status and immutable version lineage;
- `evidence_citations` for exact source locators and support relation;
- `evidence_links` for graph edges to transcript segments, experts, events and replay ranges;
- derived trust status with fail-closed checks for reviewer, active source, exact locator and graph trace;
- article-level `Why trust this?` UI;
- explicit `SUPERSEDED` and `RETRACTED` lifecycle states;
- editor correction creates a new version without erasing the previous claim;
- editor retraction preserves the record and removes trusted status;
- Golden Demo reset/reseed keeps evidence history reproducible.

Current MVP sources are explicitly DEMO records. The graph proves workflow and machine-checkability; it does not claim that demo sources are externally verified scientific publications. Production admission requires replacing demo evidence sources with verified source metadata and accepted editorial/medical review.


## Knowledge Change Impact Engine — living knowledge checkpoint

Added a fail-closed change-propagation layer over the Claim Evidence Graph.

Core flow:

`source change event -> impacted claims -> downstream knowledge traversal -> severity/SLA -> review case -> publication hold -> remediation -> authorized hold release`.

Supported demo source-change types:

- source updated;
- source corrected;
- source retracted;
- new systematic review;
- medical status changed;
- editorial status changed.

Downstream traversal currently reaches:

- article/content claims;
- transcript segments;
- experts;
- events;
- replay;
- Studio episodes;
- reviewed takeaways;
- learning tracks;
- product context;
- partner context;
- participant recommendation topics.

Fail-closed controls:

- changed/retracted source loses active trust status until re-reviewed;
- high/critical changes automatically place publication holds on affected public-facing assets;
- held assets are suppressed from personalised recommendations;
- held learning tracks reject enroll/progress actions;
- Discovery and content/product/partner UI expose UNDER REVIEW state;
- review alone cannot release a hold;
- release is permitted only after every impacted claim is either trusted again or explicitly superseded/retracted;
- hold release remains an authorized editor/governance action.

The demo intentionally supports a complete recovery path:

`source retracted -> impact queue -> hold -> affected claim retracted/remediated -> review -> release`.

External literature surveillance is not yet connected. Change events are explicit demo inputs until a production monitoring/provider layer is admitted.


## External Evidence Monitoring & Source Admission — Phase 2.5 checkpoint

Implemented the native admission layer specified in the Integration Master Plan.

Flow:

`PubMed/Crossref metadata -> canonical DOI/PMID identity -> normalized snapshot -> SHA-256 -> diff classification -> admission candidate -> editorial review -> scientific review -> governed admission -> Evidence Graph / Change Impact`.

Repository/runtime scope:

- `evidence_watch_targets`;
- `evidence_provider_snapshots`;
- `evidence_admission_candidates`;
- `evidence_admission_reviews`;
- `evidence_provider_errors`;
- canonical DOI and PMID normalization;
- provider-specific normalization for Crossref and PubMed JSON;
- deterministic snapshot hashing and duplicate suppression;
- change classification: `new_source`, `source_updated`, `source_corrected`, `source_retracted`;
- separate editorial/scientific review states;
- admission blocked until both review gates accept;
- admitted source metadata stored in native `evidence_sources`;
- admitted correction/retraction may invoke the existing Change Impact Engine;
- changed evidence invalidates connected current claims into review-required state;
- provider failure is persisted as an error record rather than treated as “no change”;
- Golden Demo contains a deterministic Crossref-style baseline source linked to CL01 and a demo retraction snapshot;
- optional explicit live provider adapter exists for Crossref REST / PubMed ESummary, but continuous polling is not claimed.

Truth boundary:

- the current external source workflow is an executable MVP admission mechanic;
- the scientific review button is a demo review role, not proof of an independent medical reviewer;
- continuous external surveillance is not running;
- provider metadata is never automatically converted into medical truth or rewritten claims;
- durable polling schedule state, exponential retry/backoff, dead-letter jobs and self-healing recovery of missing jobs for pre-existing active watch targets are implemented in repository scope;
- an external production scheduler/worker deployment, provider credentials/rate-limit policy and independent reviewer authorization remain open hardening work.


## Independent Medical / Scientific Reviewer Authority — Phase 2.6 repository checkpoint

Added a governed authority chain above External Evidence Admission:

`editorial review -> assigned reviewer -> credential/scope check -> conflict disclosure -> scientific decision -> immutable digest/audit -> separate governance admission`.

Repository/runtime scope:

- dedicated `reviewer` and `governance` account roles;
- reviewer profiles with credential state, issuer/reference, validity and independence attestation;
- authorized expertise scopes;
- editorial acceptance required before scientific assignment;
- explicit reviewer assignment per evidence candidate;
- request-changes review iteration reopens the candidate without allowing conflict-history bypass;
- mandatory conflict disclosure, automatic recusal on material conflict, conflict hold on potential conflict, and same-candidate reassignment block for the conflicted reviewer;
- production scientific review blocked from the editor shortcut;
- scientific decisions bound to the exact provider snapshot SHA-256;
- authenticated-session decision digest and rationale;
- database triggers preventing update/delete of decisions and authority events;
- tamper-evident previous-hash event chain;
- final production admission restricted to a separate governance actor;
- failed command outcomes roll back transactionally, preventing partial governance mutations from committing behind a 4xx response;
- DB-level reviewer authority state constraints and relational references reject invalid credential/assignment/conflict/decision states;
- PostgreSQL migration executor preserves dollar-quoted function bodies required by immutable audit triggers;
- reviewer/governance projection and CI contract tests;
- production reviewer attestation CLI requiring PostgreSQL production readiness.

Truth boundary:

- the authority mechanism is executable repository code;
- demo reviewer profile is explicitly `demo_attested` and is not independent credential verification;
- external professional credential registry verification is not yet integrated;
- the SHA-256 decision digest is not represented as a legal electronic signature;
- production institutional reviewer onboarding and signing policy remain required before claiming independent medical governance in production.
