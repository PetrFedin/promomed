# СОСТОЯНИЕ — Reconciled Implementation & Acceptance Register

**Review date:** 2026-10-15. **Scope:** repository `PetrFedin/promomed`; product truth and safe release planning, **not a production-ready declaration**.

## Source and methodology

- Canonical original register: `docs/PROMOMED_PRODUCT_CLOSURE_AUDIT_BACKLOG_2026-10-11.md` on `main` (114 numbered work packages). This document does **not** overwrite source plans or silently update the old status columns.
- Current `main`: `3471d05af97fe65e9e08b9da03a4c68bf81a2a78` as checked on 2026-10-15. Render public and admission service settings have not been reconciled; there is no dedicated Promomed PostgreSQL in the checked Render workspace.
- GitHub inventory: **8 open issues, 18 open PRs** at inspection. Open PR ≠ implemented in main. Workflow SUCCESS ≠ independent code review ≠ live/admitted PostgreSQL ≠ verified customer outcome.
- The baseline status distribution is reproduced exactly: LIVE-D 6, CI 12, GAP 2, CODE 44, PLAN 25, GATE 19, DEFER 6. Values reflect the 11 October evidence register, not new acceptance results.

## Findings with highest current leverage

| Priority | Unclosed work | Actual evidence / blocker | Concrete completion gate |
|---|---|---|---|
| P0 | REL-03 / Issue #64: live Render drift | Public build only `python -m py_compile server.py`; Health Check Path empty on both services. Read-only status checked via Render connector; CI contracts alone do not repair this. | Authorized patch of admission then public service, clean build with requirements, `/health`, `/ready`, exact SHA and rollback proof. |
| P0 | DB-01–06 / Issue #65: isolated durable authority | Only other-project `mfw-postgres` was visible in Render workspace, not reusable. No Promomed source+restore DSNs admitted. | New independently owned no-unapproved-cost source+restore PostgreSQL, full migrations + backup/restore fingerprints, fail-closed secrets and live non-demo SHA proof. |
| P0 | REL-02 / Issue #86: parallel PR integration | #89 partner+Client365, #91 candidate-finance+SQL lexer separately GREEN 5/5; their combined exact SHA was NOT previously proven. | This new qualification branch combines both plus #72; all suites GREEN on identical SHA, screenshots/reviews, overlap audit, no speculative merge. |
| P0 | Phase 0 evidence truth / Draft #72 | A source/restore-only CI must not emit live `production_ready=true`. | Include manifest and negative tests; keep `live_health`, `live_ready`, Render deploy and external acceptance unverified until observed. |
| P0 | DB-07–09, SEC-01–05 | GitHub demo/session/tenant tests are not actual credentials/privacy admission. | Prove real non-demo account lifecycle, tenant isolation, revocation, consent, retention/incident policy, and explicit owner sign-off. |
| P0/P1 | UX-01, PAR-01–10, OPS-01–06 | Screens, fixtures and responsive browser tests exist; no signed production walkthrough across all roles. | Execute every real user action with failure/restore in one admitted environment, include source-linked screenshots, usability review and accessibility. |
| P1 | MED-02–10, EVD-02–07 | Governance/review modules contain code and demos, no admitted external scientific authority for a real medical editorial workflow. | Real reviewer credentials, disclosures, sources, versioned decision, correction/retraction and external verification. |
| P1/P2 | COM-01–05, INS-07–12 | Partner internal task acceptance and finance candidate documents are NOT signed buyer acceptance or realized revenue. | External legal participation/scope, delivery receipt, independent Finance/bank/GL proof, repeated contract only if signed. |
| P1/P2 | KPI-01–08, investor model #71 | Investor scenarios and evidence ladders in PRs are read-only/demo; observed ARR/ROI/payments cannot be asserted. | Versioned metric dictionary, observed non-demo events and costs, trusted finance reconciliation with sample/denominator disclosure. |
| P2/P3 | Sidecars and experimental integrations | Search engine, media provider, FHIR/EHR and formal credentials are conditional; no approved adoption case. | Demand-based selection, legal terms, privacy/security ownership and evidence of value first. |

## GitHub dependency map — do not infer merge safety from CI

| Source | Role | Status at review | Admission decision |
|---|---|---|---|
| #64 and #65 | Existing Render configuration and separate PostgreSQL | OPEN | **Production HOLD** |
| #72 | Fail-closed repository-only Phase 0 evidence manifest | Draft, not main | Included in this qualification; actual live proof still missing |
| #73 → #79 → #82 → #89 | Participant/partner tasks, active tenant membership, Client365, session revocation | Draft #89 5/5 CI | Preserve partner origin, browser and Postgres tests; no externally signed partner acceptance |
| #83 → #77 → #80 → #84 → #87 → #88 → #90 → #91 | SQL lexer, organizer-only evidence, candidate finance, audit, corrections, atomic writes | #91 Draft 5/5 CI | Included in this qualification, still requires independent review |
| #71 | Investor Decision Lab / three business scenarios | Draft | Independent UI choice; not an actual investment decision, demand or valuation |
| #67, #69, #70, #85 | Safety runbook and source feature branches | Draft | Retain tested authoritative integration, avoid double-merging superseded partial implementations |

## Exact work-package inventory from canonical backlog

Legend: `Source state` is the 2026-10-11 classification, **not** automatically updated to DONE. The acceptance check is quoted/condensed from the source register. All package statuses require refreshed exact-SHA or live evidence.

### P0 — 26 work packages

| ID | Source state | Required capability | Closure proof |
|---|---|---|---|
| REL-01 | LIVE-D | Фиксировать точный Git SHA, Render deploy ID и независимые /health и /ready | SHA совпал, ready=true, production_ready честен; метки DEMO не исчезают |
| REL-02 | CI | Поддерживать обязательные UI, SQLite, PostgreSQL и responsive checks | Все проверки GREEN на том же SHA; merge запрещён после нового непроверенного commit |
| REL-03 | GAP | Устранить drift конфигурации Render build/health checks относительно render.yaml | Пакеты устанавливаются при сборке, /health настроен, restart и clean build проверены |
| REL-04 | CODE | Закрыть документационный PR #61 после проверки exact-head и отдельно вести evidence ledger | Только документ; нет ложного Phase 0 COMPLETE и дрейфа live SHA без учёта |
| DB-01 | GATE | Получить собственную PostgreSQL для Promomed, не касаясь MFW и остальных проектов | Адрес и ownership подтверждены; лимиты/расходы проверены; ни одной общей БД |
| DB-02 | GATE | Организовать физически изолированную restore database/branch | Source и restore имеют разные DSN и lifecycle; тест не повреждает source |
| DB-03 | CI | Сверить и применить 25 версионированных миграций без checksum drift | 25/25, missing=[], drift=[]; CI и внешний source дают одинаковую схему |
| DB-04 | CI | Провести полный backup → restore → fingerprint proof на внешней БД | Каталог и контрольные суммы совпадают; процедура воспроизводима и задокументирована |
| DB-05 | GATE | Привязать Render admission к прошедшему admission PostgreSQL | Никаких DSN в Git/логах; сервис не стартует ложно готовым без PostgreSQL |
| DB-06 | GATE | Развернуть admission на exact main и проверить /health и /ready | backend=postgres; durable=true; production_ready=true; demo_accounts=0; SHA exact |
| DB-07 | CI | Подтвердить реальную identity authority, ротацию пароля и отзыв сессий | Новая non-demo запись → login → rotate → старая сессия отозвана |
| DB-08 | GATE | Пройти non-demo authenticated smoke по минимальным ролям | Create/read/update/deny, restart/persistence и forbidden отрицательные сценарии пройдены |
| DB-09 | GATE | Утвердить ограниченную demo/production сегрегацию и запрет на импорт synthetic evidence | Production содержит 0 @demo.ru; демонстрационный контур сохраняется отдельно |
| DB-10 | PLAN | Определить периодический резервный экспорт, restore drill и целевые RTO/RPO пилота | Есть подписанный runbook, частота, timestamp последнего restore и измеренное время |
| DB-11 | GAP | Устранить HTTP 503 отдельного admission service после выяснения причины | Два независимых запроса /health и /ready воспроизводимо отвечают корректным статусом |
| SEC-01 | CI | Проверить RBAC по объекту и роли, включая отсутствие метаданных другой организации | 403/404 без existence leak, неверная роль не получает даже summary |
| SEC-02 | CODE | Провести threat model хранения bearer token и DOM-инъекций | XSS/auth/session replay проверены; выбран и протестирован безопасный session transport |
| SEC-03 | CODE | Протестировать lifecycle согласий: grant, withdraw, expiry, purpose, partner-bound sharing | Отзыв согласия блокирует новые выдачи и отражается в UI/API/export |
| SEC-04 | GATE | Утвердить retention, export/delete и incident response до внешних персональных данных | Policy version, retention map, deletion evidence, breach runbook и ответственные |
| SEC-05 | GATE | Завести технические секреты, роли доступа, ротацию и границы окружений | Секреты не попадают в артефакты/репозиторий; rotate/revoke tested |
| UX-01 | CODE | Создать трассировку всех 17 section screens и шести institutional pages до конечного результата | Ни одной кнопки без действия, сообщения, forbidden outcome или причины disabled |
| UX-02 | CI | Подтвердить iPhone SE/15 Pro/landscape, iPad/landscape, desktop/wide | Нет overflow, сбоев навигации, обрезки текста и touch targets меньше целевого |
| PAR-01 | LIVE-D | Замкнуть маршрут Guest → topic → content → register/login → personal Today | Гость видит контент; действия с персональными данными требуют понятной авторизации |
| MED-01 | LIVE-D | Проверить provenance каждого из 12 материалов и 5 карточек продуктов | Карточка не смешивает редакцию, партнёра и медицинское утверждение |
| EVD-01 | CI | Сохранить fail-closed Evidence Graph и Change Impact контракты | Ретракция/исправление создаёт review work, не автоматическую медицинскую истину |
| KPI-01 | CODE | Фиксировать паспорт метрик до демонстрации любых коммерческих графиков | Каждый KPI имеет владельца, единицу, формулу, срез и event source |

### P1 — 62 work packages

| ID | Source state | Required capability | Closure proof |
|---|---|---|---|
| REL-05 | CI | Проверять скриншоты как артефакты, а не считать скриншот визуальной экспертизой | 7 viewport variants; прикреплены пройденные и проваленные маршруты, замечания имеют статус |
| REL-06 | PLAN | Добавить реестр прогрессии функций: PLAN → CODE → CI → LIVE DEMO → PRODUCTION → REAL PILOT | Любое «готово» подтверждено SHA, экраном, тестом, authority и реальным контуром |
| DB-12 | PLAN | Доказать concurrency, транзакционность и идемпотентность мутирующих событий | 10+ параллельных операций не нарушают capacity, consent, state transitions |
| SEC-06 | GATE | Подготовить SBOM/CVE/dep scanning и базовые security regression checks | Pinned deps, high/critical triaged, нет необоснованной compliance claim |
| SEC-07 | PLAN | Внедрить redacted audit/trace и alerting без чувствительного содержимого | Trace показывает отказ и восстановление, не содержит PII/medical text |
| SEC-08 | PLAN | Реализовать step-up/passkeys для особо привилегированных действий | Step-up обязателен при публикации и экспорте, с audit и recovery |
| SEC-09 | GATE | Собрать честный vendor diligence pack без фиктивной сертификации | Каждый пункт: PASS / GAP / NOT_APPLICABLE и evidence URL |
| UX-03 | CODE | Разделить крупный 340 KB монолит public/index.html на модульные экраны | Совпадают DOM contracts и API, размер initial HTML и число регрессий снижаются |
| UX-04 | CODE | Заменить браузерные alert() на доступные inline/toast/error surfaces | Каждая ошибка объяснима и повторяемая, нет потери заполненной формы |
| UX-05 | CI | Продолжить focus trap/skip link/keyboard/contrast/reduced-motion проверки | Keyboard-only и screenreader smoke PASS, WCAG target определён явно |
| UX-06 | CODE | Довести фото-контекст до реального брендового набора; проверить лицензии и публичные credits | Monitor/iPad/iPhone crop review, royalty/credit basis, никакой ложной атрибуции |
| UX-07 | PLAN | Добавить RU как основной и EN как полный переключаемый интерфейс | Все ключевые маршруты RU/EN без смешанных технических заголовков |
| UX-08 | CODE | Унифицировать loading/empty/offline/permission/timeout/retry states | Отсутствие данных и ошибка не выглядят как бесконечная загрузка |
| UX-09 | PLAN | Ускорить entrypoint и вынести тяжёлые второстепенные панели в lazy loading | Измеренные LCP/INP/CLS, no-load regression в слабой сети |
| UX-10 | CI | Превратить CI screenshot inventory в human visual diff/acceptance process | Каждый значимый редизайн имеет before/after для 3 устройств и signed decision |
| PAR-02 | CODE | Проверить профиль, подписки, избранное и сохранённые материалы между сессиями | Save → reload → return имеет тот же state; чужие объекты не видны |
| PAR-03 | CODE | Довести детерминированные next-best-actions и маршрут 1/7/30 дней | Каждая рекомендация объясняется явными действиями; нет medical risk inference |
| PAR-04 | LIVE-D | Проверить 42 элемента программы, фильтры и актуальные слоты | Фильтр и карточка согласованы, даты/часовые пояса не конфликтуют |
| PAR-05 | CODE | Закрыть запись/отмену/лист ожидания и повторные обращения | Нет двойного бронирования, повторный запрос идемпотентен, waitlist fair |
| PAR-06 | CODE | Ввести conflict-aware Smart Route и next action в день события | Конфликты расписания видны, отмена/замена сохраняет историю |
| PAR-07 | GATE | Сделать проверяемый QR-пропуск (не декоративный demo QR) | Forgery, duplicate scan и offline reconciliation tests PASS |
| PAR-08 | CODE | Замкнуть attendance → replay → learning → follow-up после события | Реальная посещаемость возникает только от факта check-in, не от брони |
| PAR-09 | PLAN | Уведомления и reminders с preference/consent центром | Test receipt, opt-out and delivery failure; in-app first at zero cost |
| PAR-10 | CODE | Проверить взаимное согласие в community/личных сообщениях | Неавторизованная DM запрещена; organizer route работает и аудируется |
| MED-02 | GATE | Открыть Phase 1 controlled authoring после Phase 0 | Нельзя опубликовать без соответствующих approvals, время и автор не теряются |
| MED-03 | CODE | Довести medical/scientific reviewer authority до production credential and conflict checks | Проверка identity, qualification, scope, COI и независимости с отрицательными тестами |
| MED-04 | CODE | Сделать неизменяемые версии публикации, исправления и отзыв | Историческая версия сохраняется, публичная текущая = approved version |
| MED-05 | CODE | Укрепить полнотекстовый поиск и explainable discovery без отдельного платного сервиса | Поиск RU/EN, filters, empty/error states; no unauthorized entity discovery |
| MED-06 | CODE | Довести персональные подборки «Продолжить» с безопасным fallback | Каждая причина рекомендации выводится, no inferred treatment advice |
| MED-07 | CODE | Сделать реальные лицензированные Studio media и playback states | Play/pause, seek, subtitles, unavailable/retry, права распространения подтверждены |
| MED-08 | CODE | Протянуть транскрипты от реального медиа через review в главы/тейкауэи | Таймкоды совпадают, авторские права и review статус видны, source trace работает |
| MED-09 | CODE | Обеспечить экспертные Q&A с модерацией и безопасной публикацией | Нет персонального диагноза/назначений, конфликт интересов показан |
| MED-10 | CODE | Проверить learning progress, enrollment и связку с просмотром | Прогресс сохраняется, не возникает ложной аккредитации |
| EVD-02 | CODE | Подключить ограниченный DOI/PMID intake и нормализацию Crossref/PubMed | Hash/idempotency, attribution, rate limits, provider conflict, no auto-approve |
| EVD-03 | CODE | Развернуть управляемый scheduler для evidence-monitor-worker | Реальные timed polls, retry/backoff/dead letters; локальное CI не считается continuous |
| EVD-04 | CODE | Проверить reviewer separation и независимую credential authority | Demo approve не повышает статус до verified production review |
| EVD-05 | CI | Замкнуть source changed → claim changed → content hold → reviewed correction | Нельзя тихо удалить/перезаписать источник, история и reason код сохраняются |
| EVD-06 | CI | Принять provider outage/conflict/duplicate как честное состояние продукта | Timeout становится stale/needs-review, а не no-change; replay idempotent |
| EVD-07 | PLAN | Показать посетителю понятный Sources/Review/Disclosure блок | Доступна проверяемая ссылка, отсутствующие доказательства не маскируются |
| OPS-01 | CODE | Проверить расписание 7 залов и live session state как одно событие | Изменение видно в ops и participant UI, рассылка имеет idempotency |
| OPS-02 | CODE | Проверить staff assignments, shift conflicts и handoff | Нет назначения вне полномочий, конфликт смен виден |
| OPS-03 | CODE | Проверить capacity/queue/waitlist в режиме нескольких пользователей | Concurrency тесты исключают overbooking и потерю очереди |
| OPS-04 | CODE | Замкнуть incident → SLA → recovery → audit с эскалацией | SLA считается от факта, downstream broadcast/closure согласованы |
| OPS-05 | CODE | Отделить операционный переключатель stream status от настоящего вещания | Нельзя обозначить LIVE без реального media heartbeat; fallback есть |
| OPS-06 | PLAN | Ввести эвакуационные и недоступные venue сценарии как UX, не медицинский совет | Участник получает понятную замену/возврат, история операции сохранена |
| COM-01 | LIVE-D | Проверить пять пакетов партнёров, статус placement/deliverables | Нет обещания выполненной услуги без immutable proof |
| COM-02 | CODE | Замкнуть appointment slot → booking/waitlist → attendance → partner cockpit | Вместимость, отмена и видимость по партнёрам корректны |
| COM-03 | CODE | Сделать consent-first lead capture и revoke-safe export | Нет экспорта без согласия, revocation blocks future exports |
| COM-04 | GATE | Проверить реальную доставку partner CRM только после API/договора | Ни одного false synced и несанкционированной передачи данных |
| INS-01 | LIVE-D | Проверить рабочую навигацию из Commercial Workspace по 5 planning surfaces | Ни одна ссылка не ведёт в пустоту; auth boundaries честно отражены |
| INS-02 | CODE | Пройти Buyer Fit на типах клиника/вуз/общество/фарма/контент/стратег | Fit label не превращается в buyer intent/probability/pipeline |
| INS-03 | CODE | Проверить Pilot Proposal Studio с явно договорными полями | Pricing/duration/target остаются TO AGREE, экспорт воспроизводим |
| INS-04 | CODE | Провести рабочую сессию через Outreach/Working Session и Data Room | До реального партнёра notes/approval не пишутся как facts |
| INS-05 | CODE | Замкнуть Diligence Follow-up Board в режиме read-only | READY_FOR_DECISION никогда не равен APPROVED |
| INS-06 | CODE | Проверить Evidence Export hash binding и доступ контролируемым ролям | Stable SHA, no cross-org leaks, projection state помечен planning-only |
| INS-07 | GATE | Получить реальные требования non-demo организации и согласие на протоколирование | Клиент идентифицирован независимо; ни одного придуманного pilot commitment |
| INS-08 | GATE | Уточнить authority для Document Receipt / Review Disposition по результатам пилота | Схема и роли подтверждены реальными требованиями; нет shadow approval |
| INS-09 | GATE | Спроектировать canonical External Participation Acceptance только по реальному подписанту | Approval/action audit связывает конкретного подписанта и версию условий |
| KPI-02 | CODE | Закрыть операционную воронку регистрация → посещение → партнёр → возврат | Один participant counted once по заданному grain; отсутствующие данные ≠ 0 |
| KPI-03 | GATE | Перевести D7/D30 retention/активацию на реальные consented events | Cohorts defined, sample size visible, demo excluded from measurement |
| KPI-04 | GATE | Измерить first-value/time-to-action, user errors and support burden | No PII/medical free text in telemetry, metrics bound to scenario |
| KPI-05 | CODE | Обновить Investor/Executive/Corporate Room на проверенных состояниях | На одном экране показаны DEMO/CI/LIVE/GATED, нет invented ARR/valuation |

### P2 — 19 work packages

| ID | Source state | Required capability | Closure proof |
|---|---|---|---|
| UX-11 | PLAN | Подготовить единый visual journey для демо CEO/инвестору без технического шума | За 7–10 минут можно выполнить, а не только описать, 3 end-to-end сценария |
| PAR-11 | PLAN | Проверить реальное удержание D1/D7/D30 после event peak | Метрика только на реальных событиях, нет synthetic uplift |
| MED-11 | PLAN | Развить controlled RU/EN topic taxonomy и moderation discovery | Terms versioned, deprecation traceable, no automated medical truth |
| EVD-08 | CODE | Довести портативный Evidence Pack/verification API до внешнего независимого verifier | Offline verification of checksum, signature, status, time; no self-endorsement |
| EVD-09 | CODE | Проверить federation interoperability/discovery с настоящими ключами контрагента | Нет auto-admission; внешняя key custody и retraction/rotation evidence |
| EVD-10 | PLAN | Scientific Knowledge Graph / gap explorer только поверх проверенного evidence | Источник каждого ребра, confidence as proposal, no unsupported medical inference |
| COM-05 | PLAN | Отделить delivery evidence, коммерческий результат и гипотезу ROI | Value calculation учитывает только подтверждённые события, не demo |
| INS-10 | CODE | Проверить federation trust anchor/recipient receipts с организацией, владеющей своим ключом | Синтетические якоря не обозначаются внешним adoption |
| INS-11 | PLAN | Довести pilot contract/procurement handoff до согласованного процесса | Зафиксированы внешние решения и owners, нет pipeline или ARR из прототипа |
| INS-12 | PLAN | Провести первый платёжно-независимый институциональный proof of value | Есть внешний acceptance note и измеренная польза; стоимость может оставаться 0 |
| KPI-06 | GATE | Собрать измеренный economic case для заказчика вместо user-input-only сценария | ROI = (verified value - verified costs)/verified costs только при измеримых компонентах |
| KPI-07 | PLAN | Описать пакеты коммерциализации, без фиктивной цены/конверсии | Есть версия offer, exclusions, contract boundary, no synthetic pipeline |
| KPI-08 | PLAN | Сформировать повторяемый investor demo: 3 роли, 3 маршрута, evidence pack | Investor can trace every reported result to verified evidence |
| ADV-01 | PLAN | Внедрять Meilisearch лишь при доказанной необходимости поиска | Index rebuilt from authority, provider outage falls back to native search |
| ADV-02 | PLAN | Owncast/Video.js/Jitsi выбирать только как replaceable media adapters | Provider cannot write DB directly or become unapproved telemedicine |
| ADV-03 | PLAN | OpenTelemetry/observability в bounded tracing без медицинских текстов | Latency/error visibility, redaction tested, operating cost=0 within limits |
| ADV-04 | PLAN | Завершить DOI/Citation.js/Zotero-style export UX как derivative metadata | Формат воспроизводим; DOI не означает научно доказанный claim |
| ADV-05 | CODE | Развивать governed Evidence Syndication API только после проверенного лицензионного basis | External verification independent; partner consent and source rights valid |
| ADV-06 | PLAN | Курсы/обучение и verifiable credentials — после issuer authority | Без формального issuer/accreditation нельзя обещать баллы/сертификат |

### P3 — 7 work packages

| ID | Source state | Required capability | Closure proof |
|---|---|---|---|
| MED-12 | DEFER | Не ставить Ghost, Directus, Moodle, Discourse как параллельную authority без необходимости | Внешнее решение допускается лишь при измеренной потребности и governance review |
| EVD-11 | DEFER | Формальную клиническую FHIR/EHR интеграцию держать закрытой | Explicit clinical approval and data-protection scope before any patient data |
| INS-13 | DEFER | Не запускать аккредитацию/сертификацию и партнёрскую сеть без уполномоченных сторон | No accreditation claim until issuer/authority, standards and audits proven |
| ADV-07 | DEFER | Metarank/сложная персонализация и AI recommendation не нужны до реальных cohort signals | No inferred patient health risk; metric-backed improvement before adoption |
| ADV-08 | DEFER | Medplum/FHIR, patient records и диагностические агенты не входят в текущий продукт | Запрет сохраняется до конкретного законного сценария |
| ADV-09 | DEFER | Discourse/Moodle/Ghost parallel platforms откладываются до нагрузочных/UX обоснований | No duplicate authority, no added vendor cost without measurable benefit |
| ADV-10 | PLAN | AI summarization/NLP/knowledge graph использовать только как reviewable proposals | Логи происхождения и reviewer approve, никакой автоматической медистины |

## Quality and release instructions

1. At the integrated exact SHA, run SQLite, PostgreSQL 17, migration checksums, 026 partner+026 commercial+027+028+029, source→restore fingerprints, negative role/tenant/session tests, atomic finance fault injection, participant/partner/organizer/finance browser routes and evidence screenshot review.
2. Include deterministic non-demo fail-closed Phase 0 manifest; never mark `production_ready` from source+restore CI alone.
3. Independent human review is required for security/tenant changes, financial candidate audit and migration parser. A passing CI run is neither a human approval nor a production release.
4. Only after real permitted change to Render admission build/health and dedicated Promomed PostgreSQL admission, test public app exact SHA, cold restart, negative authorization, no demo identities and recovery.
5. Post-admission product closure sequence: real user/event journey → editorial and medical review → partner fulfilment and consent → verified institutional pilot → measured ROI and investor acceptance.
6. No live payments, clinical advice, unconsented patient data, fake evidence, automatic tranche release, reused MFW DB, paid resource or production deployment in this branch.
7. On accepted release, update `docs/IMPLEMENTED_SCOPE.md`, `docs/DEPLOYMENT_STATE.md`, `CHANGELOG.md`, the original work-package status (with proof), and the exact test/screenshot manifest.

## Acceptance state for this qualification

`CODE IN BRANCH` until the PR has exact-head CI and independent review. `PRODUCTION HOLD` remains true regardless of CI while #64/#65 and real participant/institutional authority are unresolved. This file is an audit register and does not authorize any financial or clinical business action.
