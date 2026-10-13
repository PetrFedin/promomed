# Partner Collaboration — verified organizational tenancy v1

**Status:** implemented in Draft PR only; not merged, not live-admitted. 2026-10-13.
**Dependencies:** #73 (stakeholder journeys + planning), #79 (task execution), #64 (Render service proof), #65 (isolated 0-RUB PostgreSQL). This is a stacked work branch based on #79; do not merge out of order.

## Why this is necessary
An authenticated partner account was previously enough to create projects by email address. Commercial parties need an organization/tenant boundary so no partner can access or accept work belonging to a different institutional counterparty.

## Implementation
- New paired additive migration `028_partner_organization_tenancy.sql` in SQLite and PostgreSQL. Its immutable `partner_collab_project_scopes` table links one project to a registered institutional organization. Existing 026/027 migration checksums remain unchanged.
- The source authority is existing `institutional_organizations` + `institutional_memberships` and the account. New scopes require **active** organization, **active** account, **active unexpired** membership, operator/administrator role, a non-empty `verification_ref`, and matching `demo_only` status. A demo account never receives non-demo institutional scope.
- Owner email alone does **not** authorize read/write or idempotent replay for a scoped project. Membership may be shared by verified users in the same organization; a foreign or revoked account receives 404 without tenant metadata.
- Central organizer keeps distinct, privileged review authority for currently active organizations, but cannot impersonate a partner's signed contract or commercial external acceptance.
- Scoped tasks retain v027 two-party performer/reviewer logic and stored receipts. Revoked membership is checked at the current request and before returning cached idempotent output.
- Endpoint `GET /api/partner-collaboration?view=organizations` lists only active **demo** organizations admitted to the current partner. The UI offers verified demo organization selection and labels legacy unscoped demo projects.
- **Fail-closed:** unscoped creation is available solely in local/seeded demo configurations for backward-compatible QA. On an unseeded PostgreSQL instance, unscoped creation is denied. Non-demo scoped project creation is explicitly denied until real production authority has separately passed its admission gates. This protects against automatic promotion of synthetic partners.

## Evidence semantics and gaps
- `verified` refers to the *existence and active status of institutional membership data maintained inside the authority*, not independent external Know Your Business confirmation. Demo organizations are fixtures; they are not real signed counterparties.
- No invitation UI, external login onboarding, partner data consent, organization admin delegation, external contract, invoice, payment collection or revenue claim is added.
- Existing institution status/qualification rules and governance authority remain canonical; this module does not create its own organization registry.
- Stacked PR #79 and read-only seven-stage evidence PR #77, as well as draft #80, must never auto-elevate internal acceptance receipts into accepted finance evidence.

## Admission and verification
1. UI contract includes `tests/test_partner_org_scope.py` with active member, cross-tenant denial, shared authorized collaborator, unverified member, revocation, expiry, immutable scopes and idempotent replay after revocation.
2. PostgreSQL 17 workflow includes scope creation, read, membership revocation and denial of replay in a test transaction, with rollback and no effect on production.
3. Run full browser tests for participant → partner → organizer → investor and verify tenant picker behavior on phone/tablet/desktop.
4. GREEN on exact commit, independent security review, merged upstream PR #73 then #79, then safe integration.
5. No live release before #64/#65; no extra paid resource, auto-upgrade or billing toggle. Existing GitHub Actions quota consumption not independently audited.

**Next engineering wave:** governance-approved membership invitations, organization-specific partner admins, scoped organizer access policies, independent artifact byte digest verification, legal acceptance vs delivery authority, then evidence-linked Client Relationship 365 and Investor Value Control Tower.
