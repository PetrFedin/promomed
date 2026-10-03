# Render Deployment State

> Operational ledger for СОСТОЯНИЕ / Promomed. Product source-of-truth: `PetrFedin/promomed/main`.

## Current authoritative live — 2026-09-30

- Release: **v1.4 Health Media & Conference**
- Repository: `PetrFedin/promomed`
- Branch: `main`
- Verified application Git SHA: `6b6fc601e6694edbf6c98a0922c34d92d3f789d4`
- Render service: `sostoyanie-promomed-live`
- Service ID: `srv-daug7pnlot8c73b1aja0`
- Deploy ID: `dep-daugbl8jo6nc738agrmg`
- URL: https://sostoyanie-promomed-live.onrender.com
- Region: Frankfurt
- Plan: free
- Runtime: Python 3.12.8
- Build: `python -m py_compile server.py`
- Start: `python server.py`
- Auto deploy: yes
- Render status: **LIVE**
- Runtime evidence: `SOSTOYANIE v1.4 health media conference listening 10000`
- HTTP evidence: Render observed `HEAD / 200` and `GET / 200`
- Build evidence: **Build successful**
- Error logs at verification: no deployment/runtime error reported.

## v1.4 product state

- homepage rebuilt as a year-round health media/product/conference hub;
- Promomed editorial/company/product context;
- products presented inside an educational and regulatory-aware journey, not as disguised independent recommendation;
- richer Media: explainers, R&D/company stories, healthy launches, FM/podcast, lectorium and СОСТОЯНИЕ Box concept;
- conference expanded from 18 to **42 events**;
- **7 parallel venues**, 09:00–20:00;
- keynote, lecture, debate, panel, roundtable, workshop, practice, appointments, community, networking and B2B formats;
- existing v1.3 Pilot Command System remains part of the release.
- Promomed thought-leadership layer added: СОСТОЯНИЕ Index, Studio, Selection/Awards concept and opinion-leader engine.

## Legacy Render services

Historical services `sostoyanie-promomed-v06` and `sostoyanie-promomed-preview` were created from temporary Moscow branches. They are no longer the source-of-truth. The authoritative service above is built directly from `PetrFedin/promomed/main`.

## Release completion rule

Every completed wave records: application Git SHA, release version, Render service ID, deploy ID, URL, build/runtime verification and known production boundaries.

## Known production boundary

Persistent production datastore is still not admitted: current free service uses SQLite under `/tmp`. Production pilot requires durable PostgreSQL/migrations/session-consent-audit authority.


## Deployment drift observed — 2026-10-01

GitHub live-proof runs against `https://sostoyanie-promomed-live.onrender.com/health` observed:

- response app marker: `sostoyanie-v15-product-quality`;
- no `git_commit` field;
- therefore recent `main` commits were **not** verified as deployed to the public service.

This supersedes any assumption that repository `main` automatically equals public live. No later wave may be labelled LIVE until exact-SHA verification passes again.

Phase 0 production admission requires a separate durable PostgreSQL contour and `/ready -> production_ready=true`. Current public SQLite runtime remains demo-only.


## Phase 0 repository proof — 2026-10-02

- Main SHA: `adeb0e6e9db24900af33ac96026a4029840b97b2`
- Release state: **REPOSITORY PASS / LIVE BLOCKED**
- UI quality run: `36949486434` — PASS
- Responsive browser run: `36949486534` — PASS
- Persistence authority run: `36949486415`
  - SQLite migration + backup/restore — PASS
  - PostgreSQL 17 migration + API-state + durable session + backup/restore — PASS
- Exact-SHA live proof run: `36949486423` — FAIL

The live-proof polled the public `/health` endpoint 30 times and consistently received:

`{"ok": true, "app": "sostoyanie-v15-product-quality", "authority": "shared-sqlite-demo", "golden_demo": true}`

The public service therefore did **not** reach main SHA `adeb0e6e...`. No `git_commit` field was present.

Next admission action requires Render workspace confirmation, inspection of service `srv-daug7pnlot8c73b1aja0`, restoration of exact-main deployment, then a dedicated free PostgreSQL attachment and `/ready -> production_ready=true`.


## Phase 0 live admission checkpoint — 2026-10-02

### Exact-main deployment — PASS

- GitHub `main`: `c87aa79d775e15ac3ea46f829732ea9d5abe92a5`
- Render service: `sostoyanie-promomed-live` / `srv-daug7pnlot8c73b1aja0`
- Current live deploy: `dep-davsmbhmgk9c73c6tdn0`
- Region / plan: Frankfurt / free
- Exact-SHA public live-proof workflow: `37025984463` — **PASS**
- Post-deploy Render error logs: no errors observed in the verification window.
- Runtime remains SQLite and therefore is **not** production-ready.

### Durable PostgreSQL capacity — BLOCKED UNDER CURRENT ZERO-COST CONSTRAINT

Verified provider state:

- Render ME: one active free PostgreSQL is already occupied by `mfw-postgres`; an attempted second free database was rejected with `cannot have more than one active free tier database`.
- Supabase free organization: both allowed free project slots are already occupied by Antiqua and FLASHIN.
- Railway: Europe deployment region is Europe West (Amsterdam), not Frankfurt, and the no-cost path is a finite trial credit rather than a permanent free PostgreSQL allocation.

No existing MFW, Antiqua or FLASHIN database was deleted, paused, opened externally or reused for Promomed.

### Remaining Render configuration drift

The existing Render web service still reports:

- build command: `python -m py_compile server.py`;
- health-check path: empty.

Repository `render.yaml` expects:

- `pip install -r requirements.txt && python -m py_compile server.py app/db.py`;
- health-check path: `/health`.

Before setting a live PostgreSQL `DATABASE_URL`, the actual service build configuration must install `psycopg`; otherwise PostgreSQL startup is not admitted.

### Phase 0 status

**CODE / CI / EXACT-MAIN LIVE: PASS**  
**DURABLE POSTGRESQL LIVE ADMISSION: BLOCKED BY FREE-CAPACITY + SERVICE-CONFIG DRIFT**  
**Phase 1 remains gated.**


### Preferred zero-cost resolution candidate — Neon

After exhausting currently connected free capacity, Neon is the verified non-destructive candidate:

- Free plan available;
- PostgreSQL 17 available on Free;
- AWS Europe Central 1 / Frankfurt (`eu-central-1`) available;
- does not require deleting or sharing MFW, Antiqua or FLASHIN databases.

The Neon account/connector is not connected in the current execution context, so no Neon resource has been created and no claim of admission is made.

Required continuation after connection:

`create isolated Promomed PostgreSQL in eu-central-1 -> obtain DATABASE_URL securely -> reconcile Render build command/dependency install -> set DATABASE_URL + PROMOMED_REQUIRE_POSTGRES=true -> migrations -> /ready production_ready=true -> smoke -> backup/restore proof`.


## Responsive live checkpoint — 2026-10-02

- GitHub `main`: `3c012531174a2aff6f9fed682aaf142d7c2b474d`
- Authoritative live service: `sostoyanie-promomed-live` / `srv-daug7pnlot8c73b1aja0`
- Authoritative live deploy: `dep-davti3rncjis73fn52hg` — **LIVE**
- PostgreSQL admission service: `sostoyanie-promomed-pg-admission` / `srv-davsqk942hec73e1vcr0`
- Admission deploy: `dep-davti4jncjis73fn54mg` — **LIVE**
- Responsive browser QA run: `37031945373` — **PASS**
- UI quality run: `37031945504` — **PASS**
- Persistence authority run: `37031945258` — **PASS**
- Exact-SHA public live proof run `37031945141` rerun after explicit Render deploy — **PASS**
- Browser evidence artifact: `promomed-browser-qa`, artifact `11238230861`, SHA-256 `96c98454142d38bd507949427d6cb4c648d95b75d34294d416c483029b01f751`

Responsive matrix now covers:

- iPhone SE portrait — 375×667;
- iPhone 15 Pro portrait — 393×852;
- iPhone 15 Pro landscape — 852×393;
- iPad Air portrait — 820×1180;
- iPad Air landscape — 1180×820;
- desktop — 1440×900;
- wide monitor — 1728×1117.

The admission service installs `psycopg==3.2.10` from `requirements.txt` and therefore is ready to receive an isolated PostgreSQL `DATABASE_URL` without changing the current public SQLite service.

**Phase 0 is still not complete:** both current Render services remain on SQLite until an isolated zero-cost durable PostgreSQL contour is attached and `/ready` proves `production_ready=true`. Phase 1 remains gated.


## PROMO-INT-01 repository completion live checkpoint — 2026-10-03

- GitHub `main`: `bfb9e12a391326a40d295d57424d6de25df95b80`
- Public service: `sostoyanie-promomed-live` / `srv-daug7pnlot8c73b1aja0`
- Public deploy: `dep-db043fmgekts7383tigg` — **LIVE**
- PostgreSQL admission service: `sostoyanie-promomed-pg-admission` / `srv-davsqk942hec73e1vcr0`
- Admission deploy: `dep-db043ggu01pc738plqig` — **LIVE**
- UI/architecture workflow: `37078516176` — **PASS**
- Responsive browser QA: `37078516164` — **PASS**
- Persistence authority: `37078516147` — **PASS**
- Exact-SHA live Render proof: `37078516177` — **PASS**

PROMO-INT-01 is complete in repository scope: bounded read projections and bounded write-command handlers are separated by domain, while `server.py` is the HTTP/auth/transaction/dispatch composition layer.

Responsive/browser authority remains green across the required phone/tablet/desktop matrix.

**Phase 0 remains incomplete:** both Render contours still require an isolated durable PostgreSQL `DATABASE_URL` and live `/ready -> production_ready=true` plus live PostgreSQL smoke and restore evidence before Phase 1 may begin.


## Phase 0 durable-account authority live checkpoint — 2026-10-03

- GitHub `main`: `af0c8e16961211982adca0f6155aafd9d4d8aa87`
- Public service: `sostoyanie-promomed-live` / `srv-daug7pnlot8c73b1aja0`
- Public deploy: `dep-db049rid0e5s73a266hg` — **LIVE**
- PostgreSQL admission service: `sostoyanie-promomed-pg-admission` / `srv-davsqk942hec73e1vcr0`
- Admission deploy: `dep-db049sm7bikc7384m6gg` — **LIVE**
- UI/architecture workflow: `37079962351` — **PASS**
- Responsive browser QA: `37079962327` — **PASS**
- Persistence authority workflow: `37079962342` — **PASS**
- Exact-SHA live Render proof: `37079962354` — **PASS**

This release moves demo login authority out of `server.py` into the database, adds migration `003_account_authority`, salted scrypt password hashes, honest production-readiness gates, and clean PostgreSQL admission/restore proof.

The currently deployed Render contours remain SQLite demo runtimes. This checkpoint therefore does **not** mark Phase 0 COMPLETE.
