# Candidate Contract-to-Cash — Atomic Document + Audit Writes

**Status:** candidate-only code; no public HTTP write route, no external bank authority, no Finance acceptance. Draft PR only.

## Invariant

Every local `record_contract` and `record_event` operation must either insert its candidate financial document **and** its corresponding append-only audit record, or insert neither. The caller, not the library, chooses when to COMMIT the enclosing transaction. Success never performs an implicit COMMIT; a deliberate caller ROLLBACK can still revert the full group of earlier successful candidate writes.

## Implementation

- A unique `SAVEPOINT promomed_candidate_N` encloses the complete candidate business command, including organization membership, source validation, immutable document INSERT and chained audit INSERT.
- On any exception from the command or SAVEPOINT release, ROLLBACK TO SAVEPOINT is attempted and the savepoint is released; the original failure is surfaced where the database allows it. This is crucial on PostgreSQL, where any constraint/trigger SQL exception otherwise leaves a transaction aborted until a full ROLLBACK.
- SQLite retains its existing BEGIN IMMEDIATE writer serialization; PostgreSQL retains the existing per-organization advisory transaction lock. Neither the application nor this PR exposes a public financial mutation API.
- Failed commands may be caught by their caller. A subsequent outer COMMIT must not persist a candidate document missing an audit record, and must not roll back unrelated work before the SAVEPOINT.
- Retrying the same idempotency key following a rolled-back audit failure must create exactly one candidate event with an audit entry. Calls with the same idempotency key and different canonical payload continue to fail.

## Automated negative proof

- SQLite: install test-only BEFORE INSERT audit rejection triggers, record unrelated outer-transaction work, run a contract or event write, catch the injected audit failure and COMMIT. Verify no half-written contract/event, previous audit chain valid, unrelated outer work preserved, and safe retry succeeds after dropping trigger.
- PostgreSQL 17: install test-only BEFORE INSERT rejection trigger/function, induce contract or event audit failure, then prove the connection remains usable, explicit caller COMMIT has no orphaned document and the retry succeeds after removing test fixtures.
- CI: `tests/test_commercial_evidence_ledger.py` runs in SQLite and PostgreSQL persistence jobs; `tests/test_commercial_evidence_ledger_postgres.py` verifies PostgreSQL behavior directly. Migration `026` is unchanged.

## Remaining admission gates

Database-local hash chains are not independent signatures, nor does candidate evidence authorize actual invoicing, posted accounting journals, collection, customer acceptance, profit figures, or investment tranches. Production HOLD (#64 Render live configuration, #65 dedicated Promomed PostgreSQL and restore) remains. Independent review plus exact-SHA CI required before any merge. PR depends on #88 → #87 → #84 → #80 → #77.