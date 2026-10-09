# Institutional Accessibility & Performance Hardening v1

**Status:** implementation candidate  
**Base:** `main@21e0722a9f5d5a2655b53b97873e6fa172f4d7bd`

## Purpose

Harden the institutional commercial/readiness surfaces for keyboard access, reduced-motion users, high-contrast environments and predictable static performance without changing business semantics.

## Accessibility

Added:

- skip link to `#main-content`;
- programmatic main focus target;
- visible keyboard focus states;
- reduced-motion media handling;
- forced-colors/high-contrast handling;
- navigation accessibility regression.

## Performance

Added:

- progressive `content-visibility:auto` paint containment for major institutional regions;
- intrinsic-size fallback;
- static shared-shell size budgets;
- institutional page payload budgets;
- no-external-runtime-asset contract for institutional surfaces.

## Hard boundaries

This layer changes no:

- API;
- persistence;
- CRM/pipeline truth;
- customer evidence;
- approval authority;
- Participation Acceptance.

## QA

Automated contracts cover:

- shared shell semantics;
- skip-link keyboard lifecycle;
- reduced-motion browser mode;
- no horizontal overflow;
- all six institutional surfaces;
- CSS/JS/page static budgets.

## Commercial consequence

The institutional contour is safer to demonstrate to enterprise stakeholders and more robust across accessibility needs and constrained devices, without adding synthetic product semantics.
