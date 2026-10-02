# Phase 0 — Persistence Admission

Status: **repository implementation in progress; production PostgreSQL not yet admitted**.

## Authority model

- `/health` proves that the process is alive and reports backend + deployed Git SHA.
- `/ready` proves schema migration state and baseline data readiness.
- `production_ready=true` is possible only on a durable PostgreSQL backend with clean migrations and baseline data.
- SQLite remains supported for local/demo continuity, but can never satisfy production durability.

## Configuration

- `DATABASE_URL=postgresql://...` selects PostgreSQL.
- Without `DATABASE_URL`, runtime uses `SQLITE_PATH`.
- `PROMOMED_REQUIRE_POSTGRES=true` makes readiness fail unless PostgreSQL is selected.
- `PROMOMED_SEED_DEMO=true` enables deterministic demo seed. It defaults to true only for SQLite.
- `PROMOMED_SESSION_TTL_SECONDS` controls durable session lifetime.

## Migrations

Versioned migrations live under:

- `migrations/sqlite/`
- `migrations/postgres/`

Applied versions and SHA-256 checksums are recorded in `_schema_migrations`. A modified applied migration is treated as checksum drift and fails readiness.

## Durable sessions

Login tokens remain opaque to the client. Only SHA-256 token hashes are stored in `auth_sessions`; session role, account identity, created/expiry timestamps and revocation state are database-backed.

This removes the old process-memory session authority. Demo credentials remain fixtures and are not a production identity provider.

## Backup / restore

`ops/db_backup_restore.py` supports:

- SQLite online backup via the SQLite backup API;
- PostgreSQL custom-format `pg_dump`;
- checksum manifest;
- PostgreSQL `pg_restore`;
- independent restored-database verification in CI.

## Admission gates

The GitHub workflow `Promomed persistence authority` must pass:

1. SQLite migration compatibility;
2. real PostgreSQL 17 migration;
3. deterministic re-seed;
4. state queries on both backends;
5. durable session lookup;
6. backup and restore verification;
7. migration checksum verification.

## Current external blocker

The public Render service has been observed serving an older runtime that does not expose `git_commit`. Therefore repository completion does **not** equal live admission. Production completion requires:

`main exact SHA -> Render exact SHA -> DATABASE_URL PostgreSQL -> migrations -> /ready production_ready=true -> backup/restore evidence`.
