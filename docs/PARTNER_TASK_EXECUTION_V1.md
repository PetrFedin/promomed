# Partner Task Execution v1 — internal counterparty review

**Status:** CODE IN DRAFT PR, NOT RELEASED. **Date:** 2026-10-13.
Depends on #69, #70 and integrated #73, plus isolated Promomed PostgreSQL and existing Render configuration.

## Why

The existing Partner Collaboration Workspace could create tasks but not perform them. This extension adds explicit task state transitions and review receipts rather than presenting plans as delivered partner obligations.

### Lifecycle

- `todo → in_progress`: task performer starts work.
- `in_progress → submitted`: performer submits an artifact reference AND a 64-character SHA-256 digest **supplied by the performer**.
- `submitted → accepted`: other party (not the submitter) accepts the **internal review outcome**; accepted does **not** mean signed agreement or completed commercial delivery.
- `submitted → changes_requested → in_progress → submitted`: other party documents a reason for rework; revised submission must supply fresh reference and digest.
- `accepted` is terminal in v1. An already accepted receipt cannot be edited or deleted through API.
- Execution only when project state is `internally_reviewed`; archived/draft/reopened projects cannot execute.

### Separation of authority

| Task lane | Performer | Reviewer |
| --- | --- | --- |
| `partner` | authenticated owning partner | organizer |
| `platform` | organizer | authenticated owning partner |

The partner has access only to their own project (foreign IDs return 404). The organizer can currently access all demo projects; **organization membership and scoped organizational delegation are not yet implemented**. API rejects role switching, stale versions, unauthorized reviewer, same-email acceptance, duplicate idempotency conflicts and missing evidence.

### Persistence

New paired append-only migration `027_partner_task_execution.sql` for SQLite/PostgreSQL:
- `partner_collab_task_execution`: current task state/version, references, reviewer.
- `partner_collab_task_receipts`: immutable internal action receipts (trigger denies UPDATE/DELETE), actor role, submitted reference SHA-256 and decision.
- Existing `026_partner_collaboration.sql` unchanged, preserving migration checksums. Legacy task record's `todo/in_progress/done` status reflects coarse state; new table supplies detailed status.
- Optimistic compare-and-swap on task version; command ledger from migration 026 gives replay protection.

The SHA-256 field is **not independently checked against artifact bytes**. There is no file upload, offline copy, cryptographic external signature or artifact custody. The stored value is a submitter-supplied assertion; the reviewer must independently access/validate the referenced artifact outside the platform. This module cannot establish legal obligations, data-sharing consent, external delivery acceptance, medical approval, invoicing, revenue or ROI.

### UI

`/partner-collaboration.html`: task cards, start, evidence submission, review decision and immutable receipt history. TextContent is used for all untrusted text. Form validates reference length and SHA-256 format. The view retains clear internal/demo-only labeling.

### Verification

- `tests/test_partner_execution.py`: SQLite counterparty role tests, inaccessible foreign projects, stale version and same-operation replay, declined submissions, resubmission requirements and immutable receipts.
- `tests/test_partner_execution_postgres.py`: real PostgreSQL 17 transitions and trigger denial (transaction rolled back).
- `tests/test_integrated_stakeholder_partner_browser.py`: cross-role participant→partner→organizer→investor path plus task start→submit→accept and screenshots.
- Exact-head CI in GitHub required before review/merge, plus manual smartphone/tablet/desktop screenshot inspection.
- Existing Render Issue #64 and dedicated free PostgreSQL Issue #65 remain blocking for a real pilot.

### Zero-cost budget

No external paid service or new infrastructure created by this change. Uses only existing repository CI and the existing backend stack. Runner quotas and production hosting financial limits are **not independently audited**; 0 additional paid resources is not a claim of zero total operational cost.

### Next engineering wave (only after gates)

Verified organization memberships, scoped per-organization partner admin rights, real read-only evidence download/checksum verification, immutable financial acceptance distinct from delivery review, consent revocation and participant own-data journey. Issue #76 and #74–75 track this work.
