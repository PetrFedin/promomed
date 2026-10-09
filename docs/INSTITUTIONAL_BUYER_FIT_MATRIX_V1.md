# Institutional Buyer Fit Matrix v1

**Status:** implementation candidate  
**Base:** `main@d9056a86ead8405858e63a12bf1dc8a63bd41d39`

## Purpose

Compare Promomed capability match across institutional partner archetypes without fabricating demand, pipeline, win probability or revenue potential.

## Compared archetypes

- clinic / healthcare provider;
- university / education institution;
- medical / scientific society;
- pharma / biopharma partner;
- knowledge / content provider;
- strategic / ecosystem partner.

## Compared dimensions

- governed health/scientific content;
- event / programme journey;
- learning / community continuation;
- evidence / interoperability;
- partner / executive reporting;
- technical integration;
- security / procurement diligence;
- medical / scientific governance intensity.

Fit values are deliberately limited to:

- `strong`;
- `conditional`.

They do not mean:

- market demand;
- budget;
- probability of purchase;
- customer priority;
- sales stage;
- revenue potential;
- investor traction.

## Validation questions

Every archetype includes explicit real-world questions that must be answered by an actual buyer before commercial prioritization.

Examples include:

- actual buyer objective;
- allowed/prohibited data categories;
- governance owner;
- integration expectations;
- compliance / legal requirements;
- success definition;
- whether interoperability or only hosted experience is needed.

## Technical boundary

The matrix is a read-only projection over Pilot Proposal Studio outputs.

It introduces:

- no table;
- no migration;
- no CRM pipeline;
- no score;
- no probability model;
- no revenue forecast;
- no approval authority.

Internal route:

`GET /api/institutional-buyer-fit-matrix`

Allowed roles:

- organizer;
- partner;
- sales.

Responsive surface:

`/institutional-buyer-fit.html`

## Truth boundary

- planning only;
- real customer not claimed;
- real pipeline not claimed;
- real pilot not claimed;
- External Participation Acceptance remains `GATED`;
- fit means capability match only.

## Commercial consequence

Promomed can prepare different institutional conversations deliberately, understanding where the current product has a direct capability match and where real buyer validation is still required.

The matrix helps answer:

**which institutional conversation is structurally easier for the current product?**

It does not answer:

**who will buy, how much they will pay, or which prospect has the highest probability of closing.**
