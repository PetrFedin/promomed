# promomed — обязательная программа внедрения с нулевой стоимостью

**Snapshot:** 2026-10-12 · **Status:** REQUIRED / NOT ALL IMPLEMENTED · **Purpose:** persistent work pickup, not release evidence.

**Источник канона:** `docs/IMPLEMENTED_SCOPE.md`, `render.yaml`, Issue #64, Issue #65, `docs/DEPLOYMENT_STATE.md`

**Текущее ограничение:** PR #63 слит. Issue #64: live Render build/health не соответствует `render.yaml`. Issue #65: отдельная PostgreSQL ещё не допущена; нельзя использовать MFW/Antiqua/Marco DB.

## Работы в порядке зависимости

| ID | Priority | Обязательно внедрить | Связи/зависимости | Доказательство завершения |
|---|---|---|---|---|
| PRO-ZC-01 | P0 | Свести live Render к `render.yaml` без создания новых сервисов | existing Render web → pip requirements → startCommand → `/health`/`/ready` | live settings подтверждены, exact deployed SHA и оба endpoints проверены; конфигурация не выдаёт demo за production |
| PRO-ZC-02 | P0 | Создать изолированный 0-cost PostgreSQL контур только при подтверждённом free allowance | source PG → migration manifest → isolated restore → Render admission | источник и restore target различны, backup/restore/fingerprint proof, отсутствие DSN в GitHub, production readiness честна; иначе BLOCKED |
| PRO-ZC-03 | P1 | Доказать сквозную конференцию | registration → role/consent → agenda → capacity/waitlist → QR → attendance → replay | server E2E + mobile screenshots + отказ при ошибочных ролях/дубликатах |
| PRO-ZC-04 | P1 | Редакционная и медицинская governance | content → citations/review → publication → partner leads/analytics | отдельная проверка медицинских утверждений, отзыв consent, журнал решений, отсутствие неподтверждённых claims |

## Непереговорные ограничения: 0 ₽ новых расходов
- Запрещено создавать/включать платные ресурсы, pay-as-you-go, автоапгрейд, платный AI/API, платную БД, облачное хранилище, CI minutes сверх бесплатной квоты или оплачиваемые production-транзакции.
- Сначала доказывать, что существующая локальная инфраструктура, open-source инструменты или **подтверждённый доступный** бесплатный лимит действительно не требуют оплаты. Если 0-cost ресурс не подтверждён — статус `BLOCKED_NO_FREE_CAPACITY`, не выдумывать альтернативную готовность.
- Не менять и не подключать базу, секреты, деплой другого продукта; никогда не публиковать DSN/токены. Никаких несанкционированных изменений production/main. Кодовые задачи — отдельные PR и существующие quality gates.
- Не запускать реальные платежи/торговлю/рассылки/платные провайдеры ради теста: тесты, моки, sandbox без биллинга или проверенная бесплатная среда.

## Правило для исполнителя / агента
1. Сверить **текущие** main/PR/issues/CI с источниками выше: статусы здесь — snapshot на 2026-10-12, не подтверждение release.
2. Работать по очереди P0 → P1 → P2, но сначала разблокировать зависимости; не начинать следующую бизнес-цепочку, если предыдущая не доказана.
3. Для каждого пункта в PR приложить: exact SHA, файлы, миграции/API/UI связи, локальные тесты, негативные проверки прав, browser/device screenshots (если UI), DB/backup proof (если persistence), live verification (если публичный сервис), стоимость **0 ₽** с источником/лимитом.
4. Отмечать отдельно `PLANNED`, `IN_CODE`, `CI_PASS`, `LIVE_VERIFIED`, `BLOCKED`. Никогда не отмечать `DONE` только из-за документации или зелёного unit-test.
5. Сверить с существующими canonical specs/AGENTS.md; этот чеклист добавляет приоритеты и cost gate, но не заменяет доменную архитектуру/политику.

## Передача следующему проходу
- Выбирай **первый незакрытый незаблокированный** пункт P0, проверяй реальное состояние и открывай точечную реализацию, а не создавай ещё один «план без кода».
- После каждого рабочего прохода обновляй issue/PR и данный чеклист с ссылками на evidence, но не перезаписывай наблюдения устаревшим snapshot.
