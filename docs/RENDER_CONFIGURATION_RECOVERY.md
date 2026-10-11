# REL-03: Render configuration recovery and validation (2026-10-12)

Issue: https://github.com/PetrFedin/promomed/issues/64

Read-only Render inspection found these facts:

| Existing service | Actual build | Health path | Latest deployed SHA |
| --- | --- | --- | --- |
| Public `srv-daug7pnlot8c73b1aja0` | `python -m py_compile server.py` | empty | `ae5303b3d4f28d558cf4cf35b9927da88653b4ed` |
| Admission `srv-davsqk942hec73e1vcr0` | `pip install -r requirements.txt && python -m py_compile server.py app/db.py` | empty | `657fc948ce58ba8044b652756dbe37911d2e4f2c` |

Initial main SHA: `15091535d78bfea80f6625e3a967143c87967ee0`. Both deploys reported live but were stale. No HTTP response body or PostgreSQL readiness was proven by this inspection.

## Target configuration for BOTH existing free Frankfurt services

- repo: `https://github.com/PetrFedin/promomed`; branch: `main`
- build: `pip install -r requirements.txt && python -m py_compile server.py app/db.py`
- start: `python server.py`
- health check: `/health`
- public auto deploy stays `commit`; admission stays `off`
- public SQLite/demo stays unchanged and MUST report `production_ready=false`

`render.yaml` defines desired settings but does **not** prove these existing services are Blueprint-managed. Do not create/sync a Blueprint and accidentally create extra infrastructure.

## Safe sequence

1. Open the [public settings](https://dashboard.render.com/web/srv-daug7pnlot8c73b1aja0) and [admission settings](https://dashboard.render.com/web/srv-davsqk942hec73e1vcr0). Confirm exact service IDs and free plans.
2. First fix admission `healthCheckPath=/health`, leaving PostgreSQL URL unset. Its build already installs dependencies. Wait for exact-main CI before manually deploying admission, since auto deploy is off.
3. Fix public build and health path in the actual service settings. Do not change public database/seeding env values. Deploy current accepted main only after CI and rollback readiness.
4. For both: verify exact deployed SHA and `/health` response; public `/ready.production_ready=false`. Run browser E2E and capture deploy IDs, proof runs and screenshots.
5. Run the new static PR CI and, if credential custody is authorized, manually dispatch `Promomed Render configuration contract`. Store an API token only in GitHub Actions secret `PROMOMED_RENDER_AUDIT_API_KEY`. This script only issues Render GET requests and does not inspect secret env values. Enable exact SHA check only after both services are independently deployed to the same accepted SHA.
6. Close Issue #64 only after actual configuration drift is zero; record evidence in `docs/DEPLOYMENT_STATE.md`.

## Issue #65 remains a separate blocker

Before any `DATABASE_URL` change, prove an isolated free Promomed PostgreSQL source and independent empty restore target, apply migrations, prove zero demo accounts, verify source/restore fingerprints and live PostgreSQL readiness. Follow `docs/PHASE0_POSTGRES_ADMISSION.md` and never reuse MFW, Antiqua, Marco or FLASHIN databases. Do not spend money or modify another project.

**Important:** The connected Render tool exposes no service Build Command/Health Check mutation. Thus these changes are NOT applied by this PR, and the public service is NOT production-ready merely because this runbook exists.

## Verified follow-up — 2026-10-12

The exact-head PR checks at `22e3b413e6e165c1b60147792320a7bed21f211f` all completed successfully:
Render contract `38178818607`, persistence `38178818527`, UI quality `38178818545`, responsive browser `38178818572`.
These are repository CI proofs only, not Render acceptance.

Read-only Render inspection again confirmed configuration drift and stale deploys. Public: `dep-db4nva7lk1mc73fd0uh0`, SHA `ae5303b3d4f28d558cf4cf35b9927da88653b4ed`. Admission: `dep-db2caec9v7es73dt4arg`, SHA `657fc948ce58ba8044b652756dbe37911d2e4f2c`. Both still lack `/health` as configured health path.

The latest audit hardening adds `--report-json <output-path>`, which emits only fixed service IDs, role, PASS/FAIL codes and an explicit `postgres_admission_proven=false`. No Render tokens, environment-variable values or response payloads are recorded. Example:

```sh
python ops/render_configuration_audit.py --live-api --report-json /tmp/promomed-render-audit.json
```

Do not commit raw Render response snapshots: they could contain unexpected sensitive metadata. Capture the redacted report and its workflow run ID only. A PASS report means configuration conforms; exact deployed SHA and live /health and /ready still need independent proof.

### Actual settings to apply on the existing services (no new services)

- Admission service: Render Settings → Health Check Path → `/health`; build and start commands remain unchanged. Keep manual auto-deploy disabled and leave PostgreSQL variables untouched.
- Public service: Render Settings → Build Command → `pip install -r requirements.txt && python -m py_compile server.py app/db.py`; Health Check Path → `/health`. Keep Free, Frankfurt, `main`, and existing SQLite/demo variables.
- Validate actual service metadata with the read-only audit, then deploy the independently accepted exact `main` SHA. Do not infer deploy success from the auto-deploy configuration flag; current observed deployments were API-triggered.
- After deployment: verify the exact SHA in Render deploy metadata and live `/health`; verify `/ready` truthfulness and responsive browser QA, then record the evidence. Keep Issue #64 open until all these steps are complete.

### Zero-cost isolation rule

The only Render PostgreSQL observed in the connected workspace is `mfw-postgres` (Free, version 17, expiring 2026-10-30), which is out of scope and must not be modified. No dedicated Promomed PostgreSQL source/restore resources have been verified. Issue #65 cannot be closed on the basis of CI's ephemeral PostgreSQL alone.
