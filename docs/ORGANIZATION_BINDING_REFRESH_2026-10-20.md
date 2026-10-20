# Institutional organization refresh: omission is not revocation
Candidate date: 2026-10-20. Stacked on Draft PR #134. NOT deployed.

## Existing risk
The earlier register_organization API defaulted partner_id to None and always
updated partner_id on the institutional_organizations UPSERT conflict branch.
A routine institution metadata refresh that omitted partner_id could therefore
erase an existing binding, unexpectedly triggering commercial access revocation.

## Candidate fix
- A private sentinel distinguishes omitted partner_id from explicit null.
- New organization + omitted binding receives NULL.
- Existing organization + omitted binding retains the currently stored binding.
- Explicit partner_id=None still clears the binding in this internal function.
- Nonblank explicit strings must resolve to an existing legacy partner row;
  blank and non-string inputs fail validation.
- The preservation rule is in a single conflict SQL statement; concurrent
  metadata refresh never copies a stale pre-read partner_id into the update.

## Regression
- SQLite institutional evidence suite exercises metadata refresh preserving
  the binding, explicit null and whitespace rejection.
- PostgreSQL 17 fixture repeats omission/null/whitespace behavior on a real
  isolated CI database.
- Existing demo/non-demo boundaries and package integrity tests still run.

## Not claimed
This is not approval for partner reassignment by arbitrary callers. The
existing internal actor parameter is not an independently verified governance
authorization. Issue #135 remains OPEN for an explicit authenticated binding
change, audit trail, reassignment rules and cross-module privacy review.
Issue #133 still owns the distinct collaboration access policy.

No schema migration, main merge, paid resource or production deployment.
Release HOLD remains until #64, #65, #94 and independent review.
