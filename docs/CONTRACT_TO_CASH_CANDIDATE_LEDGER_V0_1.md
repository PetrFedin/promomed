# Promomed — Contract-to-Cash Candidate Evidence Ledger v0.1

Status: Draft code-only feature, **NOT an operational AR, bank, GL or revenue-recognition system**. Blocked by #64, #65, independent legal/pilot acceptance and approved Finance accounting policy.

## Purpose

Provide reproducible provenance of proposed institutional commercial documents without representing buyer intent, an invoice, bank settlement or an internal note as independently recognized revenue. The investor's Pilot-to-Revenue Evidence Ladder from PR #77 stays at all seven GATED stages even when candidate documents are present.

## What is in this PR

- Mirrored migration `026_commercial_evidence_ledger.sql` in both SQLite and PostgreSQL: versioned contract candidates, typed immutable document events, append-only evidence audit.
- Core `app/commercial_evidence_ledger.py`: functions `record_contract`, `record_event`, `snapshot`, `verify_chain`; the functions are **NOT exposed as HTTP writes**.
- Candidate-only states enforced with SQL `CHECK`: there is no `paid`, `recognized`, `approved` or `capital_released` state.
- Candidate event types: obligation, delivery, invoice, credit_note, settlement, allocation, refund, direct_cost, recognition, finance_review, renewal.
- The existing organization-scoped read-only investor projection now reports counts of candidate contract/document versions and internal audit records, clearly distinguished from actual money.
- Unit tests for cumulative caps, partial payment, credits, refunds, idempotency, revisions, immutable audit, demo segregation and tenant isolation; existing migration/restore CI runs with migration 026.

## Monetary model and reconciliation boundaries

Every monetary amount is an **integer in minor currency units**, never float; currency is a contract attribute, currently only cross-currency entries are prohibited (no FX conversion), and tax is a separate nonnegative field. The model accepts ISO-like three-letter codes, but the correctness of external currency minor-unit scaling and tax treatment requires a future approved source.

1. Contract: external reference + version + predecessor; net consideration is proposed, not approved.
2. Obligation: sum of candidate obligation amounts cannot exceed the contract's candidate net consideration.
3. Delivery: cumulative delivered candidate amount cannot exceed its specific obligation.
4. Invoice: cumulative invoice net candidate amount cannot exceed linked delivery. Tax is recorded separately.
5. Credit-note: cumulative credit net/tax cannot exceed invoice net/tax; it cannot create overallocated cash or coexist with recognized-candidate amounts without a controlled recognition reversal.
6. Settlement: external bank/PSP reference is metadata only, never proof of money unless a real provider verification is integrated.
7. Allocation: invoice net+tax minus credits cannot be overallocated; settlement cannot be double-allocated after refunds. Partial payments across multiple settlements are permitted.
8. Refund: may consume only unallocated settlement capacity. Refunding already allocated cash will need a future reviewed reversal process.
9. Direct cost: a candidate voucher linked to delivery, not an approved cost of sales.
10. Recognition: a candidate period-linked memo with net ceiling, **not a posted GL journal**. The current test scheme requires invoice linkage and therefore is not a general-purpose accounting recognition engine.
11. Finance review: dispositions restricted to `hold`, `request_changes`, `rejected`. There is deliberately NO `approved` decision.
12. Renewal: a distinct candidate contract referencing the prior period and a previous recognition *candidate*. This is **not a signed renewal**.

## Actor and data separation

- Non-public Python-only custody functions require a matching active admin/operator membership at the exact organization, matching demo scope, validity window and bearer identity mapping. Membership is checked before looking up the target record.
- Non-demo writes reject SQLite and PostgreSQL with demo seeding. This is not a substitute for external finance authority; the non-demo path remains a candidate write.
- Read APIs remain authenticated and read-only; unauthorized organizations return the same not-found response as unknown organizations.
- The immutable audit SHA-256 chain supports database-local integrity checks, **not non-repudiation or external financial signatures**. `verify_chain` recomputes the chain over source payload hashes; external signed attestations, independent signing and timestamping are deferred.
- The base app's demo Deal Room / partner technical ACK / catalogue are never imported into financial actuals.

## Safe correction policy

Documents never update or delete. Version N+1 replaces previous version after an explicit reference, and downstream evidence blocks revision to avoid quietly invalidating invoices, allocations and recognition memos. A later complete reversal/credit workflow is a separate authority-gated epic.

## Acceptance gates

- PASS required: exact-head UI/persistence/browser CI, SQLite & PostgreSQL migrations/restore, tests for multi-tenant data and negative money/approval cases.
- HOLD: Phase 0 PostgreSQL #65, live Render reconciliation #64, real buyer signature, legal acceptance, bank/PSP authority, GL accounting/finance controller and true multi-signatory audit.
- No production deployment, external transfers, invoice issuing, live payment capture or capital release is authorized by this PR.

## Follow-on architecture (#78)

Replace synthetic candidate receipts with signed original evidence in tenant-scoped source storage; adopt contract and invoice legal IDs, local accounting policy, consent and document retention; add review-by-different-actor commands; implement bank/PSP and GL reconciliation with immutable reversal records; only then recognize amounts and compute auditable contribution/retention. The accepted financial reports must be external-source-supported, not candidate values.