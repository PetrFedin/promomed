# Promomed — Integrated Commercial Authority Qualification (13 October 2026)

**Scope:** staging-only rehearsal of the long Draft PR chain plus the independent PostgreSQL migration-parser repair. **This branch is NOT an approved deployment or merge candidate.** No Render environment variables, database connections, payment credentials, production services or purchased resources were modified.

## Exact composition

| Component | Source PR | What is included |
|---|---|---|
| PostgreSQL migration parser | #83 | Correctly splits PostgreSQL statements across comments, single/double quotes, escaped E strings, tagged/untagged dollar literals |
| Pilot-to-Revenue Ladder / scoped identity | #77 | Organizer + exact organization active membership, no financial actuals |
| Candidate commercial custody / migration 026 | #80 | Contract versions, typed evidence, append-only audit, PostgreSQL + SQLite mirrored schema |
| Candidate coverage for diligence | #84 | Bounded metadata, never actual amounts or external acceptance |
| Candidate correction versions | #87 | Immutable allocation/recognition candidate adjustments, unchanged lineage |
| Full-document audit verification | #88 | Recompute canonical amounts, source fields, actor, idempotency key and timestamps; detect missing audit entries |
| Atomic writes | #90 | Per-write SQL SAVEPOINT ensures candidate document and audit insert succeed/fail together; caller owns outer transaction |

PR #71 Investor Decision Lab remains an **independent** scenario-only UI and is intentionally NOT introduced into this qualification branch.

## Conflict inspection

- Base is the last passing commit of PR #90, which already contains the commercial dependency chain. Do not merge the PRs into `main` to construct this qualification.
- `app/db.py` was compared byte-for-byte between PR #90 and PR #83. Its pre-parser prefix and post-parser suffix are identical. Only the isolated parser function from PR #83 replaces the older function.
- `tests/test_postgres_sql_lexer.py` from PR #83 is included unchanged.
- The persistence and UI workflows combine BOTH the migration parser tests and commercial contract-to-cash tests; neither suite is removed.
- An additional `tests/test_commercial_integration_gate.py` asserts parser compatibility with actual migration 026 and candidate-only SQL states.

## Mandatory exact-SHA CI evidence

1. Render configuration contract and existing-service reconcile: must PASS; these do NOT fix live service settings.
2. SQLite: all migrations including 026, candidate contract/invoice/allocation/credit and rollback tests, SQL lexer and integration gate, backup and restore.
3. PostgreSQL 17: migration and retention tests, fault-injected audit rollback / connection reuse, SQL lexer, parser+026 integration, full backup/restore and clean Phase 0 admission.
4. UI Quality: scope leak / candidate-vs-actual boundaries + parser composition.
5. Responsive Browser QA: 375px, 820px, 1440px and failure/authentication paths; review screenshots before publication.

## Truth and safety boundaries

All monetary rows here remain **candidate-only**. They are not legal invoices, verified bank receipts, recognized revenue, approved delivery costs, external controller decisions, executed renewals or investment release orders. A database-local SHA-256 audit chain cannot prove external authenticity.

This PR must remain Draft and be treated strictly as integration evidence. Individual PRs require independent review and safe sequential merging only after approved security and infrastructure gates. Production HOLD: #64 live Render service configuration, #65 separate Promomed PostgreSQL, external signatures, Finance reconciliation and verified backup/restore in the real service. A passing Actions PostgreSQL 17 service-container test does not mean the production database has been connected.

## Recommended post-qualification sequence

1. Independent review and merge of the standalone parser PR #83, then refresh/check the corresponding migration parser in subsequent branches.
2. Independently review PR #77 and PR #80 before advancing the stacked #84 → #87 → #88 → #90 dependency chain.
3. On every real integration SHA, repeat all five workflows and negative tenant / transaction checks; review browser screenshots.
4. Correct existing Render admission then public service configuration under #64; no env var workaround for missing build/health fields.
5. Admit dedicated zero-additional-cost PostgreSQL under #65, including isolation and restore proof, before any production access.
6. Only with real approved source and independent Finance governance, implement actual contract/invoice/cash/GL reconciliation separate from candidate storage.
