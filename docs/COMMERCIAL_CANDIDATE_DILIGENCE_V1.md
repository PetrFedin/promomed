# Commercial Diligence — candidate document coverage v1

**Release state:** draft candidate feature, stacked on Draft PR #80. This is not recognized financial data, signed customer acceptance, a bank reconciliation, or a released tranche.

## What changed

The authenticated, read-only `/api/pilot-revenue-ladder/<organization-id>` now includes `candidatePortfolio`: a bounded exact-tenant list of contract *document versions* and typed candidate event-version counts.

Each candidate item includes a privacy-preserving internal document ID, its version, demo flag and 11 event-version counts: obligation, delivery, invoice, credit note, settlement, allocation, refund, direct cost, recognition candidate, finance review, and renewal candidate. It never includes the nominal contract amount, external document reference, beneficiary, client identity, bank account or participant/health record.

## Truth guarantees

- Only authenticated `organizer` users with exact active tenant administrator/operator membership can request the data.
- Unknown or unauthorized organizations remain indistinguishable from non-existent organizations.
- All seven actual commercial gates remain `GATED` even when many candidates exist.
- Actual values `contractedRub`, `invoicedRub`, `cashCollectedRub`, `recognizedRevenueRub`, `directCostsRub`, `acceptedContributionRub` and `renewalRevenueRub` remain `null`.
- A candidate invoice record is not an issued legal invoice, settlement candidate is not bank-verified cash, recognition candidate is not posted recognized revenue, and review candidate never authorizes `approved`.
- Backend returns at most 20 candidate versions, marks `truncated=true` for additional records, and never queries unrelated organizations; table scans are limited by organization and contract IDs.
- UI renders untrusted strings via `textContent` only. It hides the entire review area without authorization and clears DOM on logout/denial.
- Local JSON evidence-request export remains based on original scoped read-only projection, not an external signature.

## Verification

- SQLite unit tests: candidate-only organization, recorded obligation, 20-item cap with truncation, no money, cross-org isolation and denial for unbound actor.
- UI contract tests: no local/session storage, no unsafe HTML, explicit candidate naming and responsive styles.
- Browser QA: phone 375px, tablet 820px and desktop 1440px; unauthorized login is denied. Positive rendering is tested with isolated in-browser **synthetic mock** that cannot send money, log in to production, or validate a real business partner. Screenshots are attached to CI artifacts.
- Full exact-head GitHub CI and independent review are required before merge. Do not infer production readiness from passing preview tests.

## Further engineering

Next: audited access policy for external buyer/finance controllers, versioned credit and reversal workflows, supplier cost vouchers and period allocations; signed contract and bank/GL adapters remain gated by #64/#65 and Finance owner. An investor view may show externally finance-approved actuals only after those admissions.

### Dependency order

- PR #83: PostgreSQL migration parser robustness / Issue #81 (independent main-based fix).
- PR #71: optional independently reviewed investor scenario UI.
- PR #77: Pilot-to-Revenue Evidence Ladder and organization-scoped auth.
- PR #80: migration 026, candidate contract-to-cash ledger. Depends on #77.
- This feature: candidate-coverage report. Depends on #80 and #77.

**Do not merge stacked branches out of order.** Production HOLD until Render Issue #64 and Postgres Issue #65 are independently accepted.