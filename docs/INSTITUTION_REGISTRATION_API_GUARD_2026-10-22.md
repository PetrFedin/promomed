# Promomed — institution registration API binding integrity gate
Date: 2026-10-22
State: STACKED DRAFT (candidate, not published)
Parent: Draft #137 at c56094982974d909e1ab8878e0b7a4096335d012
Related: #135 partner binding lifecycle, #133 collaboration policy, #64 Render, #65 isolated PostgreSQL, #94 branch governance.

## Defect confirmed from source

The prior protective change (Draft PR #136) used an omission sentinel in `app/evidence_interchange.register_organization`. However `app/institutional_commands.handle_command`, the actual `POST /api/institution/register` dispatcher, always passed:
```python
partner_id=(str(data.get("partner_id") or "")[:80] or None),
demo_only=bool(data.get("demo_only",False)),
external_ref=str(data.get("external_ref") or "")[:400],
credential_source=str(data.get("credential_source") or "")[:400],
```
A caller omitting `partner_id` therefore still requested explicit **unbinding**. Similarly omission of `demo_only` tried to reset demo rows to non-demo, and omission of provenance metadata overwrote existing source identifiers with blank values. The core helper's regression tests passed, but the API contract was never exercised with an authenticated governance request.

Commercial partner membership/appointment projections require a nonblank institutional `partner_id`. Accidental unbinding can revoke partner visibility and invalidate participant calendar export eligibility, without any intentional offboarding decision. Thus it was not enough to test core upsert alone.

## Candidate code behavior

- A routine governance `POST /api/institution/register` without partner_id **does not pass** the binding field into the core helper. The SQL UPSERT preserves the existing field.
- Passing a different partner_id (including explicit null on a previously bound institution) returns `409 partner_binding_change_requires_review`. Whitespace and wrong types return `422 partner_id_invalid`. Passing the unchanged current ID never mutates that ID; no stale pre-read is copied into UPDATE.
- Metadata fields `external_ref` and `credential_source` are preserved when omitted; explicit null/blank means deliberate clearing (existing reviewer policy on metadata is not implied).
- Existing `demo_only` classification is preserved when omitted. Explicit change is rejected; invalid types are rejected. New institutions default to non-demo if no classification is given. A privileged identity cannot reclassify demo evidence through ordinary metadata renewal.
- Only the existing role `governance` can invoke this route. Successful create/update writes a transactional, non-sensitive `events` audit entry with organization ID and an explicit `binding_changed=False`; rejected calls write neither institution changes nor success-audit records.
- An initial or subsequent partner binding change **cannot** be performed through this metadata API, even by supplying a new ID to create. A separate authenticated, version-checked, approved and auditable binding lifecycle remains to be designed/verified under #135 and collaboration implications under #133.
- The SQL UPSERT conflict branch includes `WHERE status='active' AND demo_only=excluded.demo_only`. A concurrent writer cannot reclassify or update a revoked organization after the Python pre-read. Zero affected rows raise `organization_concurrent_boundary_conflict` instead of falsely reporting success.

This is defense in depth for an existing code path, not a substitute for a governance approval system. Internal `register_organization` still accepts explicit binding actions from trusted callers; every caller and actor requires independent code review. No claim that a current local log is immutable.

## Cross-module acceptance scenario

1. A synthetic, verified partner account belongs to a non-demo institution with an explicit binding and active commercial placement.
2. A participant books a legitimate appointment with slot-specific contact consent.
3. The governance account edits the institution name through the real HTTP composition or bounded route, without providing partner_id, demo_only or source fields.
4. Assert organization name changed while partner binding, provenance, organization demo boundary, membership/slot and client-owned agenda export remain authoritative.
5. Explicit null, reassignment, invalid demo flag, wrong role and invalid request body fail closed; original binding/contact scope persists.
6. Confirm the accepted update writes exactly one audit event; rejected attempts do not create success events.
7. On independent real PostgreSQL 17 connections, run two concurrent metadata updates and check that both succeed without clearing binding or provenance.
8. Force conflicting simultaneous new registrations of one organization with different demo classes. Exactly one must be created and the other rejected; no metadata crossing the classification boundary. Verify stale-read SQLite protection and revoked state.

## CI/admission checklist

- Isolated SQLite fresh migration, route tests and authenticated server HTTP dispatch.
- Isolated PostgreSQL 17 fresh migration and actual concurrent connections.
- Organization/binding contract, partner commercial, appointment, persistence, UI architecture and responsive browser checks on **one exact SHA**.
- Preserve checksum migration integrity: no migration edits.
- Keep synthetic test identities and local databases, no external participant data.
- Explicit independent review of omitted vs explicit-null semantics, HTTP authority scope and audit evidence.

## Non-goals and release status

No new paid resource, no PostgreSQL admission to Render, no main branch merge, no live environment mutation, no legal or medical compliance claim. Production HOLD stays in place until #64/#65/#94/#133/#135, protected main, independent review, medical/privacy signoff and independently verified rollout/rollback.
