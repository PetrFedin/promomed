# СОСТОЯНИЕ — Pilot-to-Revenue Evidence Ladder v1

**Status:** candidate / read-only application feature, not live commercial or finance admission.

## Customer-led buying question

Can a paying institutional customer move from an authorized bounded pilot to accepted services, invoicing, cash settlement, Finance-recognized revenue, transparent costs and a repeat signed period without substituting demo events, partner packages, draft invoices or clicks for commercial facts?

Existing project evidence establishes planning and demonstration features: Proposal Studio, Partner Delivery, Deal Room, Finance Acceptance and Investor Decision Lab (separate Draft PR #71). There is **no verified external commercial contract, accounts-receivable invoice, bank receipt, signed Finance recognition or renewal authority in the current 25-migration database**.

## Seven stages and hard stops

| Stage | Real source required | Fail-closed state | Business control owner |
|---|---|---|---|
| 1. Accepted pilot | Counterparty signer, signed scope, External Participation Acceptance | GATED | Institution + Governance |
| 2. Contract | Executed terms, commitments, amounts, currency and version | GATED | Legal + Commercial |
| 3. Delivery | Contract-linked deliverables, independent buyer acceptance, dispute/credit record | GATED | Delivery + Customer |
| 4. Invoice | Accounts-receivable invoice ID, legal entity, tax and credit-note status | GATED | AR / Finance |
| 5. Cash | Bank/PSP settlement linked to invoice, refunds and chargebacks | GATED | Treasury |
| 6. Finance | Revenue recognition, direct cost ledger, account policy, Controller acceptance | GATED | Finance Controller |
| 7. Renewal | New signed term, prior contract link, recognized renewal revenue | GATED | Account + Finance |

### Existing technical signals (never considered stage acceptance)

- Read `institutional_organizations` scoped by exact organization ID: non-demo identity metadata may exist but is not a signed pilot.
- Read non-demo `evidence_exchange_deliveries` acknowledgements scoped by exact organization ID: this is *technical* delivery of evidence, not commercial acceptance, invoicing or revenue.
- No fallback to synthetic `deal_payment_requests`, demo `contract_builder` investment envelopes, partner packages or global event statistics.
- No silent claim of zero revenue when data are missing: values are **null (not verified)**, never fabricated or defaulted to 0.
- A SHA-256 of a deterministic evidence *request* pack is an integrity fingerprint, not a third-party signature, signed acceptance or payment authorization.

## Security and correctness

- Route: `GET /api/pilot-revenue-ladder/<organization-id>` through `strategic_reads.read`, authenticated `organizer` role **only**, AND a current `institutional_memberships` record for that exact organization as an active administrator/operator, matching demo boundary and valid effective/expiration timestamps. Sales and partner requests return forbidden before lookup; organizers without membership receive the same `organization_not_found` response as an unknown organization. Existing bearer sessions supply email to the route. Do not open external access without an independently reviewed commercial access policy.
- Strict `[A-Za-z0-9:_-]` identifier, maximum 100 chars, and exact SQL `organization_id=?` predicates.
- No new SQL migrations, financial mutation commands, payment routes, customer contact imports, HTTP POST to finance or automatic capital release.
- UI authentication only through existing `/api/login`; bearer token resides in memory, not web storage; local JSON exports are manual.
- No real PII/medical content is included in the structured financial projection. A future real pilot requires separate privacy and retention approval.

## Business metrics to add only after accepted authority

Quantitative data must use a per-contract / per-invoice / per-period grain with source ID, currency, tax treatment, status, creator, approved actor and immutable evidence digest. All numeric metrics require known finance definitions and evidence:

- Contracted consideration: sum of signed active contract line values for agreed scope (not ARR by default).
- Invoiced: valid issued invoices less accepted credit notes.
- Cash collected: posted bank/PSP receipts allocated to invoice IDs net of refunds.
- Recognized revenue: journal lines approved for recognition period after adjustments.
- Direct delivery costs: attributable supplier/labor/platform costs, allocation method and approvals.
- Accepted contribution: Finance-recognized revenue minus approved attributable direct delivery costs; not EBITDA or FCF.
- Renewal: newly signed new term and recognized renewal revenue; define GRR/NRR on a consistent eligible customer cohort before computing ratios.

Do not sum annual license projections with event revenue if a contract already packages those components. Do not treat marketing reach, bookable events or product usage as amounts owed. No forecast ARR, GMV, ROI or return guarantee is produced by this module.

## Acceptance and tests

1. Unit: both demo and non-demo fixture organizations, one technical ACK; both remain financially gated, other organization must not see ACK.
2. Unit: malformed identifier and nonexistent org fail; partner/participant/sales roles cannot infer existence.
3. Unit: deterministic pack hash, `null` amounts, no capital release.
4. UI: seven stages, keyboard click, responsive 375/820/1440, denial and password clearing, zero JS errors, no horizontal overflow.
5. CI: UI-quality contract plus responsive browser workflow on exact head SHA; screenshots archived.
6. Production: remains HOLD until Issue #64 and #65 pass and authorized external financial authority is defined.

## Next implementation (separate gated epic)

1. Approve a real tenant-scoped authenticated commercial role model and independent signed participation authority.
2. Introduce versioned PostgreSQL financial ledger tables with uniqueness/idempotency, immutable financial event journal, on-behalf-of authorization and invoice/credit linkage.
3. Add external invoice/payment provider adapters as receipt candidates, never automatic recognition; explicitly document and verify reconciliation.
4. Add Controller decision with dual control and immutable accepted evidence; tests must prove reversal and no cross-org leakage.
5. Only then promote a non-demo contract through all seven steps with actual buyer acknowledgment and Finance sign-off. Separately validate cost and renewal cohort before showing a recognized financial KPI.

**Release note:** PR #71 Investor Decision Lab currently remains separate from this branch. Its three financial scenarios are user-input assumptions, not sources for this financial ledger.