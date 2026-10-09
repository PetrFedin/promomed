# Institutional Diligence Command Center v1

**Status:** implementation candidate  
**Base:** `main@7ba7cd511a5fa3e34a518c71dc65bae36bf59117`  
**Purpose:** give CEO, commercial lead and institutional programme owner a 30-second answer to why a pilot/deal is not moving and who must act next.

## Executive composition

The Command Center is a read-only composition over the existing Institutional Diligence Follow-up Board and corporate-readiness projection.

It does not create a new persistence authority.

It answers:

- what blocks the pilot;
- what blocks procurement;
- what blocks legal;
- what blocks security/privacy;
- what is `READY_FOR_DECISION`;
- who owns every blocker;
- what is on the critical path to contract;
- which workstreams can proceed in parallel;
- what remains impossible while External Participation Acceptance is absent.

## Internal route

`GET /api/institutional-command-center/<organization_id>`

The exact organization ID is path-scoped. No bulk institutional directory is exposed.

Allowed application roles:

- organizer;
- partner;
- sales.

## Executive verdicts

The projection may return:

- `HARD_STOP_PARTICIPATION_ACCEPTANCE_MISSING`;
- `BLOCKED_BY_DILIGENCE_GAPS`;
- `READY_FOR_DECISION_NOT_APPROVED`;
- `NO_ACTIVE_DEAL_EVIDENCE`.

The verdict is explanatory only. It cannot approve, reject or contractually bind either party.

## Domain views

Four deterministic domain views are composed:

1. `pilot`;
2. `procurement`;
3. `legal`;
4. `security`.

An item may appear in more than one domain when the same evidence genuinely affects multiple decision contours. This is intentional and not double-counted in the overall board item count.

Each domain exposes:

- current status;
- blocker count;
- `READY_FOR_DECISION` count;
- blocker title;
- current/next owner;
- rationale;
- whether the item blocks the pilot.

## Owner queue

The owner queue groups active blockers and decision-ready items by owner class.

It answers:

- who has the ball now;
- how many blocking items that owner carries;
- how many items are ready to route for a decision;
- which exact items belong to the owner.

Owner assignment is a planning projection. It is not acceptance of responsibility by a named person or institution.

## Critical path to contract

The v1 critical path is:

1. institution identity and authority;
2. pilot scope and technical readiness;
3. security and privacy disposition;
4. legal, DPA and SLA terms;
5. procurement and commercial handoff;
6. External Participation Acceptance.

The final stage is a hard stop.

The path is deterministic planning logic, not a contractual schedule or legal conclusion.

## Parallel workstreams

The Command Center shows three parallel tracks:

- technical and integration;
- security, privacy and legal;
- procurement and commercial.

`canProceedInParallel=true` means the work does not have to wait for another planning track to start. It does not waive a dependency or approval gate.

## READY FOR DECISION

Critical invariant:

`READY_FOR_DECISION != APPROVED`

Every item in the decision-ready list includes:

`approved=false`

The Command Center cannot:

- approve an item;
- record review disposition;
- record document receipt;
- create a contract or purchase order;
- claim revenue, ARR/MRR or adoption;
- activate a pilot;
- create accreditation or endorsement.

## Participation hard stop

Without canonical External Participation Acceptance, the product explicitly prevents claims that it can:

- record a real institutional pilot commitment;
- convert `READY_FOR_DECISION` into `APPROVED`;
- activate production pilot participation;
- claim a signed contract, purchase order, revenue or market traction;
- represent a demo organization as external adoption.

## Runtime truth

The executive summary includes the existing corporate runtime `production_ready` value.

This does not change the runtime state. If the live environment is SQLite/demo, the Command Center must display that state rather than infer production readiness from CI evidence.

## UI

Standalone responsive surface:

`/institutional-command-center.html`

The page supports:

- role-based login;
- exact organization ID selection;
- executive verdict;
- domain blocker cards;
- critical path;
- owner queue;
- parallel workstreams;
- decision-ready list;
- explicit impossible-without-participation boundary;
- deterministic export SHA-256.

The page is covered by iPhone, tablet and desktop browser QA.

## Truth boundary

- read-only;
- critical path is a projection;
- parallel tracks are planning only;
- no approval is persisted;
- `READY_FOR_DECISION` never means approved;
- External Participation Acceptance remains `GATED`;
- no contract, revenue, accreditation or real-pilot claim is created.

## Commercial consequence

The institutional stack now answers an executive question rather than merely presenting evidence:

**Why is the deal not moving, what is the shortest credible path to contract, and who owns the next action?**

The next authority layer remains blocked until a real non-demo institution demonstrates actual receipt, review, decision and participation workflows.
