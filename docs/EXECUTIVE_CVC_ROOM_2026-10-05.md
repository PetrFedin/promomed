# Executive / CVC Decision Room
Date: 2026-10-05
Scope: corporate decision surface for CEO, investment committee / CVC, strategic partner and procurement/security review.

## Purpose

The room answers a different question from Investor Proof.

Investor Proof asks:
- what exists;
- what is executable;
- what is CI-proven;
- what remains gated.

Executive / CVC Room asks:
- what decision is supportable now;
- what exactly the next funded stage buys;
- which evidence releases the next tranche;
- what the paid pilot must measure;
- what a strategic partner provides and receives;
- what procurement/security can verify today;
- what is still explicitly not claimable.

## Current decision state

Until Phase 0 is COMPLETE, the allowed decision state is:

**CONTROLLED PILOT ONLY**

This is not:
- production medical rollout;
- validated market traction;
- validated unit economics;
- white-label scale;
- a revenue or valuation forecast.

## Audience lenses

### CEO
Focus:
- strategic fit;
- value creation;
- current decision;
- next gate.

### CVC / Investment Committee
Focus:
- milestone funding;
- evidence release gates;
- risk;
- economics;
- scale option value.

### Strategic Partner
Focus:
- value exchange;
- commercial proof;
- data boundary;
- renewal evidence.

### Procurement / Security
Focus:
- architecture;
- identity/authentication;
- continuity;
- privacy/consent boundary;
- vendor diligence;
- medical governance;
- production observability.

## Milestone funding

No amount is embedded in product code.

The product stores:
- tranche purpose;
- tranche status;
- release gate;
- evidence required to unlock the next stage.

This keeps funding logic separate from a negotiated commercial amount.

## Pilot contract

The pilot is defined as a contract to generate evidence.

In scope:
- participant experience;
- live operations and recovery;
- partner delivery;
- consent-first continuation;
- post-event return;
- actual delivery-cost evidence.

Out of scope:
- personalized medical advice;
- production medical-claim automation;
- unreviewed evidence scoring;
- white-label scale before repeatability proof;
- guaranteed commercial uplift.

Exit decision:
**GO / ITERATE / STOP based on agreed evidence, not presentation quality.**

## KPI dictionary

Targets are not invented by the product.

Each KPI defines:
- name;
- formula;
- data source;
- target state.

Commercial/audience target values remain `to_agree_before_pilot` until agreed with the client.

## Strategic partner boundary

Partner does not automatically receive:
- sensitive health data;
- silent contact export;
- medical/editorial approval power;
- guaranteed leads or revenue.

## Data Room index

The room indexes current evidence:
- `docs/IMPLEMENTED_SCOPE.md`;
- `docs/PROMOMED_INTEGRATION_MASTER_PLAN_2026-10-01.md`;
- `docs/DEPLOYMENT_STATE.md`;
- `docs/INVESTOR_READINESS_2026-10-05.md`;
- this Executive / CVC Room document.

Future gated packs:
- production Security / Privacy / Vendor pack;
- paid-pilot close pack with finance-approved actuals.

## Truth boundary

Current demo/runtime can be shown to executives.

It cannot claim:
- production readiness until live PostgreSQL admission is complete;
- paid market traction;
- validated unit economics;
- production medical governance.

Phase 1 remains blocked behind Phase 0 COMPLETE.
