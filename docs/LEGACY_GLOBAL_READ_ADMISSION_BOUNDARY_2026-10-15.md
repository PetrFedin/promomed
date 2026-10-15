# SEC-01 — legacy global-report boundary (2026-10-15)

**Scope:** proposed source-only Draft PR stacked after integration #92 and request/demo hardening #93. Not a claim of production acceptance, validated real-tenant isolation, or completed privacy governance.

## Observed source risk

Older HTTP routes in `server.py` read shared global tables without a required organization identifier + active membership predicate. Examples include `/api/intelligence` (registrations, partner engagement, follow-ups and interest totals), `/api/command` (staff shifts, incidents and broadcasts), `/api/continuity-proof` (direct-message total), and anonymous `/api/state` (global commercial counts and operational state). A partner's legacy role check alone is insufficient for organization-bound data.

## Safe interim behavior

`app/legacy_report_scope.py` names these nine exact legacy global-read routes:

- `/api/state`
- `/api/analytics`
- `/api/command`
- `/api/intelligence`
- `/api/investor-proof`
- `/api/executive-room`
- `/api/corporate-readiness`
- `/api/product-quality-proof`
- `/api/continuity-proof`

All `/api/demo/*` routes remain separately protected by the same early guard and by the demo read/command modules. When `PROMOMED_SEED_DEMO` is false, these paths return `404 {"error":"not_found"}` **before** token lookups and shared DB reads. Query strings are normalized at the HTTP entrypoint. Demo mode retains existing role checks and demonstrations; no new authority or real customer analytics is implied.

**Notably, /api/state is deliberately unavailable in a non-demo runtime.** This is necessary because its current payload combines anonymous public content with unscoped business metrics, and it may include account-specific information when authenticated. Therefore a non-demo consumer web experience is **not admitted** by this change. No automatic conversion of demo results to a user-facing product is allowed.

## Next required engineering work before a real pilot

1. Create versioned public discovery/catalogue projections excluding personal records, private editorial artifacts, campaign rates, unreleased operational status, and unsourced/held medical claims.
2. Split participant account reads from public state. Require active account, current role, explicit purpose and object-owner match for personal records.
3. Implement organization- and venue-scoped analytics for partner/staff/organizer/sales roles. Filter at the SQL predicate level, not only after a global query. For real production, deny legacy `partner` role access to system-wide intelligence.
4. Prove two genuinely disjoint non-demo organizations, forged/missing/revoked membership, no row *or metadata existence* leakage, equal unauthorized response shapes, restricted exports and audited consent revocation.
5. Run negative HTTP + PostgreSQL + browser tests at the same SHA, with explicit owner review. Update `/ready` semantics only after a complete eligible non-demo onboarding journey is verified end-to-end. Do not label live pilot or finance accepted from green unit/CI checks.
6. Resolve #64 actual Render service settings, #65 isolated no-extra-cost PostgreSQL with separate restore target, #94 main protection, and independent review before any production deployment.

## Acceptance proof limited to this change

`tests/test_legacy_report_scope.py` enumerates every observed legacy route, asserts no call to authentication/DB for non-demo requests (including authorized-role routes and query selectors), checks non-demo unrelated scoped paths remain outside the registry, and proves demo-path authorization handling was not relaxed. Both UI and SQLite/PostgreSQL CI pipelines execute this test module.

No existing production HTTP service or tenant data is touched by the code changes. All real-world business KPI, verified retention, bank settlements, accepted revenue and Phase 0 deployment claims remain unverified.
