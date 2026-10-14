# Promomed: Client → Partner → Investor evidence ladder

**As of 2026-10-13:** strategy/acceptance spec for AFTER PR #69 + #70 exact-head CI and Phase 0; not a declaration that real commercial participation exists. Canonical integration: `docs/PROMOMED_INTEGRATION_MASTER_PLAN_2026-10-01.md`, `docs/PROMOMED_PRODUCT_CLOSURE_AUDIT_BACKLOG_2026-10-11.md`.

## Why this sequence

Institutional audiences need to see the ability to work together, not a static pitch. But an interactive demo is not proof of real users, contract obligations, attributable revenue or financial return. The next engineering wave must be **verified event → explicit consent → fulfilled partner obligation → measured outcome → financially accepted value**, with distinct authorities and ownership at each step.

| Surface | First genuinely useful workflow | Source of truth | Acceptance evidence | Must NOT be claimed |
|---|---|---|---|---|
| Client Relationship 365 | Participant views exactly their own confirmed registrations, attendance, replay, chosen interests and D1/D7/D30 follow-ups | authenticated participant records / existing `journey365` and `participant` projections | server-scoped exact identity, timestamps, evidence references, check-in and repeat action proven after restart | synthetic retention, medical benefits, behavioral inference or cross-user profiling |
| Partner Collaboration | Verified partner submits initiative, accepts deliverable owner, internally tracks tasks, review and reconciliation | `partner_collab_*` demo draft authority, later institutional membership + obligation authority | RBAC denial, idempotency, two-party acceptance separately attributable and persistence after restart | signed contract, buyer demand, monetary partner ROI or consent to share participant contacts |
| Investor Value Control Tower | Distinct readiness, pilot engagement, delivery, finance and decision gates | canonical `investment_proof`, `deal_room`, `portfolio_control`, accepted finance records | linked exact SHA, accepted milestone, evidence hashes, signed agreements, actual invoices/cost evidence when available | ARR/MRR, paid customers or capital returns inferred from demo counts |

## Measurable event design (no fake rates)

- `Unique active participants`: distinct **non-demo** account IDs over fixed, declared observation window; 0 if no admissible authority, never number of seeded test accounts.
- `Registration → verified attendance`: denominator distinct accepted registrations; numerator same attendees with validated check-in; report exclusions, duplicate events and sample size. A replay click is not attendance.
- `D7 / D30 return`: distinct cohort participant IDs with verified action at least 7 / 30 days after cohort start, with timezone and consent treatment defined; do not count scheduled follow-ups as confirmed return.
- `Partner activated`: verified external organization identity + real approved agreement + accepted work item; internal review or partner package listing insufficient.
- `Consented introduction`: scoped, revocable record specifying recipient, purpose and actor; never infer from generic enrollment, click or appointment.
- `Recognized revenue`: actual finance source-backed amount under applicable accounting policy, net of credits/refunds. A proposed price or demo `leads` counter is not revenue.
- `Unit economics`: recognized revenue - verified direct delivery costs; avoid double counting platform vs event/partner billing. Report denominator and period.

## Implementation gates

1. **P0** exact-head UI + PostgreSQL + browser + integration checks GREEN for #69, #70, #73; review security and mobile snapshots. No merge without review.
2. **P0** #64 Render existing service configuration corrected by owner-approved workspace action, actual deployed SHA and health checked independently.
3. **P0** #65 own Promomed zero-new-cost PostgreSQL with independent restore target, migrations 001–026, backup, fingerprint/restart and `production_ready` truth. If zero incremental price cannot be verified, `BLOCKED_NO_FREE_CAPACITY`.
4. **P1** turn demo-only partner project owner into verified organization membership and explicit partner role scoping. Keep older demo data permanently distinct.
5. **P1** complete partner task statuses/receipts/deliverable acceptance with independent party and immutable history; no auto-conversion to contract.
6. **P1** authenticated Client 365 **own-data-only** history and consent controls; hard fail for foreign tenant and expired/revoked consent.
7. **P1** read-only investor ledger with links to accepted pilot evidence / attributable finance facts, explicit `unverified` for missing records.
8. **P2** partner opportunity marketplace publishing only approved opportunities with disclosure, expiry and verified authorized organization; no health-product promotional claims.
9. **P2** user-approved pilot with actual external parties and non-demo evidence; independent legal, security and medical review before public claims.

## Cost / safety constraints

No new payment, paid server, usage-based integration, SaaS trial with credit card, domain, provider license or paid AI service. Existing Free tier requires quota and availability proof; do not reuse MFW/Marco/Antiqua databases. Test with synthetic identities only, never patient medical information. Do not claim that 0 RUB infrastructure expansion means zero total economic cost or production SLA.

## Next agent handoff
Start from current GitHub PR heads, not old chat statuses. Pick P0 blockers first. For each new API/UI/database change require same-sha positive AND negative role tests, mobile/tablet/desktop browser screenshots, rollback and recovery evidence, then update this file with exact PR/evidence links. Maintain Draft status until verified.
