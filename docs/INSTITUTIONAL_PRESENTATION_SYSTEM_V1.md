# Institutional Presentation System v1

**Status:** implementation candidate  
**Base:** `main@308653a3c5bb020e28d378a30a998e7984bc8268`

## Purpose

Make the institutional commercial/readiness stack feel like one coherent product rather than a collection of standalone proof pages.

This layer is visual/editorial only.

## Shared shell

Applied to:

1. Institutional Commercial Workspace;
2. Buyer Fit Matrix;
3. Pilot Proposal Studio;
4. Institutional Outreach Pack;
5. Institutional Evidence Export Pack;
6. Diligence Command Center.

The shared shell provides:

- sticky institutional navigation;
- active-page state;
- route-stage cue;
- persistent planning truth cue;
- responsive horizontal navigation;
- shared visual hierarchy;
- print-safe removal of navigation.

## Product boundary

No API, table, migration, CRM object, pipeline stage, customer evidence or approval authority is introduced.

The shell communicates:

`Planning != customer truth`.

It does not change the semantics of the underlying surfaces.

## Responsive proof

Browser QA covers all six surfaces on:

- iPhone;
- tablet;
- desktop.

The contract verifies:

- navigation visibility;
- correct active state;
- truth cue visibility;
- Workspace link visibility;
- no horizontal overflow.

## Commercial consequence

A CEO, seller, procurement stakeholder or strategic partner can move through the institutional journey without losing context, while every surface preserves its own truth boundary.
