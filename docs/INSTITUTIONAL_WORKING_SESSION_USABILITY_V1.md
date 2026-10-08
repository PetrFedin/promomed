# Institutional Working Session Usability v1

**Status:** implementation candidate  
**Base:** `main@27dd76cd00836f8cac1edc9250d32654f248bf81`

## Purpose

Make the Procurement Data Room usable in a real first institutional working session without turning the room into approval, contract or adoption authority.

## Added working-session structure

- participant-role map;
- document request checklist;
- due-diligence question routing;
- evidence-gap ownership;
- ordered working-session agenda;
- deterministic working-session export.

Internal route:

`GET /api/institutional-working-session?organization_id=...`

Allowed roles:

- governance;
- editor;
- sales.

## Participant roles

The room distinguishes:

- Promomed facilitator;
- institution business owner;
- institution technical owner;
- Security / Privacy / Legal;
- Procurement / Commercial;
- Medical / Editorial governance when applicable.

All roles expose `canApprove=false` in v1.

## Document request checklist

Requests cover:

- institution identity;
- accountable administrator;
- integration map;
- security/vendor questionnaire when applicable;
- intended data categories;
- SLA/support expectations when applicable;
- proposed success criteria and targets;
- procurement/commercial process;
- External Participation Acceptance evidence.

The final participation request remains `GATED`.

## Due-diligence question routing

Each common diligence question is routed to the appropriate role and names the evidence needed to close it.

Question routing does not persist answers or imply acceptance.

## Evidence-gap ownership

Open Data Room items receive an owner class so the meeting can end with a clear follow-up map.

Ownership does not mean resolution. Every gap remains:

`resolutionCanBeAcceptedHere=false`.

## Truth boundary

The working-session layer:

- is read-only;
- does not persist document receipt;
- does not persist answers;
- does not persist owner acceptance;
- does not persist approvals;
- does not create contract or revenue;
- does not create adoption/accreditation;
- keeps External Participation Acceptance gated;
- cannot convert a demo institution into a real pilot.

## Commercial consequence

The product now supports a practical first diligence session: who must attend, what must be provided, who answers each question, which gaps remain and who owns the next action.
