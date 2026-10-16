# Promomed access authority — role / status invalidation v1
**Status:** implemented only in Draft integration PR #89, not merged or deployed. Updated 2026-10-13.

## Threat and fix
Before this change, HTTP session validation accepted the `role` copied into the session at login. If an account was suspended, deleted or reassigned to another role after session issuance, a still-valid session might retain access to organizer or partner routes until expiry. This is a real authorization gap, not a cosmetic UI concern.

## New enforcement
- `app/auth.py:auth` requires the exact `Bearer ` authorization prefix and rejects absent, whitespace-containing or oversized tokens before querying.
- Each request re-resolves session vs current `accounts`: account must exist, have status `active`, and current role must match the stored session role. Returned name comes from the current account, not old session metadata.
- Additive, checksum-stable mirrored migration `029_auth_session_revocation.sql` in SQLite/PostgreSQL installs triggers that revoke all unrevoked sessions for the account on **role changes, status changes and deletion**. No change to migrations 001–028.
- The database revocation and user change happen in the same transaction: if the change rolls back, revocation must roll back. On a committed change, an old token remains invalid even if the account is reinstated.
- Normal password rotation remains controlled by existing `ops/provision_account.py` logic; it is not assumed covered by the role/status trigger.

## Acceptance
- `tests/test_auth_session_revocation.py`: active login, exact Bearer parsing, expiry, suspension, privilege reassignment, deletion, rollback restoration, migration checksum/replay, tampered cached-role denial.
- `tests/test_auth_session_postgres.py`: the same authority on actual PostgreSQL 17, including rollback, suspension, privilege reassignment and deletion.
- Existing Client365 account isolation, partner tenant membership and organizer-only financial evidence E2E must remain GREEN at **the new head SHA**.
- Test on old session token after status changed; expect `401` / unauthenticated (not continued access). Avoid logging the raw token.
- Manual verification/independent security review and production admission of isolated 0-new-cost PostgreSQL are not satisfied by GitHub CI.

## Budget and handoff
No new provider, paid resource or network service was created. Existing GitHub Actions may consume quotas; 0 RUB incremental billed expense has not been verified by provider billing. Production HOLD until #64 Render configuration, #65 isolated free PostgreSQL, independent review, source+restore fingerprint and exact deployed SHA evidence.

Next wave: account deprovisioning audit trail, organization-specific privileged actor permissions, consent-bound partner introductions and per-organization finance review. No claimed user adoption, financing or recognized revenue from synthetic data.
