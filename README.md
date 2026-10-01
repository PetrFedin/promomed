# СОСТОЯНИЕ × Промомед

Рабочий продуктовый концепт **СОСТОЯНИЕ** для Промомед: year-round health media + flagship conference + post-event relationship platform. Это самостоятельный концепт, а не официальный продукт компании.

## Текущий кодовый кандидат

**v2.0 Integration Authority Candidate** реализует последовательность из `docs/PROMOMED_INTEGRATION_MASTER_PLAN_2026-10-01.md`.

Базовый продукт сохраняет:

- iPhone-first participant journey;
- 42 события / 7 пространств;
- Smart Route, booking/waitlist, QR/check-in;
- live/replay;
- venue/staff/incident/speaker operations;
- Partner Cockpit / Appointment Desk;
- native community and learning tracks;
- Customer Intelligence and Owner Control Tower.

Интеграционная волна добавляет:

- PostgreSQL 17 authority + migrations + durable sessions/consent/audit;
- editorial/medical/compliance publication workflow;
- evidence/citation/claim lineage;
- search + semantic retrieval adapters;
- explainable personalisation;
- live/replay media provider boundary + Video.js;
- evidence-first transcript/takeaway pipeline;
- Expert Rooms;
- Programme Production Desk;
- Expert Authority;
- Partner Commercial Workspace;
- notification delivery adapter;
- MapLibre venue rendering;
- explicit scale/clinical gates;
- anonymous public acquisition analytics.

## Architecture

New integration code lives under `app/` and is routed through `app/integration_api.py`. External products are replaceable providers, never silent second authorities.

`DATABASE_URL` selects PostgreSQL. SQLite remains a demo/dev fallback. Production admission is fail-closed through:

- `GET /health` — runtime/backend/migration visibility;
- `GET /ready` — 200 only for durable PostgreSQL with no pending migrations.

See `docs/ARCHITECTURE.md`.

## External provider boundaries

Supported adapters/boundaries:

- Directus — controlled authoring snapshot import;
- Zotero-pattern evidence metadata import;
- Meilisearch — rebuildable full-text/faceted index;
- semantic retrieval provider — derived similarity only;
- Metarank — ranking only, allow-listed reason codes;
- Owncast — live media transport/state;
- Video.js — playback UI;
- Jitsi — Expert Room media transport;
- pretalx — approved programme snapshot import;
- Novu — delivery orchestration;
- MapLibre — venue renderer;
- Umami — optional anonymous acquisition telemetry.

The presence of an adapter does **not** mean the external service is connected in production.

## Safety and trust boundary

СОСТОЯНИЕ is not a diagnostic/prescribing service. Personalisation may rank existing reviewed content but cannot generate diagnosis, individual treatment advice, drug recommendation or health-risk classification.

Demo content, profiles, geometry, programme details, partners and performance indicators may be illustrative and must not be represented as factual Promomed performance data.

## Development

Install:

```bash
pip install -r requirements.txt
```

Run demo/dev:

```bash
python server.py
```

Run with PostgreSQL:

```bash
DATABASE_URL=postgresql://... python server.py
```

CI verifies PostgreSQL migrations/seed, backup/restore, integration contracts, SQLite fallback and iPhone inline JavaScript.

## Render

Blueprint build:

```bash
pip install -r requirements.txt && python -m compileall -q server.py app
```

Start:

```bash
python server.py
```

The authoritative deployment ledger is `docs/DEPLOYMENT_STATE.md`.

## Source of truth

- canonical repository: `PetrFedin/promomed`;
- canonical production branch: `main`;
- integration implementation plan: `docs/PROMOMED_INTEGRATION_MASTER_PLAN_2026-10-01.md`;
- architecture: `docs/ARCHITECTURE.md`;
- implemented code scope: `docs/IMPLEMENTED_SCOPE.md`;
- deployment evidence: `docs/DEPLOYMENT_STATE.md`;
- release history: `CHANGELOG.md`.

No release is called production-complete until exact Git SHA, durable datastore, Render deploy and runtime evidence are recorded.
