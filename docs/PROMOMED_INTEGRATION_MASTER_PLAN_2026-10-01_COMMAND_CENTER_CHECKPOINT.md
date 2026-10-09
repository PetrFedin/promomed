# PROMOMED Integration Master Plan — Command Center checkpoint

**Parent plan reviewed:** `docs/PROMOMED_INTEGRATION_MASTER_PLAN_2026-10-01.md`  
**Parent repository state:** `main@7ba7cd511a5fa3e34a518c71dc65bae36bf59117`  
**Checkpoint date:** 2026-10-09

This file is an append-only implementation checkpoint for the parent master plan. It exists because the current GitHub contents interface cannot safely append to the large parent file without replacing its full content. The parent plan was reviewed before implementation; this checkpoint records the accepted next layer without altering earlier phases.

## Institutional Diligence Command Center v1

Purpose:

turn the existing readiness, onboarding, Data Room, Working Session and Follow-up Board layers into one executive deal-readiness composition.

Flow:

`Follow-up Board -> domain blockers -> owner queue -> critical path -> parallel workstreams -> READY FOR DECISION -> Participation hard stop`.

Executive questions answered:

- what blocks pilot;
- what blocks procurement;
- what blocks legal;
- what blocks security/privacy;
- what is ready for a real decision;
- who owns the next action;
- what is on the critical path to contract;
- what can proceed in parallel;
- what is impossible until External Participation Acceptance exists.

Hard invariant:

`READY_FOR_DECISION != APPROVED`.

Implementation boundary:

- read-only projection;
- no new table or migration;
- no receipt/review/approval mutation;
- no contract or purchase-order mutation;
- no contractual due date invented;
- no accreditation, adoption, revenue, ARR/MRR or real-pilot claim;
- critical path is planning logic only;
- parallel tracks are planning logic only;
- External Participation Acceptance remains `GATED`.

Internal route:

`GET /api/institutional-command-center/<organization_id>`

Responsive executive surface:

`/institutional-command-center.html`

Deterministic evidence:

- Command Center export SHA-256;
- exact Follow-up Board export hash binding;
- exact organization identity;
- explicit runtime production-readiness field;
- CI and responsive-browser proof.

Commercial consequence:

A CEO or commercial lead can understand within one screen why the institutional deal is not moving and who must act next, without mistaking executive composition for legal, security, procurement or governance approval.

## Next dependency

After green exact-head CI, merge and live proof:

- use the Command Center with a real non-demo institution;
- capture observed decision-friction and missing evidence semantics;
- do not implement canonical receipt, review disposition, approval or participation acceptance until real-party workflow evidence exists.
