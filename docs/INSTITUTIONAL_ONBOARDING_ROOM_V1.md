# Institutional Onboarding Room v1

**Status:** implementation candidate  
**Base:** `main@794b3a76f36aa7aa21a6a882ce8553a3da03a857`  
**Purpose:** convert institutional readiness into a first-working-session product for clinic, university, medical society, pharma, knowledge-provider and strategic-partner conversations.

## Product sequence

`Organisation Profile -> People & Authority -> Technical Qualification -> Trust & Key Setup -> Integration Readiness -> Evidence Pack -> Security / Legal / Procurement Pack -> Pilot Scope Builder -> Responsibilities / RACI -> Pilot Success Criteria -> Commercial / Procurement Handoff -> External Participation Acceptance`.

Only the final step remains intentionally:

`External Participation Acceptance = GATED`.

## Authority model

The room is a read-only orchestration layer over existing authorities.

It does not create a parallel institution, qualification, key, contract, pilot or adoption database.

Internal route:

`GET /api/institutional-onboarding-room?organization_id=...`

Allowed Promomed roles:

- governance;
- editor;
- sales.

## Procurement Evidence Pack

The room assembles a deterministic procurement evidence pack from current product authority:

- runtime / architecture posture;
- security controls;
- data inventory;
- privacy principles;
- governance/readiness;
- federation interoperability profile;
- integration requirements;
- delivery / SLA boundaries;
- vendor / legal questions;
- procurement gates;
- customer inputs required;
- explicit truth boundary.

The pack has a deterministic SHA-256 over its canonical content.

The pack is not a security certification, legal opinion, DPA, SLA, accreditation, contract or adoption claim.

## Pilot Scope Builder

The room exposes a working-session template for:

- business objective;
- institutional use case;
- users / teams;
- systems / integrations;
- data categories;
- workflows;
- pilot window;
- support model;
- explicit exclusions.

The template is not persisted as an accepted contract in v1.

## Responsibilities / RACI

Default RACI covers:

- institution identity;
- technical integration;
- security / privacy diligence;
- scope and success criteria;
- commercial / legal terms.

Named individuals and final responsibility allocation require customer confirmation.

## Success criteria

The room provides formulas only, not invented target values:

- required onboarding completion;
- mandatory conformance completion;
- portable evidence verification success;
- delivery acknowledgement success when in scope;
- material blocker closure.

Targets remain `to_agree` or `to_agree_if_in_scope`.

## Commercial handoff

The room remains in `pre_contract` state.

Before signature, the room requires:

- agreed scope and exclusions;
- agreed success criteria;
- security/privacy disposition;
- vendor/DPA position;
- SLA/support terms;
- owners/dates;
- commercial approval outside this proof layer;
- explicit external participation acceptance.

It explicitly does not claim:

- signed pilot;
- customer commitment;
- purchase order;
- revenue;
- ARR/MRR;
- accreditation.

## Truth boundary

- demo organisation remains demo-only;
- read-only projection cannot mutate authority;
- draft scope is not a contract;
- compatibility is not adoption;
- procurement evidence pack is not certification;
- success targets are not agreed until both parties approve them;
- external participation acceptance remains gated until a real non-demo participant exists.

## Commercial consequence

The project can now support a structured first institutional working session rather than showing only architecture.

The room gives both sides one shared view of:

**what exists -> what is proven -> what is missing -> who owns it -> what must be agreed -> what must happen before procurement and contract.**
