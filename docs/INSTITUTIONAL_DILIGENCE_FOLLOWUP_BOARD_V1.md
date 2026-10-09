# Institutional Diligence Follow-up Board v1

**Status:** implementation candidate  
**Base:** `main@75cbe93d872a93bed14f3093b79878bcb006df34`

## Purpose

Keep institutional diligence work visible between the first working session and contract without creating a hidden approval or participation authority.

## Board states

`REQUESTED -> RECEIVED -> UNDER_REVIEW -> GAP -> READY_FOR_DECISION`

Important:

`READY_FOR_DECISION != APPROVED`

The board is a read-only projection. It cannot move items manually.

## State semantics

### REQUESTED
Evidence/action is required or conditionally required, but no canonical receipt/review record exists.

### RECEIVED
Reserved for future canonical document-receipt evidence.

The v1 board cannot create this state itself.

### UNDER_REVIEW
Reserved for future canonical review-disposition evidence.

The v1 board cannot start review itself.

### GAP
Existing readiness/procurement authority already shows an unresolved requirement.

### READY_FOR_DECISION
No matching unresolved canonical gap is visible for the required item.

This means only that the item can be routed to the appropriate external/governance decision authority.

It is not approval.

## Board item fields

Each item exposes:

- title;
- category;
- owner;
- required/conditional flag;
- state;
- due class;
- whether it blocks pilot;
- next owner;
- evidence reference;
- rationale;
- manual-action capability flags.

All manual mutation flags remain false:

- `canMarkReceivedHere=false`;
- `canStartReviewHere=false`;
- `canApproveHere=false`.

## Due classes

- `urgent` — unresolved gap blocking pilot;
- `standard` — required evidence/action;
- `standard_if_applicable` — conditional security/privacy/commercial evidence;
- `optional` — non-blocking optional material.

No actual contractual due date is invented in v1.

## Truth boundary

The board:

- does not persist receipt;
- does not persist review disposition;
- does not persist approval;
- does not create contract or purchase order;
- does not create adoption/accreditation;
- does not create participation acceptance;
- does not turn demo evidence into real-pilot evidence;
- does not infer that READY FOR DECISION means approved.

External Participation Acceptance remains `GATED`.

## Commercial consequence

Promomed can now preserve the operational follow-up map after a diligence meeting: what is missing, who owns it, what blocks pilot and what is ready to be routed for a real decision.

The next authority layer for document receipt/review should only be designed after a real non-demo institution demonstrates the actual workflow and audit requirements.
