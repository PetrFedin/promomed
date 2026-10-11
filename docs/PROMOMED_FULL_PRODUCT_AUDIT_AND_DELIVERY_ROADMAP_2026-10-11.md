# СОСТОЯНИЕ × Promomed — Full Product Audit & Delivery Roadmap

**As of:** 2026-10-11. **Repository baseline:** PetrFedin/promomed main@ae5303b3d4f28d558cf4cf35b9927da88653b4ed. **Scope:** participant + editorial/evidence + conference operations + partner + institutional/commercial + production + QA + investors. **Status:** proposed executable backlog; not evidence of deployed features.

**Primary source of long-range requirements:** [Integration Master Plan](PROMOMED_INTEGRATION_MASTER_PLAN_2026-10-01.md). Existing truth documents: [Implemented Scope](IMPLEMENTED_SCOPE.md), [Deployment State](DEPLOYMENT_STATE.md), [Phase 0 admission](PHASE0_POSTGRES_ADMISSION.md), [Security pack](CORPORATE_SECURITY_PRIVACY_VENDOR_PACK_2026-10-05.md), [UI system](UI_SYSTEM_V2.md), [Investor readiness](INVESTOR_READINESS_2026-10-05.md).

## 0. Audit method, evidence, and non-claims

Evidence inspected: main GitHub tree and file contents; 25 corresponding PostgreSQL/SQLite versioned migrations; GitHub Actions main runs on 2026-10-09 (UI, persistence, responsive, live SHA PASS); Render public/admission service settings, deployments, app logs; open PR #61; independent HTTP probe. **Do not interpret CI green as production E2E or production database proof.** GitHub connector verified main latest exact SHA; Render deploy dep-db4nva7lk1mc73fd0uh0 links to it, marked live on October 9. Its app log explicitly says sqlite. The public service actual build command remains python -m py_compile server.py with no dependency install, whereas render.yaml expresses pip install -r requirements.txt and a health path; provider-side configuration differs. Admission service is running a 2026-10-06 SHA and is not production-ready evidence.

**Availability uncertainty (P0):** a separate HTTP extraction probe on 2026-10-11 returned HTTP 503 for /, /health, /ready and /institutional-commercial-workspace.html. Render currently records successful Oct 9 deploy, and searched later Render logs did not independently establish persistent 503s. **This is a single-vantage red flag to reproduce and investigate, not a confirmed permanent outage.** No independent current /health body, /ready body, real-user mobile capture or authenticated live transaction was obtained in this audit.

Render workspace ME has only one PostgreSQL instance discovered: free Frankfurt PostgreSQL 17 mfw-postgres; that instance **belongs to MFW** and must not be attached, migrated, stopped, or removed for Promomed. External Neon/free provider capacity is a candidate in the runbook, not a provisioned instance. Other provider accounts have not been exhaustively audited.

PR #61 docs-only remains open, mergeable, CI green on head b38cef285a0771e424f2b7997b6ecc21849b6db6. This document is a new independent planning change; no consent/medical/commercial approval is silently granted by it.

**Status dictionary:**
- **R** — implemented in repository; requires environment-specific QA as indicated.
- **C** — exercised in GitHub CI (local demo/PostgreSQL disposable test); not real customer traffic.
- **L** — deploy recorded live at exact SHA; not synonymous with current website uptime or durable persistence.
- **G** — gated pending external actor/authorisation/production readiness.
- **P** — planned / code or integration not demonstrated.
- **U** — unverified live end-to-end; requires source-to-UI/side-effect audit.

## 1. Product target and strict invariants

Promomed СОСТОЯНИЕ is a year-round health media, education, conference, community and partner platform plus governed evidence/institutional distribution infrastructure. It does **not** diagnose, prescribe, replace a physician, or infer patient risk from behaviour. The source of truth stays Promomed for identity, consent, content versions, evidence decisions, bookings/attendance, partner entitlements, events, institutional trust/decisions, and auditable commercial facts. Third-party search, live video, authoring, mail, mapping, training or metadata providers are replaceable adapters, **never** secondary authority. No raw clinical/sensitive health data or credentials in public demo fixtures or developer logs. Synthetic commercial success and demo institutions must never become evidence of external adoption. External Participation Acceptance, canonical contractual agreement, document receipt, review disposition and real accreditation remain **GATED** pending genuine independently attributable evidence, owner policy and legal/medical approval.

The target is a demonstrable coherent sequence: **discovery → registration → permission → event/programme → verified participation → reviewable media/knowledge → continuing learning/community → consented partner action → measurable outcome → governed evidence → institutional procurement/pilot**; each arrow has an API, authoritative record, UI status, negative test, and provenance.

## 2. Confirmed repository footprint, not production acceptance

- Participant UI: Today, Media, Events, Community, My; responsive phone bottom nav, tablet rail, monitor expanded/collapsible rail; skeletons/errors, modal keyboard focus, image attribution; 42 seeded demo event items in seven venues.
- Native domain modules: registration, bookings/waitlist, demo QR pass/check-in, attendance, speaker/incident/stream operations, Studio, learning, partner appointments/consent/lead context, reporting and investor surfaces.
- Journey365 (BEFORE / EVENT DAY / D1 / D7 / D30), explicit-signal personalisation, native faceted discovery and saved items, supervised transcript takeaways, claim-evidence graph, change-impact holds, PubMed/Crossref metadata-admission code, independent reviewer role model and immutable audit mechanics.
- Native advanced institutional code: syndication, portable verification, federated trust anchors, trust bundle, interoperability profile, review/procurement/onboarding read-only projections and commercial guidance. These are **not** evidence of institutional adoption or paid customers.
- Six separate institutional pages: commercial workspace, buyer fit, pilot proposal, outreach pack, evidence export, command center; additional read-only room views embedded in main index/Investor Proof. Page existence and CI route checks do not prove real workflow persistence.
- PostgreSQL adapter, migrations 001–025, role-based hashed sessions, account-provision tool, backup+restore test utilities, CI Postgres 17. Production PostgreSQL admission **OPEN**.
- Four vendored illustrative editorial photos, attribution manifest: not approved company-original brand media; avoid visual representations that falsely suggest depicted subjects are employees, patients, venues, or customers.

## 3. Mandatory release order / gates

| Gate | Deliverable | Dependency | Success evidence | Release permission |
|---|---|---|---|---|
| G0 — availability and truth | External GET, status-body probes, provider drift report, exact release ledger | Existing live Render + main | At least two independent viewpoints/retries, status, exact health SHA, screenshot of actual UI, variance logged | No new claims |
| G1 — durable backend | Isolated source + independent restore PostgreSQL, migrations, credentials, controlled exact SHA deployment | G0, isolated provider capacity | independent restore and matching fingerprints; production_ready=true; clean demo=0; authenticated non-demo smoke | Phase 0 COMPLETE only here |
| G2 — closed journeys | Participant, operator and partner golden paths finish on persistent state | G1 | UI+API+DB/audit evidence on phone/tablet/monitor; error and replay tests | production pilot technical candidate |
| G3 — governed medical publishing | Independent authorized editorial/science role with disclosures and exact-source corrections/retractions | G1 | two-actor decision and immutable version/hold propagation, no bypass | governed health claims |
| G4 — stable external provider adapters | Notification, video/live/replay, literature monitoring, mapping if chosen | G1–G3 | real provider sandbox -> ACK/NAK -> retry/idempotent/dlq -> UI; outages recover | selected integration goes live |
| G5 — institutional buyer pilot | Attributable non-demo organisation, authorization, actual needs, bounded scope, real session | G1–G4 relevant paths | institution-controlled identity/evidence + authorised UAT report; governance/legal decision | permit design of canonical external acceptance only if needed |
| G6 — scalable/commercial | actual measures (retention, attendance, leads, proof of service, cost), legal commercial terms | G5 and defined KPI baselines | auditable numerator/denominator/source, no invented contract/revenue | investor enterprise-ready claim by evidence, not appearance |

## 4. Canonical capability backlog

Every line is a separately auditable item. Priorities: **P0 blocks reliable pilot/product truth; P1 closes core journeys; P2 adds validated enterprise value; P3 is conditional scale/clinical expansion.** R/C can coexist with open U/G. For each item acceptance also requires negative authorization tests, rollback/failure checks and exact SHA recording when applicable.

### 0. Infrastructure, storage, identity, observability

| ID | Priority | Capability | Observed status | Depends on | Implementation / integration | Acceptance evidence |
|---|---|---|---|---|---|---|
| OPS-01 | P0 | **External availability diagnostic** | L/U | Render service + external probe | Reproduce single-client HTTP 503; compare 2 networks and cold wake, request logs, app crash/proxy/timeouts, / /health /ready and 6 institutional pages; avoid premature root-cause claim | two distinct vantage responses/status/body, logs and known explanation or tracked provider incident |
| OPS-02 | P0 | **Build/deploy config reconciliation** | R/L/U | GitHub render.yaml ↔ Render actual live service | Install pinned runtime dependencies; use /health provider healthCheckPath; reconcile public Git clone vs webhook/explicit deploy policy, exact SHA release | provider settings reflect reviewed declared config; new build and live proof green without disrupting demo |
| OPS-03 | P0 | **Release and docs truth ledger** | R/U | PR #61, deployment ledger, changelog | Review/merge docs-only PR #61 after exact-head green; classify LIVE vs DEMO vs CI vs GATED; record newest accepted SHA+deploy IDs | no contradictory current-state claims; release evidence URL per stage |
| DB-01 | P0 | **Isolated PostgreSQL source and restore** | P/G | Independent resource capacity, secret store | Provision two independent addressable PostgreSQL DBs; Never touch MFW/Antiqua/FLASHIN/Marco; provider budget/retention reviewed | separate connection targets verified; URLs stored only in secrets |
| DB-02 | P0 | **Migration and checksum admission** | R/C/G | DB-01, Postgres migrations 001–025 | Run phase0-postgres-admission with fresh DB, version/checksum and read-write-delete probe; no demo seed | all expected 25 migrations applied, no drift, zero seeded demo identities |
| DB-03 | P0 | **Backup/restoration independence** | R/C/G | DB-02, separate restore DB | pg_dump, checksum, isolated restore and independently checked catalog fingerprint; establish backup retention owner | source and restore fingerprints match; evidence IDs, reproducible runbook |
| DB-04 | P0 | **Production authentication bootstrap** | R/C/G | DB-02 | Provision non-demo operator via safe CLI secrets, test expiry/logout/rotation/revocation/least privilege | login/revoke success and wrong role/expired token denial |
| DB-05 | P0 | **Exact-head live admission** | R/C/G | OPS-02, DB-02/03/04 | Set DATABASE_URL, REQUIRE_POSTGRES true, SEED_DEMO false on admission contour; exact SHA redeploy and live smoke | /health git_commit exact SHA; /ready ready=true production_ready=true backend=postgres demo_accounts=0 |
| DB-06 | P0 | **No demo/production bleed** | R/U | DB-05 | Maintain separate credentials, URLs, fixtures, analytics and visible DEMO watermark; prohibit synthetic onboarding in prod | demo reset cannot mutate admitted DB; synthetic facts never classified real |
| SEC-01 | P0 | **Permission/tenant/consent matrix** | R/C/U | DB-04 + participant/partner actions | Test guest/participant/partner/organizer/editor/reviewer/governance/sales; deny cross-role entity reads, writes and existence leakage | 403/404 semantics and audit complete; denied actions have no side effects |
| SEC-02 | P0 | **Corporate data protection baseline** | P/G | DB-05 and documented legal owner | Document and test retention/deletion, backup lifecycle, access logging, secrets rotation, incident escalation, real DPA/SLA if required | signed internal policies and test evidence; no unsupported certification |
| SEC-03 | P1 | **Privileged step-up and passkeys** | P | DB-04, SEC-01 | Step-up for scientific publication, role change, consented lead exports, trust keys; recoverability | unauthorized action fails and recovery/audit passes |
| OBS-01 | P1 | **Operations telemetry and alerting** | P | DB-05 | OpenTelemetry/correlation IDs, redaction, endpoint & provider latency, job backlog, 5xx, p95, missing webhook receipts | dashboards + alert drill; no PII or medical text in telemetry |
| OBS-02 | P1 | **Continuity and recovery objectives** | P | DB-03, OBS-01 | Agree owner-approved RPO/RTO and restore schedule, backup expiry, audit server cold start and regional outages | measured drill with recorded RTO/RPO and incident runbook |

### 1. Interface and conference operations

| ID | Priority | Capability | Observed status | Depends on | Implementation / integration | Acceptance evidence |
|---|---|---|---|---|---|---|
| UX-01 | P0 | **Whole-site screen/action/API census** | R/U | G0 and test inventory | Enumerate every screen, button, form, drawer, deep link, role, GET/POST, DB write and notifications; click-test all visible controls | matrix action→route→API→state/event→recover; no unowned dead ends |
| UX-02 | P1 | **Unify participant & institutional navigation** | R/U | UX-01 | Connect six separate institutional pages to core index/Investor Proof with consistent role and return paths; preserve authorization | every menu/back/refresh/deep link consistent on 3 devices |
| UX-03 | P1 | **Phone/tablet/monitor visual acceptance** | R/C/U | UX-01, final brand media | Screenshot real exact SHA, 375/390+ landscape/iPad/desktop monitor; review touch targets, cropping, data density, hierarchy, modals | visual acceptance signoff; no clipping/focus trap; screenshots at original sizes |
| UX-04 | P1 | **State and failure consistency** | R/C/U | UX-01 | Every API call loading/empty/error/stale/forbidden/retry; offline or external provider outage; form preservation | error cannot masquerade as success, stale signal, accessible retry |
| UX-05 | P1 | **Authentic visual content and legal evidence** | R/U | UX-03, brand approval | Keep attributed demo photos separate; license/rights checks and official Promomed imagery for approved business materials | approval register, responsive crops, accessible captions, no false affiliation |
| UX-06 | P2 | **RU/EN editorial locale parity** | P/U | controlled vocabulary + UX-03 | Audit every UI/API/user message for actual bilingual coverage; localise content and medical disclosures only after review | no empty translations; original approved source and reviewer matched |
| EVT-01 | P1 | **Registration → pass → check-in** | R/C/U | DB-05, UX-01 | Profile, consent, registration, dedup, QR with signed/rotating token policy, staff scanner and offline boundary | one valid entry; replay/forged/expired code rejects; attendee audit event |
| EVT-02 | P1 | **My Agenda/Smart Route/overlaps** | R/C/U | EVT-01 | Programme filters, save, capacity and overlap resolution, speaker/room/time change | no incompatible simultaneous bookings; change visible + reason |
| EVT-03 | P1 | **Booking/waitlist/cancellation race** | R/C/U | EVT-02, DB-05 | Bounded inventory and waitlist promotion under concurrent writes and retries | no overbooking/duplicate allocations; idempotent notifications and cancellation ledger |
| EVT-04 | P1 | **Venue now/next + occupancy** | R/C/U | EVT-01, operational source | Verify real floor/check-in counters, threshold freshness, venue status and fallback | one authoritative count at same timestamp; stale vs real labeled |
| EVT-05 | P1 | **Operator incident and SLA closure** | R/C/U | EVT-04, OBS-01 | Create/assign/escalate/respond/resolve incident and venue alert; connect participant-facing change | persistent event history, SLA clocks, cross-role visibility test |
| EVT-06 | P1 | **Speaker/producer programme desk** | R/P | EVT-02 + editorial authority | Invitation/material deadlines/review, versioned approved agenda vs draft, moderator briefs | published agenda only approved version; changes propagate to registered attendees |
| EVT-07 | P1 | **Indoor map and accessible route** | R/P | EVT-04 and real venue geometry | MapLibre renderer only for verified layout, entrances, session/partner/step-free routes | real venue validation, keyboard/accessibility and route fallback; no invented metre distances |

### 2. Media, scientific evidence and review

| ID | Priority | Capability | Observed status | Depends on | Implementation / integration | Acceptance evidence |
|---|---|---|---|---|---|---|
| MEDIA-01 | P1 | **Controlled authoring/publishing** | R/G | DB-05, SEC-01, Science-01 | Draft→editorial→scientific→compliance/disclosure→approved→publish/version/correct/retract; choose sidecar only if justified | unapproved asset never public; immutable version + approval actor and published snapshot |
| MEDIA-02 | P1 | **Real Studio ingest/player/replay** | R/P | MEDIA-01, rights/provider | Owncast/Video.js providers conditional, event stream health, recording, transcripts, caption, speed, chapter seek | real provider sandbox plays on iOS/iPad/desktop, captions accurate and accessible, outage fallback |
| MEDIA-03 | P1 | **Transcript provider evidence** | R/G | MEDIA-02, Science-01 | Attach real STT service with source time ranges and human reviewed takeaways; privacy and retention | generated draft hidden; reviewer approves exact span; audio/rights metadata proves attribution |
| MEDIA-04 | P1 | **Replay → learning → D1/D7/D30** | R/C/U | MEDIA-02, JRN-01 | After event, prompt relevant replay and learning, save takeaway, revisit without fictitious push | verified event receipts and return route; no duplicate progress |
| MEDIA-05 | P2 | **General expert AMA room** | P/G | MEDIA-01, legal disclosure | Optional Jitsi or equivalent for educational Q&A only, moderation and privacy | not telemedicine, consent/rights and recording controls; provider fallback |
| SCI-01 | P1 | **Independent reviewer admission** | R/C/G | DB-05, SEC-01 | Credential/scope validity, conflict declaration/recusal, editor vs independent scientist vs governance actor | no self-approval/conflict bypass; independent real credential verified |
| SCI-02 | P1 | **Claim evidence/provenance public UX** | R/C/U | SCI-01, MEDIA-01 | Attach DOI/PMID locators, citations, disclosure, review time and review-until to published claims; Why Trust This on relevant cards | each public claim resolves to specific reviewed support; source change banner visible |
| SCI-03 | P1 | **Live literature monitoring worker** | R/C/G | DB-05, SCI-01, source TOS | Deploy scheduled Crossref/PubMed worker; provider API policies, limited metadata, rate limit/error/dlq | real corrected/retracted update enters admission review, no auto-promoted medical truth |
| SCI-04 | P1 | **Evidence impact and release governance** | R/C/U | SCI-02, SCI-03 | Updated source→claim/contents/replay/discovery hold→review→new version or retract→separate release | no stale claim returns to public or recommendations without authorized approval |
| SCI-05 | P2 | **Scientific terminology/coverage matrix** | P | SCI-02/03 | Controlled RU/EN topic graph, candidate NLP, claim coverage, contradiction/methodology notes, reviewer prioritization | no inferred diagnosis; accepted terms and annotated links auditable |
| SCI-06 | P2 | **Study radar and knowledge graph** | P | SCI-05 | ClinicalTrials.gov / OpenAlex registries, publications and changes as scientific *metadata* only | source provenance, freshness and conflict visibility; no clinical efficacy assertions |

### 3. Community, learning and partners

| ID | Priority | Capability | Observed status | Depends on | Implementation / integration | Acceptance evidence |
|---|---|---|---|---|---|---|
| COM-01 | P1 | **Topic discovery/save/continue** | R/C/U | DB-05, UX-01 | Search facets and status restrictions, save item and continue correctly from Today/Media/Events | saved item persists and is removed; held/retracted claim absent in recommendation |
| COM-02 | P1 | **Membership/consent/notifications** | R/P | DB-05, SEC-01 | Separate consent for notifications, community, partner followup and study; explicit revocation | revocation blocks sends,exports,access; privacy audit |
| COM-03 | P1 | **Community moderation/opt-in meet** | R/C/U | COM-02, reviewer/moderator roles | Post/report/moderate/block, mutual meeting opt-in and direct message permission | one-sided meeting can't unlock DM; toxicity/report handled and auditable |
| COM-04 | P2 | **Learning assessment/credential** | R/P/G | MEDIA-01, SCI-01 | Use native tracks, assessed learning with versioned curriculum; only verified issuer may provide external credentials | attendance/assessment trusted; badge revocation/expiry; no unsupported CME claims |
| COM-05 | P2 | **Scale search/learning/community** | P conditional | COM-01/03/04 with measured limits | Consider Meilisearch, Metarank, Discourse, Moodle only when concrete scale shortcomings appear | canonical state retained, sidecar reversible and timeouts graceful |
| PART-01 | P1 | **Real partner entitlement and appointment** | R/C/U | DB-05, EVT-03, COM-02 | Contracted placement, qualified slot and attendee appointment booking with capacity and attendance proof | partner sees only allowed records; no booking duplication; commission/attribution source |
| PART-02 | P1 | **Consented lead and commercial export** | R/C/U | PART-01, COM-02, SEC-03 | Opt-in → qualified event/partner signal → permitted followup/export/withdrawal with data lineage | export row sample matches consent, deletion and scope; unauthorized actor denied |
| PART-03 | P1 | **Notification provider real delivery** | R/P | COM-02, EVT-03, MEDIA-02 | Provider adapter for booking, waitlist, session changed, stream/replay ready, expert Q&A; idempotent outbox | sent/failed/retry/revoked/past-due tracked; opt-out honored |
| PART-04 | P2 | **Partner attribution and 1/7/30 measurement** | R/U | PART-01/02, JRN-01 | Tie campaign/event/session/appointment/followup via auditable IDs with dedup and bounded cohort counts | recompute dashboards from source records; separate real from synthetic |
| PART-05 | P2 | **Real paid value/proof ledger** | P/G | PART-04, real agreements and Finance owner | Contract entitlement, delivery evidence, invoice acceptance, actual collected payment—not scenario revenue | signed commercial terms and finance acceptance; no synthetic ARR/MRR |

### 4. Institutional, investor and acceptance

| ID | Priority | Capability | Observed status | Depends on | Implementation / integration | Acceptance evidence |
|---|---|---|---|---|---|---|
| INST-01 | P1 | **Six-page institutional navigation audit** | R/C/U | UX-02, DB-05 | Workspace→Buyer Fit→Proposal→Outreach→Evidence Export→Command Center role flow and consistent contexts | each URL loads, role/deep link error correct, export source hash verified |
| INST-02 | P1 | **Read-only onboarding/readiness/data-room/followup coherence** | R/C/U | INST-01 | Surface gaps/owners/readiness with precise state and no implied approval; form states and print/export | READY_FOR_DECISION not APPROVED; no unauthorized mutations |
| INST-03 | P1 | **Real independent first working session** | G | INST-01, G1 production truth, buyer consent | Attributable non-demo institution + authorized contact, recorded requirements with permission and smallest necessary notes | external evidence trace, customer asks, no fictitious prospect/adoption claim |
| INST-04 | P2 | **Participation authority design from observed need** | P/G | INST-03 and legal/security governance | Only after actual workflow: document receipt, review disposition, accepted pilot participation with owner, signature/evidence and revocation | two-person authority and external proof; no public claims until real acceptance |
| INST-05 | P2 | **Partner success operational portal** | P/G | INST-03 + PART-04 | Design scoped partner deliverables, compliance checkpoints, tickets, SLA, verified value, commercial review | real counterparties, verifiable partner UAT, consent boundary |
| INST-06 | P2 | **Institutional syndication protocol pilot** | R/C/G | SCI-01–04, INST-03 | Exchange approved evidence pack, signed webhook/receipt, partner trust/JWKS DID verify using institution-owned keys | retraction propagates, receipts verify offline, key revocation reflected, non-demo anchor proof |
| INST-07 | P3 conditional | **Accredited professional learning** | P/G | COM-04, real accreditor, legal | Partner issued Open Badges / professional education only after actual issuer/accreditor approved | external credit claims verified/revoked; no provider self-certification |
| INST-08 | P3 conditional | **Clinical data interoperability** | P/G | documented real healthcare use case and legal authorization | Medplum/FHIR only with actual approved healthcare partner, DPIA/privacy/security review | scoped patient record access test, controller/processor agreement; otherwise no clinical integration |
| INV-01 | P1 | **Investor reality and source-of-truth status** | R/C/U | OPS-03, DB-05 | Investor/CEO/Committee view status LIVE/CI/DEMO/GATED with exact evidence links | no synthetic counts in traction; every claim traceable and privacy-safe |
| INV-02 | P2 | **Actual KPI baselines and economics** | R/P/G | G2 real usage, PART-04, Finance acceptance | Registrations→attended→consented→qualified→repeat, D1/D7/D30, denominator and time basis, verified invoice/outcome; scenario modeling separate | reconciled source rows, defined periods, signed baselines vs targets, no invented ROI |
| INV-03 | P2 | **Procurement/security pack execution** | R/G | SEC-02, OBS-01, INST-03 | DPA, contract terms, SLA, restore proof, access logs, medical governance, vendor questionnaire resolution | acceptance by accountable buyer owners, no implied certification |
| INV-04 | P2 | **Real demonstration with role switching** | R/U | all G1–G4 prerequisites | Script 3 role tracks Participant / Operator / Partner + independent Reviewer / Buyer cases with fail states | five reproducible non-demo routes plus evidence timeline and documented unresolved gaps |

### 5. Quality and end-to-end testing

| ID | Priority | Capability | Observed status | Depends on | Implementation / integration | Acceptance evidence |
|---|---|---|---|---|---|---|
| QA-01 | P0 | **Golden-path and screen inventory** | R/U | UX-01 | Browser coverage map by persona; every visible UI action and API; permissions and database side effects | coverage matrix with failure/negative tests and actual screenshots |
| QA-02 | P1 | **Cross-backend atomicity and idempotency** | R/C/U | DB-05 | Concurrent booking, duplicate payload, cancelled/retried notification, delayed approval transaction | no double commit, transaction rollback on validation and identical outcome on retry |
| QA-03 | P1 | **Mobile real-device signoff** | R/C/U | G1, UX-03 | Physical iPhone Safari, iPadOS Safari and monitor browser; slow/free-tier and network interruption | recorded video/screenshots/input test/latency and readability/accessibility exceptions |
| QA-04 | P1 | **External failure and chaos contracts** | P | G1, provider adapters | Provider offline/retry/backoff/dead-letter, expired credentials, webhook replay, missing source metadata | clear UI stale/failure and recovery; no false success or published stale claims |
| QA-05 | P1 | **Security, performance and accessibility gates** | R/C/U | G1 and all role flows | OWASP threat model, dependency alerts, keyboard/screen reader, image/video content a11y, load scenarios and p95 from real metrics | documented defects closure and named nonfunctional release thresholds approved by pilot owner |
| QA-06 | P2 | **Pilot UAT and support runbooks** | P/G | G2–G5 | UAT by participant/event staff/editor/partner/buyer, support/on-call, incident escalation, customer feedback collection | external human acceptance, issue/retest ledger and signed go/no-go decision |

## 5. Golden-path end-to-end matrix

| Persona + scenario | UI entrypoint | API/authority source | Success and negative proof |
|---|---|---|---|
| Guest → account/registration | Today / My / Events | accounts, sessions, registration, consent | isolated non-demo login, logout/expiry, denied write for guest |
| Participant → relevant content and save | Today / Media / Search | discovery, saved items, content review | search result → saved → Continue; revoked/held claim suppressed |
| Participant → event booking and route | Events / My Day | programme, bookings, waitlist | conflict and capacity handled, identical retry, source event |
| Participant → physical check-in | QR Wallet / venue staff | signed pass, check-in, attendance | valid once, revoked/forged QR rejected, live audit |
| Participant → changed event | My Day / live venue | operational update, booking, notification | changed room visible; no phantom attendance |
| Participant → partner slot | Community / Partner | appointment, consent, partner scope | cancel, capacity conflict, partner role sees only entitled record |
| Participant → year-round return | Media / learning / My | Journey365, takeaways, community, replay | D1/D7/D30 correct for recorded event time and absence of activity |
| Participant → revoke consent | Profile / partner preferences | consent and export | revoke blocks future dispatch/export and linked access |
| Host/operator → incident response | Organizer / command strip | incident/staff/venue states | incident create→assign→close, correct role and SLA event |
| Editor → evidence publication | Content draft / editor | claim, citation, exact approved publication | unreviewed blocked; correction preserves old version |
| Independent reviewer → admission | reviewer authority | credentials, recusal, candidate snapshot, audit | conflict recusal, two-actor separation, no role escalation |
| Evidence monitor → changed source | monitoring/editor | provider metadata, queue, claim impact | 503/timeouts don't equal no change; hold/retraction propagates |
| Partner manager → consented result | Partner Cockpit / appointments | partner scope, consented lead, attribution | scoped leads and export consistent; anonymous/no-consent denied |
| Institutional lead → proposal and diligence | six institutional pages | read-only buyer-fit/pack/room authority | deep links and pack hashes, no simulated deal state |
| Real institution → formal pilot | Working Session / future intake | attributable organisation and governance only after admission | actual signed acceptance and UAT; else still GATED |
| Investor → claim verification | Investor / Committee Room | runtime, CI/deploy evidence, finance accepted metrics | exact source links, DEMO shown as DEMO, no unearned revenue |

For each golden path collect: test actor + role; starting DB fixture; exact commit/deploy; viewport/device; steps/screenshots; request/response IDs; authoritative DB row/event ID; expected denial conditions; cleanup/retry state; explicit **PASS / FAIL / BLOCKED / NOT TESTED**. A screenshot is not enough without side-effect verification; an API 200 is not enough without successful UI recovery.

## 6. Recommended dependency-driven work waves (no invented completion dates)

**Wave A — immediate, can proceed without customer and without production write risk:** OPS-01 (HTTP 503 diagnosis), OPS-02 (provider configuration reconciliation without premature production switch), OPS-03 (truth ledger), UX-01 (screen-action-API census), QA-01 (golden paths), UX-03 preliminary screenshots/visual findings on isolated preview. Each should be its own small PR or evidence artifact. No automatic main merge or production disruption.

**Wave B — G1 admission:** DB-01 source/restore provision → DB-02 migrations → DB-03 restore → DB-04 non-demo auth → DB-05 exact SHA live admission → DB-06 demo separation → SEC-01 permission negative suite. Phase 0 remains OPEN until complete proof is present.

**Wave C — daily-use closed system:** UX-02/04, EVT-01/02/03/04/05, COM-01/02/03, PART-01/02, MEDIA-04 and QA-02/03. Observe all three device types. Prioritize repairing blocked actions over new surface count.

**Wave D — scientific credibility:** SCI-01 independent reviewer admission and MEDIA-01 publisher, then SCI-02/03/04, legal/security governance; MEDIA-03 reviewed transcript provider. Prevent source metadata auto-admission.

**Wave E — real providers and end-of-event lifecycle:** MEDIA-02 video/live/replay provider, PART-03 external notifications, EVT-06 programme desk, EVT-07 venue map only after real venue evidence; instrument OBS-01/02 and QA-04/05.

**Wave F — independent commercial proof:** INST-01/02/03 real first working session, INVESTOR truth, actual partner measurement and UAT. Only observed customer evidence may trigger INST-04/05 signed participation/contract authority, invoice/value/ARR claims and expanded regulated exchange. Use real stakeholder feedback to reprioritize UX and KPI features before building further waves.

**Wave G — optional moat/scale:** SCI-05/06 knowledge graph/clinical-trial radar; COM-04 badges with accredited/non-accredited distinction; COM-05 search/LMS/community scale; INST-06 syndication/federated real pilot; INST-07 accreditation; INST-08 FHIR clinical integration only after separate legal/clinical authorization. New sidecar must have source owner, provider failure fallback, privacy/security review and data portability.

## 7. Required interface/API authority binding for any new feature

Every backlog PR must record: user role, screen IDs, primary action, request/response schema, canonical SQL entity and revision, audit event, consent/legal basis, sidecar adapter (or none), visibility on phone/iPad/monitor, loading/error/recovery, negative permission test, idempotency/dedup strategy, BI event source, data-retention regime, exact SHA browser proof and owner-approved release gate. **Do not create unlinked modules or buttons with only demo onClick behaviour.**

## 8. Release evidence package and hard-stop conditions

To mark an item DONE require the pull request with exact-head checks, production-like contract on PostgreSQL, persistent UI scenario, negative role/consent coverage, failure/retry evidence, responsive screenshot/real-device result, new migration verification if applicable, updated docs/IMPLEMENTED_SCOPE.md and docs/DEPLOYMENT_STATE.md, and post-deploy independent live response. Mark BLOCKED rather than claiming results when external database, external party, verified identity, brand rights, accreditor, regulated data basis, or real metrics are absent.

Hard stop: production_ready=false; free shared other-project DB; HTTP 503 unresolved; misleading evidence/medical claims; unapproved content; misleading investor conversion; one-sided consent; unscoped data export; synthetic institution promoted to real; expired trust anchor claimed valid; untested rollback/restore on production launch.

## 9. Source links reviewed

- https://github.com/PetrFedin/promomed/tree/ae5303b3d4f28d558cf4cf35b9927da88653b4ed
- https://github.com/PetrFedin/promomed/blob/main/docs/PROMOMED_INTEGRATION_MASTER_PLAN_2026-10-01.md
- https://github.com/PetrFedin/promomed/blob/main/docs/IMPLEMENTED_SCOPE.md
- https://github.com/PetrFedin/promomed/blob/main/docs/PHASE0_POSTGRES_ADMISSION.md
- https://github.com/PetrFedin/promomed/blob/main/docs/UI_SYSTEM_V2.md
- https://github.com/PetrFedin/promomed/blob/main/docs/INVESTOR_READINESS_2026-10-05.md
- https://github.com/PetrFedin/promomed/blob/main/docs/CORPORATE_SECURITY_PRIVACY_VENDOR_PACK_2026-10-05.md
- https://github.com/PetrFedin/promomed/pull/61
- https://github.com/PetrFedin/promomed/actions/runs/38006961611
- https://github.com/PetrFedin/promomed/actions/runs/38006961623
- https://github.com/PetrFedin/promomed/actions/runs/38006961632
- https://github.com/PetrFedin/promomed/actions/runs/38006961582

**Note:** all statuses are snapshot-specific as of audit. Decisions requiring original signed contracts, personal data, actual buyer feedback, producer consent, or staff professional credential validation must be made by an authorised human; this proposed plan does not assert they exist.
