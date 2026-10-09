# Institutional Pilot Proposal Studio v1

**Status:** implementation candidate  
**Base:** `main@9feeb8b6e3993b7fd06969c064c6cb4683230246`

## Purpose

Turn Promomed's institutional readiness stack into a practical pre-sales proposal surface without inventing a customer, pilot, price, timeline, acceptance or revenue.

The Studio works with a **partner archetype**, not a real institution identity.

Supported archetypes:

- clinic / healthcare provider;
- university / education institution;
- medical / scientific society;
- pharma / biopharma partner;
- knowledge / content provider;
- strategic / ecosystem partner.

## Output

For each archetype the Studio composes:

- value hypothesis / business objectives;
- bounded use-case options;
- pilot scope modules;
- required customer inputs;
- stakeholder map;
- success-criteria formulas;
- procurement / security / legal prerequisites;
- commercial truth boundary;
- current product-evidence posture;
- deterministic export SHA-256.

## Scope modules

The proposed pilot can be assembled from:

1. Foundation;
2. Experience;
3. Evidence & governance;
4. Technical integration — optional / to agree.

All modules remain proposed until a real external institution agrees scope.

## Success criteria

The Studio may define measurement formulas, but target values remain:

- `to_agree`;
- `to_agree_if_in_scope`.

No synthetic KPI target is treated as accepted.

## Commercial boundary

The Studio explicitly emits:

- pricing = `TO_PRICE`;
- pilot duration = `TO_AGREE`;
- support model = `TO_AGREE`;
- SLA = `TO_AGREE_IF_REQUIRED`;
- purchase order = `NOT_CLAIMED`;
- revenue = `NOT_CLAIMED`.

## Participation boundary

External Participation Acceptance remains:

`GATED`.

A proposal cannot create:

- customer identity;
- pilot acceptance;
- contract;
- purchase order;
- revenue;
- ARR/MRR;
- accreditation;
- adoption;
- real traction.

## Technical boundary

The Studio is a read-only projection.

No table, migration, receipt, review disposition, approval or participation mutation is introduced.

Internal route:

`GET /api/institutional-pilot-proposal/<archetype>`

Allowed roles:

- organizer;
- partner;
- sales.

Responsive surface:

`/institutional-pilot-proposal.html`

## Commercial consequence

Promomed can now enter a first institutional conversation with a tailored, evidence-aware pilot structure instead of a generic product deck, while preserving the difference between:

**what Promomed proposes**  
and  
**what a real institution has actually agreed.**
