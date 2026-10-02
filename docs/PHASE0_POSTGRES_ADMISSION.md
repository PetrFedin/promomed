# Promomed Phase 0 — Durable PostgreSQL Admission Runbook

Status: repository-ready; external durable PostgreSQL resource still required.

## Purpose

This runbook is the fail-closed path from a newly provisioned isolated PostgreSQL database to Phase 0 persistence admission.

Phase 0 is not complete merely because a connection string exists. Admission requires:

1. PostgreSQL backend selected;
2. `PROMOMED_REQUIRE_POSTGRES=true`;
3. `PROMOMED_SEED_DEMO=false`;
4. migrations applied with no checksum drift;
5. durable account authority migration present;
6. zero `@demo.ru` accounts on the admitted production database;
7. database write/read/delete probe PASS;
8. source catalog fingerprint captured without row contents;
9. backup created with SHA-256 manifest;
10. restore into a separate isolated PostgreSQL target;
11. restored target independently admitted;
12. source and restore catalog fingerprints match;
13. Render admission service receives the admitted `DATABASE_URL`;
14. live `/ready` returns `ready=true` and `production_ready=true`;
15. live `/health` proves the exact Git SHA.

## Provider boundary

The workflow is provider-neutral. The current master plan names Neon Free in Frankfurt / eu-central-1 as the preferred zero-cost candidate, but Neon is infrastructure only. Promomed owns schema, migrations, accounts, sessions, consent rules and audit state.

Do not reuse MFW, Antiqua or FLASHIN databases.

## Required databases

Use two isolated PostgreSQL databases:

- source/admission database;
- restore-proof database.

They must not share the same database URL.

For providers with branching, an isolated restore branch/database is acceptable if it is independently addressable and can be destroyed after proof.

## GitHub secrets

The manual workflow `.github/workflows/phase0-postgres-admission.yml` expects:

- `PROMOMED_ADMISSION_DATABASE_URL`;
- `PROMOMED_ADMISSION_RESTORE_DATABASE_URL`.

Do not put either URL into the repository, issue text, CI logs or demo fixtures.

## Run repository admission

Run the workflow:

`Promomed Phase 0 PostgreSQL admission`

It executes the same repository utilities that are exercised against PostgreSQL 17 in pull-request CI:

- `ops/phase0_postgres_admission.py`;
- `ops/db_catalog_fingerprint.py`;
- `ops/db_backup_restore.py`.

The workflow must fail if demo seeding is enabled, demo accounts exist, migrations drift, the write probe fails, restore fails, or source/restore fingerprints differ.

## Render admission service

Only after the manual database workflow is green, configure the existing admission service with:

- `DATABASE_URL=<admitted source URL>`;
- `PROMOMED_REQUIRE_POSTGRES=true`;
- `PROMOMED_SEED_DEMO=false`.

The service build must install `requirements.txt` so `psycopg` is available.

Trigger an explicit exact-main Render deploy.

## Live acceptance

Required live response characteristics:

`/health`

- HTTP 200;
- backend = `postgres`;
- durable = `true`;
- demo_seed = `false`;
- git_commit = exact current `main` SHA.

`/ready`

- HTTP 200;
- backend = `postgres`;
- durable = `true`;
- schema_ready = `true`;
- checksum_drift = [];
- demo_seed_enabled = `false`;
- demo_accounts = 0;
- ready = `true`;
- production_ready = `true`.

Then run an authenticated smoke only with a deliberately provisioned non-demo account. Do not enable the old demo identities on the production contour.

## Completion evidence

Update `docs/DEPLOYMENT_STATE.md` with:

- exact Git SHA;
- Render service/deploy ID;
- PostgreSQL provider/region without credentials;
- migration versions;
- admission workflow run ID;
- source catalog SHA-256;
- backup/restore PASS;
- live `/health` proof;
- live `/ready` proof.

Only after this evidence exists may Phase 0 be marked COMPLETE and PROMO-INT-02 begin.
