# СОСТОЯНИЕ × Промомед — Pilot Command System v1.3

Рабочий репозиторий концепции **СОСТОЯНИЕ** для Промомед. Это самостоятельный продуктовый концепт, а не официальный продукт компании. KO-LAB/co-lab.pro использовался только как референс концепции.

## Текущая версия

**v1.4 Health Media & Conference + Pilot Command System** — year-round health-media и product experience + 42-event multi-track conference + Pilot Command System + Customer Intelligence + Owner Control Tower.

### Что реализовано

- participant journey: регистрация, профиль, программа, персональный маршрут, ticket/QR, booking/waitlist;
- live conference boundary: scheduled → live → technical pause → ended/replay, captions/replay boundary;
- venue operations: live floor map, capacity/occupancy, queues, hall state, waitlist;
- staff operations: assignments, on-shift state, оперативное переназначение;
- incidents: severity, recovery, SLA status и escalation signal;
- speaker readiness: check-in → briefing → mic → slides → ready;
- session attendance и check-in authority;
- partner cockpit и Partner Appointment Desk;
- добровольный lead/consent boundary;
- operational participant alerts;
- multi-stream health;
- commercial analytics и Customer Intelligence D1/D7/D30;
- Owner Control Tower;
- organizer, staff, partner, participant и sales/demo roles;
- sales presentation mode для демонстрации руководству;
- Apple Wallet boundary без генерации неподписанного fake pass.

## Структура

- `server.py` — API, SQLite authority, auth/demo roles, operational state, analytics и static server.
- `public/index.html` — полный responsive web/iPhone интерфейс v1.3.
- `render.yaml` — Render Blueprint для web service.
- `docs/ARCHITECTURE.md` — текущая архитектура и authority boundaries.
- `docs/IMPLEMENTED_SCOPE.md` — карта реализованного функционала.

## Локальный запуск

```bash
python server.py
```

По умолчанию приложение слушает `PORT=8000`. SQLite-файл задаётся через `SQLITE_PATH`; без переменной используется временная БД.

## Render

Build command:

```bash
python -m py_compile server.py
```

Start command:

```bash
python server.py
```

Health endpoint: `/health`.

## Важно

Данные, программа, партнёры, эксперты и показатели в демонстрации могут быть иллюстративными. Они не должны интерпретироваться как фактические результаты Промомед или медицинские рекомендации.

## Source of truth и релизы

- Код проекта: только `PetrFedin/promomed/main`.
- Текущее состояние Render: `docs/DEPLOYMENT_STATE.md`.
- История завершённых волн: `CHANGELOG.md`.
- Правила дальнейшей разработки и релизов: `docs/RELEASE_PROTOCOL.md`.

После каждого live-деплоя фиксируются exact Git SHA, Render deploy ID, URL, smoke-test и оставшиеся блокеры. Это обязательная часть завершения каждой следующей волны.

## Current live

Authoritative Render service: https://sostoyanie-promomed-live.onrender.com

Current verified application release: **v1.4**, 42 conference events across seven parallel venues plus year-round Media/Product/Partner surfaces. Exact deployment evidence is maintained in `docs/DEPLOYMENT_STATE.md`.

## План интеграционного развития

Канонический документ для следующих волн развития и внешних интеграций:

- [docs/PROMOMED_INTEGRATION_MASTER_PLAN_2026-10-01.md](./docs/PROMOMED_INTEGRATION_MASTER_PLAN_2026-10-01.md)

Это **план внедрения**, а не утверждение о том, что перечисленные возможности уже реализованы. В документе зафиксированы последовательность работ, границы authority, внешние референсы, зависимости и критерии приёмки. Для запуска полной запланированной волны следует явно ссылаться на это имя файла.
