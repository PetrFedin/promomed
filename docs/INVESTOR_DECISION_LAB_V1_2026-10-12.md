# СОСТОЯНИЕ — Investor Decision Lab v1

Status: Draft PR #71, repository candidate, not published and not commercial traction.

## Investor journey

1. Product: open functioning participant/event/media surfaces, inspect live runtime truth.
2. Pilot: inspect Buyer Fit and bounded Proposal Studio. External participation and agreements remain gated.
3. Delivery: link partner obligations, consented participant actions and independent acceptance evidence.
4. Finance: compare three independently entered scenarios, break-even customer count, operating result and simple payback.
5. Capital: return to Diligence Command Center; no demo calculation authorizes investment tranches.

## Transparent scenario model

All seven inputs are entered by the investor for EACH of conservative, base and optimistic scenarios, with no default market values.

- R = C x L + E x F, where C paying organizations; L annual licence price; E annual events; F revenue per event.
- P = R x (1 - V/100) - O, where V direct cost percentage and O fixed annual operating expense.
- M = 100 x P/R where R > 0, otherwise undefined.
- Minimum customer count B = max(0, ceil((O/(1-V/100) - E*F)/L)) when finite and possible.
- Simple payback months = 12 x I/P when P > 0, otherwise not applicable; I is user-defined initial investment.

This is NOT DCF, EBITDA, FCF, a verified ROI, a forecast, contracted ARR or a valuation. Taxes, financing, working capital, churn, seasonality, growth, cash timing and accounting rules are intentionally outside this model.

Empty and invalid inputs are not silently zeroed. Scenarios are held only in browser memory and exported to a locally generated CSV; no backend POST, database migration, contract creation or capital release.

## Evidence boundaries

- Health, readiness and catalogue are read from existing GET endpoints only.
- Counts of sessions, media objects and partner packages are catalogue objects, not attendees, contracts or revenue.
- Live production readiness requires an independent exact Git SHA, dedicated PostgreSQL and restore proof; Issue #64 and #65 remain open.
- External partner acceptance, signed contract, finance recognition and repeatable renewals are NOT claimed.

## Quality and release gates

- New HTML, CSS and JS screen linked from home Investor Proof and Institutional Commercial Workspace.
- Static and read-only behavior tests added to UI quality CI.
- Before merge: exact-head CI all GREEN, functional browser proof, 375/820/1440px review, keyboard navigation and input validation.
- Before publication: Render build/health settings, exact main SHA and correct public /ready state.
- Before real investment decision: verified pilot contract, finance reconciliation, cost base, consent and formal committee decision.

Next wave: Pilot-to-Revenue Evidence Ladder: signed scope -> delivery -> accepted invoicing -> actual direct costs -> Finance acceptance -> repeatable contract renewals, gated by authoritative PostgreSQL and tenant isolation.