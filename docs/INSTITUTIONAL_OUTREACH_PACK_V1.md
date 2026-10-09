# Institutional Outreach Pack / First-Meeting Brief v1

**Status:** implementation candidate  
**Base:** `main@6cf1cdce7793a30990c459a12c8d9bdb77261d50`

## Purpose

Prepare a first institutional conversation using the already-proven Proposal Studio and Buyer Fit Matrix, without fabricating customer intent, meeting history, pipeline stage or pilot acceptance.

## Output

For a selected institutional archetype the pack composes:

- archetype-specific meeting framing;
- 55-minute first-meeting agenda;
- discovery questions;
- evidence to show;
- buyer-side stakeholders to invite;
- customer inputs to request;
- candidate success criteria to discuss;
- claims that must not be made;
- expected meeting outputs;
- follow-up handoff options;
- deterministic export SHA-256.

## Hard truth boundary

The pack does **not** claim:

- that a meeting occurred;
- that buyer interest exists;
- that a pipeline stage exists;
- that a next meeting is agreed;
- that a pilot exists;
- that pricing is agreed;
- that KPI targets are agreed;
- that External Participation Acceptance exists.

External Participation Acceptance remains `GATED`.

## Meeting outputs

Expected outputs are intentionally represented as:

`to_capture_in_real_meeting`

until an actual conversation produces attributable evidence.

The pack cannot convert an expected output into a fact.

## Technical boundary

The pack is a read-only projection over:

- Institutional Pilot Proposal Studio;
- Institutional Buyer Fit Matrix.

No new table, migration, CRM object, pipeline stage, receipt, approval or acceptance authority is introduced.

Internal route:

`GET /api/institutional-outreach-pack/<archetype>`

Allowed roles:

- organizer;
- partner;
- sales.

Responsive surface:

`/institutional-outreach-pack.html`

## Commercial consequence

Promomed can now prepare a first institutional meeting with a disciplined agenda and evidence sequence instead of relying on a generic deck or improvisation.

This moves the product from:

**we have an enterprise-ready architecture**

to:

**we know exactly how to conduct the first serious buyer conversation without overstating what is already proven.**
