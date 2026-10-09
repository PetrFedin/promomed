# Institutional Evidence Export Pack v1

**Status:** implementation candidate  
**Base:** `main@645a66ef69be9838cde2c842e672577d628d853a`

## Purpose

Package already-proven institutional planning artifacts into one deterministic export without creating customer, meeting, pipeline, pilot or approval truth.

## Bound source artifacts

For a selected partner archetype the pack binds:

- Institutional Buyer Fit Matrix export SHA-256;
- Institutional Pilot Proposal Studio export SHA-256;
- Institutional Outreach Pack export SHA-256;
- Commercial Workspace surface reference.

The organization-specific Diligence Command Center is listed but deliberately **not hash-bound** in an archetype-only pack.

Reason:

an archetype is not a named institution.

## Export contents

- executive summary;
- capability-match dimensions;
- proposed use cases;
- stakeholder map;
- customer inputs required;
- validation questions;
- claims not to make;
- meeting outputs expected;
- commercial boundary;
- current product evidence posture;
- artifact catalog;
- deterministic package SHA-256;
- JSON download metadata.

## Truth boundary

The export does not prove:

- a named customer;
- meeting occurrence;
- buyer interest;
- pipeline;
- pilot;
- agreed pricing;
- agreed KPI targets;
- contract;
- purchase order;
- revenue;
- External Participation Acceptance.

External Participation Acceptance remains `GATED`.

## Technical boundary

- read-only projection;
- no table or migration;
- no CRM object;
- no document receipt/review disposition;
- no approval or participation mutation.

Internal route:

`GET /api/institutional-evidence-export/<archetype>`

Responsive surface:

`/institutional-evidence-export.html`

## Commercial consequence

Promomed can hand a CEO, procurement stakeholder or strategic partner a single inspectable package showing exactly what is currently proposed and proven, with cryptographic bindings to its source projections, without turning presentation material into customer evidence.
