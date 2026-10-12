# Stakeholder Value Exchange — role-based product experience v1

Status: IMPLEMENTED IN PR BRANCH, NOT YET LIVE VERIFIED. Date: 2026-10-12.

## Goal
Demonstrate one coherent commercial/product value story for three audiences without confusing code capability, simulated funnel, stakeholder intent, or contracted real participation.

## Flow / source of truth
- Participant: public health media -> event catalogue -> personal role-bound journey. No patient-specific inference.
- Partner: format marketplace -> existing Institutional Commercial Workspace -> protected Partner Cockpit. No fake leads or email transmission.
- Investor: Investor Proof -> Executive / CVC evidence-gated decisions -> Institutional Evidence Export.
- Landing: `/value-exchange.html` linked from public home. Individual cards route to existing sections or institutional static pages. Query-param `?screen=` accepts a small whitelist; `?presentation=` uses the existing presentation router.
- Demo catalog counts come from `/api/product-quality-proof`; live health from `/health` and `/ready`. Missing endpoint = missing evidence, never a fabricated number.
- Optional what-if partner funnel: audience * reach% -> seen; seen * opt-in% -> consenting; consenting * return% -> repeats. All four inputs required, values user-supplied and bounded; no defaults, no persistence, no commercial price or ROI claim.

## Privacy and release gates
- No new cookies, table, migrations, external calls, paid integrations, telemetry, CRM records, deals, approvals, API mutations or medical recommendations.
- Participant opt-in is a *mathematical what-if only*; no actual personal data is collected.
- Independent evidence remains required for actual demand, repeat participation, partner agreements, market traction and financial outcomes.
- Existing P0 Render configuration mismatch (#64/#68) and free isolated PostgreSQL admission (#65) are not bypassed by this page.

## Acceptance
1. `python -m unittest -v tests/test_stakeholder_value_exchange.py` included in ui-quality workflow.
2. Playwright three viewports 375x667, 820x1180, 1440x900: participant -> partner -> investor tabs; validated links; accessible keyboard navigation; funnel and missing-value behavior; runtime honest failure state; no JS page errors/overflow.
3. CI GREEN exact head on UI quality / browser / persistence; screenshot inspection.
4. Merge only after review. Verify public `/value-exchange.html` on exact live SHA after an approved deploy. Do not claim live or production-ready ahead of the evidence.

## Business hypotheses (validation required)
| Audience | Proposed use case | Metric to observe | Current evidence |
| --- | --- | --- | --- |
| Participant | Discover content then attend and return | voluntary registration -> attendance -> repeat D7/D30 | demo product features; no real adoption |
| Partner | Sponsored experience with governed consent | measured engagement -> explicit consent -> attributable follow-up | demo partner toolkit; no signed deals |
| Investor | Invest against demonstrable readiness and economics | independently validated cost of delivery, contribution, accepted pilot criteria | scenario-only analysis; no verified recurring revenue |

## Cost
Incremental cloud/provider cost target: **0 RUB**. No new resources created by this implementation; existing CI run quota and Render Free quotas remain subject to provider limits. Production expansion requires separate consent if free capacity is exhausted.
