# Institutional Working Session / Procurement Data Room v1

**Status:** implementation candidate  
**Base:** `main@d50937899206f09d6828daa18c23ac4728f84fb6`

## Purpose

Turn the Institutional Onboarding Room into a facilitated diligence session for a real institution without creating synthetic acceptance, commitments or traction.

## Session model

`agenda -> artifacts -> open items -> decisions to make -> handoff -> export`

The Data Room is read-only. It composes existing authorities and does not introduce a new canonical contract/meeting/adoption database.

Internal route:

`GET /api/institutional-data-room?organization_id=...`

Allowed Promomed roles:

- governance;
- editor;
- sales.

## Included artifacts

- Institutional readiness;
- Procurement Evidence Pack;
- security control evidence;
- data handling & privacy map;
- interoperability profile;
- pilot-scope working template;
- responsibilities / RACI;
- pilot success criteria;
- External Participation Acceptance placeholder.

The participation artifact remains `GATED`.

## Open items

Open items combine:

1. unresolved Institutional Pilot Readiness steps;
2. unresolved procurement/security/legal gates.

Each item exposes domain, current state, owner class and blocker/evidence requirement.

## Decisions to make

The Data Room lists decisions that a real working session may need:

- approve pilot scope and exclusions;
- approve success criteria and targets;
- security/privacy disposition;
- commercial/legal terms;
- External Participation Acceptance.

In v1 all decisions are `canResolveHere=false`.

This prevents a demo/workshop UI from becoming hidden contract or governance authority.

## Session export

A deterministic SHA-256 is computed over:

- organization identity;
- Procurement Evidence Pack SHA;
- artifacts;
- open items;
- decisions;
- agenda;
- truth boundary.

The export proves what the room displayed. It does not prove agreement by the institution.

## Truth boundary

The room:

- does not persist meeting notes;
- does not persist decision acceptance;
- does not create a contract or purchase order;
- does not create revenue or ARR/MRR;
- does not create accreditation;
- does not activate External Participation Acceptance;
- does not claim a real pilot from a demo organization.

## Commercial consequence

A Promomed seller, executive or product owner can now run a structured institutional diligence session with one common evidence surface instead of sharing disconnected technical documents.

The next product learning should come from a real working session. Only then should the project decide which notes/approvals require a new canonical authority.
