# СОСТОЯНИЕ × PROMOMED — AUDIT & PRODUCT CLOSURE MASTER BACKLOG

**Date:** 2026-10-11  
**Status:** AUDIT / ACTIONABLE ROADMAP — NOT PRODUCTION ADMISSION  
**Baseline:** `main@ae5303b3d4f28d558cf4cf35b9927da88653b4ed`  
**Source of truth:** `docs/PROMOMED_INTEGRATION_MASTER_PLAN_2026-10-01.md` + actual repository + GitHub Actions + verified Render + independent live HTTP.

## Executive conclusion

Stop adding synthetic capabilities until the existing app is production-admissible, the participant/event/partner/medical governance routes are closed end-to-end, and the first institutional buyer has produced independently attributable evidence. The existing product is a broad LIVE DEMO, not a production medical platform or verified commercial traction.

**Priority definition**: P0 = prevents reliable/safe pilot; P1 = closes core workflows; P2 = makes the platform institutionally sellable; P3 = deferred, conditional expansion.

**Evidence states**: `LIVE-D` = observed on live/demo HTTP or static page (not proof of entire clickflow); `CI` = code/test contract has a green GitHub run; `CODE` = source/in-memory/demo implementation exists, live business integration not yet verified; `GAP` = identified configuration/test discrepancy; `GATE` = required external admission not completed; `PLAN` = proposed or roadmap only; `DEFER` = deliberately outside this wave. State per row describes the relevant currently evidenced scope, **not** proof that the proposed acceptance test passed.

## Verified audit snapshot

| Evidence | Observed state | Verifiable source |
|---|---|---|
| Main SHA | `ae5303b3d4f28d558cf4cf35b9927da88653b4ed` | https://github.com/PetrFedin/promomed/commit/ae5303b3d4f28d558cf4cf35b9927da88653b4ed |
| Public Render release | `dep-db4nva7lk1mc73fd0uh0` / main SHA | Render service `srv-daug7pnlot8c73b1aja0` |
| Live `/health` | backend sqlite, durable false, demo seed true, exact SHA | https://sostoyanie-promomed-live.onrender.com/health |
| Live `/ready` | applied 25/25, no missing/drift, 11 demo accounts, ready true, production_ready false | https://sostoyanie-promomed-live.onrender.com/ready |
| Static product inventory | 42 events, 5 products, 12 materials, 10 speakers, 5 packages, 28 session-speaker links | https://sostoyanie-promomed-live.onrender.com/api/product-quality-proof |
| Continuity demo inventory | 3 Studio episodes, 4 threads, 3 tracks, 13 steps, 0 direct messages | https://sostoyanie-promomed-live.onrender.com/api/continuity-proof |
| Main branch QA | SQLite, PostgreSQL, UI, responsive browser, exact-SHA live proof: success | https://github.com/PetrFedin/promomed/actions/runs/38006961632 |
| Open docs-only PR #61 | no code changes; four PR checks green; unmerged | https://github.com/PetrFedin/promomed/pull/61 |
| PostgreSQL admission service | old SHA `657fc948...` and SQLite in last observed deployment logs; direct `/health` and `/ready` HTTP 503 on this audit, cause unconfirmed | Render `srv-davsqk942hec73e1vcr0`; https://sostoyanie-promomed-pg-admission.onrender.com/ready |
| Free Render PostgreSQL | workspace ME has `mfw-postgres`, owned by MFW, **do not reuse**; Render-reported expiry 2026-10-30 | https://dashboard.render.com/d/dpg-daugci8jo6nc738akc10-a |
| Visuals in code | four local Wikimedia photographs with attribution record; no independent human visual approval | `public/assets/editorial/ATTRIBUTION.md`; `docs/UI_SYSTEM_V2.md` |
| UI & test surface | 17 main sections, 6 dedicated institutional HTML pages; 7 viewport variants in browser suite | `public/index.html`; `tests/test_browser_responsive.py` |

**Important:** a Render `live` deploy and HTTP 200 on `/ready` do not establish durable production readiness. The strongest negative proof is `production_ready=false`. The extra 503 observation is an endpoint response only; do **not** assume the root cause without logs and reproduction.

**Zero-cost boundary:** Existing Render Free web services are suitable for testing, but Render documents ephemeral disks, idle spin-down and lack of production guarantee (https://render.com/docs/free). Neon announced on 2026-10-02 that its Free plan includes 1 GB/project and up to 100 projects (https://neon.com/blog/neon-free-plan-1-gb-per-project); this is a candidate, not an account or production SLA. Require cost ceiling, quotas, free availability and explicit owner acceptance before any provisioning. Never use MFW, Antiqua, FLASHIN or any other project's database. Real medical/PII or contractual pilots may require non-free service terms; do not mislabel a free prototype as contracted production.

## Strict critical path / dependency gates

1. **G0 — Exact truth and configuration**: REL-01 → REL-02 → REL-03/DB-11; no unverified claims in investor surfaces.
2. **G1 — Durable authority**: DB-01 → DB-02/03 → DB-04 → DB-05 → DB-06, with externally observed exact SHA and true `production_ready`.
3. **G2 — Secure non-demo operation**: DB-07/08/09 → SEC-01/02/03/04/05 → negative permissions and privacy tests.
4. **G3 — Operational journeys**: UX-01/02/08 + PAR-01..10 + OPS-01..06 + COM-01..03. All core actions have success, failure, consent and rollback evidence.
5. **G4 — Medical/editorial authority**: MED-02/03/04 → EVD-02/03/04/05 → MED-07/08/09. No unchecked publication or medical inference.
6. **G5 — Non-demo institutional pilot**: INS-01..06 (planning) → INS-07 real external evidence → INS-08/09 externally authorized admissions → measured KPI-03/04/06.
7. **G6 — Enterprise/investor proof**: INS-12 + KPI-06/07/08 + SEC-09. Real customer/value claims must be source-linked.

**No invented schedule**: engineering work can run in parallel only if its prerequisites and owners are explicit. No automatic merge/deploy or real participant data admission is authorized by this document.

## Functional source-of-truth boundaries

| Domain | Owner/authority | Read consumers and integrations | Forbidden alternative truth |
|---|---|---|---|
| Accounts, sessions, consent | Native PostgreSQL auth/profile/consent | participant UI, message, CRM, study/pilot | third-party CRM overwrites consent or demo account appears in production |
| Programme, booking, waitlist, QR | Native programme/booking/attendance | participant calendar, organizer ops, partner appointment | viewer clicks or seeded schedules counted as attendance |
| Content, editorial, medical review | Native immutable published snapshots; reviewer credentials | public Media, Studio, Q&A, search | metadata importer approves claims |
| Evidence, claims, monitoring | Evidence Graph + Admission + qualified reviewer | knowledge surfaces, change impact, investor verification | Crossref/PubMed changes directly publish treatment claims |
| Studio/replay | Promomed media authority + provider adapter | player, captions, learning, 1/7/30 | provider stream state becomes clinical or attendance authority |
| Operations and incidents | Native operational domain and event ledger | venue, staff, broadcasts, KPI | manually shown LIVE badge proves working stream |
| Partner & commercial | Promomed consented engagement and delivery evidence | scoped CRM export, partner cockpit, analytics | external CRM overwrites Promomed participant facts |
| Institution/federation | Native institutional authority and independent counterpart key custody | procurement pack, trust bundle, verifier | demo compatibility implies institutional adoption |
| Investor readiness/KPI | Verified event ledger + definitions + evidence receipts | executive/corporate room; export | scenario assumptions become ARR, actual revenue or medical outcome |

## End-to-end proof routes (must be executable)

1. **Participant**: Guest → topic → cited content → login → save → registration → conflict-aware route → booking → signed QR → check-in → confirmed attendance → replay/learning → consented 1/7/30 continuation. Negative: cancelled event, duplicate QR, offline/timeout, consent withdrawal.
2. **Organiser & staff**: publish programme → allocate people/room → admit check-in → capacity+waitlist → incident → broadcast → mitigation → recovery evidence → dashboard. Negative: oversubscribed booking, revoked staff role, stream-provider outage.
3. **Editor/scientific reviewer**: new draft → claim → DOI/PMID metadata → evidence link → disclosure → distinct qualified reviews → approved publication → provider retraction → review queue → content hold → correction/withdrawal with history. Negative: same actor bypasses approval, source outage, forged reviewer.
4. **Partner**: approved package → slot → attendee booking → actual visit → explicit consent → lead export → delivery ACK → partner report → independently verified outcome. Negative: consent revoked, cross-partner data request, duplicate retry.
5. **Institutional buyer**: Buyer Fit → Proposal → Outreach → verified institutional contact → Working Session → evidence requests → Receipt/Review authority **only when justified** → approved scope → documented participation → federation/exchange proof → pilot result. Negative: demo identity/compatibility treated as signed adoption.
6. **CEO/investor**: capability truth → demo interaction → measurable KPI definition → evidence pack → blockers → milestone decision → negotiated next step. Negative: fabricated ROI/ARR/contract or silently approved deal.

## Work register (grouped by implementation order)

Execution order within P0 precedes any production data ingestion. `Dependency` entries refer to this register. Each PASS criterion requires a screenshot/test ID or live log/SHA evidence, not self-declared completion.

### 00 — Истина релиза и управляемость изменений

| Priority / ID | Evidence state | Work and expected capability | Integration / source of truth | Completion test | Depends on |
|---|---|---|---|---|---|
| **P0 REL-01** | LIVE-D | Фиксировать точный Git SHA, Render deploy ID и независимые /health и /ready | GitHub main → Render → публичные HTTP responses | SHA совпал, ready=true, production_ready честен; метки DEMO не исчезают | — |
| **P0 REL-02** | CI | Поддерживать обязательные UI, SQLite, PostgreSQL и responsive checks | PR exact-head → GitHub Actions → release admission | Все проверки GREEN на том же SHA; merge запрещён после нового непроверенного commit | REL-01 |
| **P0 REL-03** | GAP | Устранить drift конфигурации Render build/health checks относительно render.yaml | Render existing public/admission services и requirements.txt | Пакеты устанавливаются при сборке, /health настроен, restart и clean build проверены | REL-01 |
| **P0 REL-04** | CODE | Закрыть документационный PR #61 после проверки exact-head и отдельно вести evidence ledger | docs/DEPLOYMENT_STATE.md, PR #61, Release Protocol | Только документ; нет ложного Phase 0 COMPLETE и дрейфа live SHA без учёта | REL-02 |
| **P1 REL-05** | CI | Проверять скриншоты как артефакты, а не считать скриншот визуальной экспертизой | GitHub browser QA artifact → human comparison → defect ticket | 7 viewport variants; прикреплены пройденные и проваленные маршруты, замечания имеют статус | REL-02 |
| **P1 REL-06** | PLAN | Добавить реестр прогрессии функций: PLAN → CODE → CI → LIVE DEMO → PRODUCTION → REAL PILOT | Master Plan, Implemented Scope, Deployment State, changelog | Любое «готово» подтверждено SHA, экраном, тестом, authority и реальным контуром | REL-01 |

### 01 — Phase 0: постоянные данные и инфраструктура

| Priority / ID | Evidence state | Work and expected capability | Integration / source of truth | Completion test | Depends on |
|---|---|---|---|---|---|
| **P0 DB-01** | GATE | Получить собственную PostgreSQL для Promomed, не касаясь MFW и остальных проектов | Neon Free Frankfurt или эквивалент, отдельный проект и роли | Адрес и ownership подтверждены; лимиты/расходы проверены; ни одной общей БД | REL-03 |
| **P0 DB-02** | GATE | Организовать физически изолированную restore database/branch | PostgreSQL source → pg_dump → second isolated PostgreSQL | Source и restore имеют разные DSN и lifecycle; тест не повреждает source | DB-01 |
| **P0 DB-03** | CI | Сверить и применить 25 версионированных миграций без checksum drift | migrations/postgres, _schema_migrations, db.migrate | 25/25, missing=[], drift=[]; CI и внешний source дают одинаковую схему | DB-01 |
| **P0 DB-04** | CI | Провести полный backup → restore → fingerprint proof на внешней БД | ops/phase0_postgres_admission.py, db_backup_restore.py, db_catalog_fingerprint.py | Каталог и контрольные суммы совпадают; процедура воспроизводима и задокументирована | DB-02, DB-03 |
| **P0 DB-05** | GATE | Привязать Render admission к прошедшему admission PostgreSQL | DATABASE_URL в секретах Render, PROMOMED_REQUIRE_POSTGRES=true, SEED_DEMO=false | Никаких DSN в Git/логах; сервис не стартует ложно готовым без PostgreSQL | DB-04, REL-03 |
| **P0 DB-06** | GATE | Развернуть admission на exact main и проверить /health и /ready | Render service, live HTTP proof и GitHub Phase 0 proof workflow | backend=postgres; durable=true; production_ready=true; demo_accounts=0; SHA exact | DB-05 |
| **P0 DB-07** | CI | Подтвердить реальную identity authority, ротацию пароля и отзыв сессий | accounts, auth_sessions, scrypt, ops/provision_account.py | Новая non-demo запись → login → rotate → старая сессия отозвана | DB-06 |
| **P0 DB-08** | GATE | Пройти non-demo authenticated smoke по минимальным ролям | Live PostgreSQL, organizer/participant scopes, sessions, API | Create/read/update/deny, restart/persistence и forbidden отрицательные сценарии пройдены | DB-07 |
| **P0 DB-09** | GATE | Утвердить ограниченную demo/production сегрегацию и запрет на импорт synthetic evidence | Seed flags, миграции, demo fixtures, admission service | Production содержит 0 @demo.ru; демонстрационный контур сохраняется отдельно | DB-08 |
| **P0 DB-10** | PLAN | Определить периодический резервный экспорт, restore drill и целевые RTO/RPO пилота | Source DB → резервное хранилище → независимое восстановление → owner sign-off | Есть подписанный runbook, частота, timestamp последнего restore и измеренное время | DB-04 |
| **P0 DB-11** | GAP | Устранить HTTP 503 отдельного admission service после выяснения причины | Render events/logs, service status, cold-start, runtime, port, configuration | Два независимых запроса /health и /ready воспроизводимо отвечают корректным статусом | REL-03 |
| **P1 DB-12** | PLAN | Доказать concurrency, транзакционность и идемпотентность мутирующих событий | Register/booking/waitlist/lead/evidence/outbox/retry на PostgreSQL | 10+ параллельных операций не нарушают capacity, consent, state transitions | DB-08 |

### 02 — Безопасность, конфиденциальность, identity и права

| Priority / ID | Evidence state | Work and expected capability | Integration / source of truth | Completion test | Depends on |
|---|---|---|---|---|---|
| **P0 SEC-01** | CI | Проверить RBAC по объекту и роли, включая отсутствие метаданных другой организации | Role × resource × tenant matrix, GET/POST negative tests | 403/404 без existence leak, неверная роль не получает даже summary | DB-08 |
| **P0 SEC-02** | CODE | Провести threat model хранения bearer token и DOM-инъекций | public/index.html localStorage + inline handlers + template HTML; app/auth.py | XSS/auth/session replay проверены; выбран и протестирован безопасный session transport | SEC-01 |
| **P0 SEC-03** | CODE | Протестировать lifecycle согласий: grant, withdraw, expiry, purpose, partner-bound sharing | Partner leads, profile, messaging, notifications, audit events | Отзыв согласия блокирует новые выдачи и отражается в UI/API/export | SEC-01 |
| **P0 SEC-04** | GATE | Утвердить retention, export/delete и incident response до внешних персональных данных | Data inventory, privacy documents, operations owner, security/legal review | Policy version, retention map, deletion evidence, breach runbook и ответственные | DB-08 |
| **P0 SEC-05** | GATE | Завести технические секреты, роли доступа, ротацию и границы окружений | GitHub secrets, Render secret env, PostgreSQL roles | Секреты не попадают в артефакты/репозиторий; rotate/revoke tested | DB-05 |
| **P1 SEC-06** | GATE | Подготовить SBOM/CVE/dep scanning и базовые security regression checks | requirements.txt, GitHub Actions, external dependency manifests | Pinned deps, high/critical triaged, нет необоснованной compliance claim | REL-02 |
| **P1 SEC-07** | PLAN | Внедрить redacted audit/trace и alerting без чувствительного содержимого | request ID → actor scope → command → DB → provider → outcome | Trace показывает отказ и восстановление, не содержит PII/medical text | SEC-04 |
| **P1 SEC-08** | PLAN | Реализовать step-up/passkeys для особо привилегированных действий | Organizer, reviewer, editor, lead export, role change | Step-up обязателен при публикации и экспорте, с audit и recovery | SEC-02, MED-03 |
| **P1 SEC-09** | GATE | Собрать честный vendor diligence pack без фиктивной сертификации | DPA/SLA, subprocessors, storage/retention, recovery/SLO, legal owner | Каждый пункт: PASS / GAP / NOT_APPLICABLE и evidence URL | SEC-04, DB-10 |

### 03 — UX, визуальная система, доступность и платформа экранов

| Priority / ID | Evidence state | Work and expected capability | Integration / source of truth | Completion test | Depends on |
|---|---|---|---|---|---|
| **P0 UX-01** | CODE | Создать трассировку всех 17 section screens и шести institutional pages до конечного результата | UI button → API → authority → UI success/error → audit | Ни одной кнопки без действия, сообщения, forbidden outcome или причины disabled | REL-05 |
| **P0 UX-02** | CI | Подтвердить iPhone SE/15 Pro/landscape, iPad/landscape, desktop/wide | Playwright 7 viewports; real-device visual acceptance отдельно | Нет overflow, сбоев навигации, обрезки текста и touch targets меньше целевого | UX-01 |
| **P1 UX-03** | CODE | Разделить крупный 340 KB монолит public/index.html на модульные экраны | Design tokens, reusable components, bundle strategy без новых authority | Совпадают DOM contracts и API, размер initial HTML и число регрессий снижаются | UX-01 |
| **P1 UX-04** | CODE | Заменить браузерные alert() на доступные inline/toast/error surfaces | Form submit, provider failure, booking, evidence, ops | Каждая ошибка объяснима и повторяемая, нет потери заполненной формы | UX-03 |
| **P1 UX-05** | CI | Продолжить focus trap/skip link/keyboard/contrast/reduced-motion проверки | Main participant shell + six institutional pages | Keyboard-only и screenreader smoke PASS, WCAG target определён явно | UX-02 |
| **P1 UX-06** | CODE | Довести фото-контекст до реального брендового набора; проверить лицензии и публичные credits | 4 locally vendored Wikimedia assets, attribution, Promomed brand review | Monitor/iPad/iPhone crop review, royalty/credit basis, никакой ложной атрибуции | UX-02 |
| **P1 UX-07** | PLAN | Добавить RU как основной и EN как полный переключаемый интерфейс | Translation keys, error strings, editorial locale, date/time and search | Все ключевые маршруты RU/EN без смешанных технических заголовков | UX-03 |
| **P1 UX-08** | CODE | Унифицировать loading/empty/offline/permission/timeout/retry states | Today, Media, Events, Community, My, institutional pages | Отсутствие данных и ошибка не выглядят как бесконечная загрузка | UX-01 |
| **P1 UX-09** | PLAN | Ускорить entrypoint и вынести тяжёлые второстепенные панели в lazy loading | Home and account priority; network/performance budgets | Измеренные LCP/INP/CLS, no-load regression в слабой сети | UX-03 |
| **P1 UX-10** | CI | Превратить CI screenshot inventory в human visual diff/acceptance process | GitHub artifacts, human review, defect tracker and QA sign-off | Каждый значимый редизайн имеет before/after для 3 устройств и signed decision | REL-05 |
| **P2 UX-11** | PLAN | Подготовить единый visual journey для демо CEO/инвестору без технического шума | Role-based guided demo → evidence state → next action | За 7–10 минут можно выполнить, а не только описать, 3 end-to-end сценария | UX-08, KPI-05 |

### 04 — Participant / конференция / Relationship 365

| Priority / ID | Evidence state | Work and expected capability | Integration / source of truth | Completion test | Depends on |
|---|---|---|---|---|---|
| **P0 PAR-01** | LIVE-D | Замкнуть маршрут Guest → topic → content → register/login → personal Today | Guest homepage, registration, accounts, profile | Гость видит контент; действия с персональными данными требуют понятной авторизации | UX-01 |
| **P1 PAR-02** | CODE | Проверить профиль, подписки, избранное и сохранённые материалы между сессиями | Profile + discovery saves + subscriptions + PostgreSQL | Save → reload → return имеет тот же state; чужие объекты не видны | DB-08, SEC-01 |
| **P1 PAR-03** | CODE | Довести детерминированные next-best-actions и маршрут 1/7/30 дней | Personalization / journey365 → Today UI → action receipts | Каждая рекомендация объясняется явными действиями; нет medical risk inference | PAR-02 |
| **P1 PAR-04** | LIVE-D | Проверить 42 элемента программы, фильтры и актуальные слоты | program_items, rooms, speakers, participant schedule | Фильтр и карточка согласованы, даты/часовые пояса не конфликтуют | DB-08 |
| **P1 PAR-05** | CODE | Закрыть запись/отмену/лист ожидания и повторные обращения | Registration + activity/appointment bookings + capacity authority | Нет двойного бронирования, повторный запрос идемпотентен, waitlist fair | PAR-04, DB-12 |
| **P1 PAR-06** | CODE | Ввести conflict-aware Smart Route и next action в день события | Schedule items + booking + venue availability + QR wallet | Конфликты расписания видны, отмена/замена сохраняет историю | PAR-05 |
| **P1 PAR-07** | GATE | Сделать проверяемый QR-пропуск (не декоративный demo QR) | Ticket identity + signed short-lived claim + scanner/check-in | Forgery, duplicate scan и offline reconciliation tests PASS | PAR-05, SEC-02 |
| **P1 PAR-08** | CODE | Замкнуть attendance → replay → learning → follow-up после события | Check-in/attendance + Studio + learning + Journey365 | Реальная посещаемость возникает только от факта check-in, не от брони | PAR-07, MED-08 |
| **P1 PAR-09** | PLAN | Уведомления и reminders с preference/consent центром | Event time change, waitlist, replay, topic alerts, notification journal | Test receipt, opt-out and delivery failure; in-app first at zero cost | PAR-05, SEC-03 |
| **P1 PAR-10** | CODE | Проверить взаимное согласие в community/личных сообщениях | Accounts + mutual meetings + direct_messages + moderation | Неавторизованная DM запрещена; organizer route работает и аудируется | SEC-01 |
| **P2 PAR-11** | PLAN | Проверить реальное удержание D1/D7/D30 после event peak | Event-level cohorts and Journey365 interaction events | Метрика только на реальных событиях, нет synthetic uplift | KPI-03 |

### 05 — Media / Studio / editorial / discovery / обучение

| Priority / ID | Evidence state | Work and expected capability | Integration / source of truth | Completion test | Depends on |
|---|---|---|---|---|---|
| **P0 MED-01** | LIVE-D | Проверить provenance каждого из 12 материалов и 5 карточек продуктов | Content and product catalogs + source/disclosure metadata | Карточка не смешивает редакцию, партнёра и медицинское утверждение | SEC-03 |
| **P1 MED-02** | GATE | Открыть Phase 1 controlled authoring после Phase 0 | Draft → editorial → medical → compliance → approve → publish | Нельзя опубликовать без соответствующих approvals, время и автор не теряются | DB-09 |
| **P1 MED-03** | CODE | Довести medical/scientific reviewer authority до production credential and conflict checks | app/reviewer_authority → editorial/claim admission | Проверка identity, qualification, scope, COI и независимости с отрицательными тестами | MED-02 |
| **P1 MED-04** | CODE | Сделать неизменяемые версии публикации, исправления и отзыв | Content snapshot, SHA-256, citation/claim/reviewer/disclosure versions | Историческая версия сохраняется, публичная текущая = approved version | MED-03 |
| **P1 MED-05** | CODE | Укрепить полнотекстовый поиск и explainable discovery без отдельного платного сервиса | Existing discovery_reads → indexed content with reviewed facts | Поиск RU/EN, filters, empty/error states; no unauthorized entity discovery | MED-04, UX-08 |
| **P1 MED-06** | CODE | Довести персональные подборки «Продолжить» с безопасным fallback | User explicit interests + saved items + topic vocabulary | Каждая причина рекомендации выводится, no inferred treatment advice | MED-05, PAR-03 |
| **P1 MED-07** | CODE | Сделать реальные лицензированные Studio media и playback states | Studio episodes → video/captions provider adapter → replay page | Play/pause, seek, subtitles, unavailable/retry, права распространения подтверждены | MED-04 |
| **P1 MED-08** | CODE | Протянуть транскрипты от реального медиа через review в главы/тейкауэи | Media asset → transcript segments → source provenance → editorial approval | Таймкоды совпадают, авторские права и review статус видны, source trace работает | MED-07, MED-03 |
| **P1 MED-09** | CODE | Обеспечить экспертные Q&A с модерацией и безопасной публикацией | Question queue → assigned expert → reviewed answer → published version | Нет персонального диагноза/назначений, конфликт интересов показан | MED-03 |
| **P1 MED-10** | CODE | Проверить learning progress, enrollment и связку с просмотром | 3 tracks, 13 steps, progress/attendance/journey states | Прогресс сохраняется, не возникает ложной аккредитации | DB-08, PAR-08 |
| **P2 MED-11** | PLAN | Развить controlled RU/EN topic taxonomy и moderation discovery | Source/claim/learning/expert/topic mapping | Terms versioned, deprecation traceable, no automated medical truth | MED-05 |
| **P3 MED-12** | DEFER | Не ставить Ghost, Directus, Moodle, Discourse как параллельную authority без необходимости | Existing CMS/community/learning canonical boundaries | Внешнее решение допускается лишь при измеренной потребности и governance review | MED-02 |

### 06 — Scientific Evidence / знания / непрерывный контроль

| Priority / ID | Evidence state | Work and expected capability | Integration / source of truth | Completion test | Depends on |
|---|---|---|---|---|---|
| **P0 EVD-01** | CI | Сохранить fail-closed Evidence Graph и Change Impact контракты | Claims ↔ evidence sources ↔ content ↔ impact holds | Ретракция/исправление создаёт review work, не автоматическую медицинскую истину | MED-01 |
| **P1 EVD-02** | CODE | Подключить ограниченный DOI/PMID intake и нормализацию Crossref/PubMed | Official APIs → immutable provider snapshots → admission candidate | Hash/idempotency, attribution, rate limits, provider conflict, no auto-approve | DB-08, MED-03 |
| **P1 EVD-03** | CODE | Развернуть управляемый scheduler для evidence-monitor-worker | PostgreSQL monitor jobs + scheduled execution + metrics | Реальные timed polls, retry/backoff/dead letters; локальное CI не считается continuous | EVD-02 |
| **P1 EVD-04** | CODE | Проверить reviewer separation и независимую credential authority | Evidence admission candidate → editorial+scientific qualified approvals | Demo approve не повышает статус до verified production review | MED-03, EVD-03 |
| **P1 EVD-05** | CI | Замкнуть source changed → claim changed → content hold → reviewed correction | Evidence Graph + Change Impact + published versions | Нельзя тихо удалить/перезаписать источник, история и reason код сохраняются | EVD-04, MED-04 |
| **P1 EVD-06** | CI | Принять provider outage/conflict/duplicate как честное состояние продукта | Provider error journal + snapshots + retry/DLQ + UI | Timeout становится stale/needs-review, а не no-change; replay idempotent | EVD-03 |
| **P1 EVD-07** | PLAN | Показать посетителю понятный Sources/Review/Disclosure блок | Claim citations + responsible reviewer + conflict and correction version | Доступна проверяемая ссылка, отсутствующие доказательства не маскируются | EVD-05 |
| **P2 EVD-08** | CODE | Довести портативный Evidence Pack/verification API до внешнего независимого verifier | Evidence export, status snapshots, trusted issuer key registry | Offline verification of checksum, signature, status, time; no self-endorsement | EVD-05 |
| **P2 EVD-09** | CODE | Проверить federation interoperability/discovery с настоящими ключами контрагента | Institution anchor + DID/JWKS + proof-of-possession + admission | Нет auto-admission; внешняя key custody и retraction/rotation evidence | INS-10 |
| **P2 EVD-10** | PLAN | Scientific Knowledge Graph / gap explorer только поверх проверенного evidence | Topic/entity/claim/source/review versions, graph queries | Источник каждого ребра, confidence as proposal, no unsupported medical inference | EVD-07 |
| **P3 EVD-11** | DEFER | Формальную клиническую FHIR/EHR интеграцию держать закрытой | Only real authorised healthcare use case + legal/privacy architecture | Explicit clinical approval and data-protection scope before any patient data | SEC-04 |

### 07 — Operations / площадка / событие / партнёры

| Priority / ID | Evidence state | Work and expected capability | Integration / source of truth | Completion test | Depends on |
|---|---|---|---|---|---|
| **P1 OPS-01** | CODE | Проверить расписание 7 залов и live session state как одно событие | Program → venue state → organizer control → attendee screens | Изменение видно в ops и participant UI, рассылка имеет idempotency | PAR-04 |
| **P1 OPS-02** | CODE | Проверить staff assignments, shift conflicts и handoff | Staff roster + access roles + event assignments | Нет назначения вне полномочий, конфликт смен виден | SEC-01 |
| **P1 OPS-03** | CODE | Проверить capacity/queue/waitlist в режиме нескольких пользователей | Venue occupancy, booking, check-in and promotion | Concurrency тесты исключают overbooking и потерю очереди | DB-12, PAR-05 |
| **P1 OPS-04** | CODE | Замкнуть incident → SLA → recovery → audit с эскалацией | Incident severity + owner + notification + immutable event | SLA считается от факта, downstream broadcast/closure согласованы | SEC-07 |
| **P1 OPS-05** | CODE | Отделить операционный переключатель stream status от настоящего вещания | stream_state → real stream provider + monitoring health | Нельзя обозначить LIVE без реального media heartbeat; fallback есть | MED-07 |
| **P1 OPS-06** | PLAN | Ввести эвакуационные и недоступные venue сценарии как UX, не медицинский совет | Venue closures → ticket route/participant notification | Участник получает понятную замену/возврат, история операции сохранена | OPS-03, PAR-09 |
| **P1 COM-01** | LIVE-D | Проверить пять пакетов партнёров, статус placement/deliverables | Partner catalog → contracted placement → delivery evidence | Нет обещания выполненной услуги без immutable proof | SEC-03 |
| **P1 COM-02** | CODE | Замкнуть appointment slot → booking/waitlist → attendance → partner cockpit | Appointment Desk, schedule, partner scoped reports | Вместимость, отмена и видимость по партнёрам корректны | OPS-03 |
| **P1 COM-03** | CODE | Сделать consent-first lead capture и revoke-safe export | Event participation → explicit purpose consent → scoped lead | Нет экспорта без согласия, revocation blocks future exports | SEC-03, COM-02 |
| **P1 COM-04** | GATE | Проверить реальную доставку partner CRM только после API/договора | Consented facts → outbox → external CRM ACK/NAK → reconciliation | Ни одного false synced и несанкционированной передачи данных | COM-03, SEC-04 |
| **P2 COM-05** | PLAN | Отделить delivery evidence, коммерческий результат и гипотезу ROI | Partner fulfilment → lead → follow-up → verified outcome | Value calculation учитывает только подтверждённые события, не demo | COM-04, KPI-03 |

### 08 — Институциональный клиент / корпоративная продажа

| Priority / ID | Evidence state | Work and expected capability | Integration / source of truth | Completion test | Depends on |
|---|---|---|---|---|---|
| **P1 INS-01** | LIVE-D | Проверить рабочую навигацию из Commercial Workspace по 5 planning surfaces | Buyer Fit → Proposal → Outreach → Command Center → Export | Ни одна ссылка не ведёт в пустоту; auth boundaries честно отражены | UX-01 |
| **P1 INS-02** | CODE | Пройти Buyer Fit на типах клиника/вуз/общество/фарма/контент/стратег | Institution buyer matrix + reviewed product capabilities | Fit label не превращается в buyer intent/probability/pipeline | INS-01 |
| **P1 INS-03** | CODE | Проверить Pilot Proposal Studio с явно договорными полями | Archetype → scopes → customer inputs → KPI formulas → pre-contract | Pricing/duration/target остаются TO AGREE, экспорт воспроизводим | INS-02 |
| **P1 INS-04** | CODE | Провести рабочую сессию через Outreach/Working Session и Data Room | Agenda, owner, question, evidence gap, source exports | До реального партнёра notes/approval не пишутся как facts | INS-03 |
| **P1 INS-05** | CODE | Замкнуть Diligence Follow-up Board в режиме read-only | Request → gap → owner queue → READY_FOR_DECISION | READY_FOR_DECISION никогда не равен APPROVED | INS-04 |
| **P1 INS-06** | CODE | Проверить Evidence Export hash binding и доступ контролируемым ролям | Buyer+proposal+outreach source snapshots → export package | Stable SHA, no cross-org leaks, projection state помечен planning-only | INS-03, SEC-01 |
| **P1 INS-07** | GATE | Получить реальные требования non-demo организации и согласие на протоколирование | Real contact/mandate → controlled interview/UAT → attributable evidence | Клиент идентифицирован независимо; ни одного придуманного pilot commitment | DB-08, INS-04 |
| **P1 INS-08** | GATE | Уточнить authority для Document Receipt / Review Disposition по результатам пилота | Real institutional requested docs → receipt → reviewer → decision | Схема и роли подтверждены реальными требованиями; нет shadow approval | INS-07 |
| **P1 INS-09** | GATE | Спроектировать canonical External Participation Acceptance только по реальному подписанту | Non-demo institution identity + authorised party + evidence + scope | Approval/action audit связывает конкретного подписанта и версию условий | INS-08, SEC-04 |
| **P2 INS-10** | CODE | Проверить federation trust anchor/recipient receipts с организацией, владеющей своим ключом | Institution public keys + PoP + revocation/status + verification | Синтетические якоря не обозначаются внешним adoption | INS-09 |
| **P2 INS-11** | PLAN | Довести pilot contract/procurement handoff до согласованного процесса | Signed scope, success targets, RACI, DPIA/DPA/SLA, support | Зафиксированы внешние решения и owners, нет pipeline или ARR из прототипа | INS-09, SEC-09 |
| **P2 INS-12** | PLAN | Провести первый платёжно-независимый институциональный proof of value | Qualified pilot → deployment → user outcomes → evidence receipts | Есть внешний acceptance note и измеренная польза; стоимость может оставаться 0 | INS-11, KPI-04 |
| **P3 INS-13** | DEFER | Не запускать аккредитацию/сертификацию и партнёрскую сеть без уполномоченных сторон | Open Badges, syndication, certification and trust graph | No accreditation claim until issuer/authority, standards and audits proven | INS-12 |

### 09 — Аналитика, экономика и инвестиционная готовность

| Priority / ID | Evidence state | Work and expected capability | Integration / source of truth | Completion test | Depends on |
|---|---|---|---|---|---|
| **P0 KPI-01** | CODE | Фиксировать паспорт метрик до демонстрации любых коммерческих графиков | Event ledger → denominator → definition/version → evidence URL | Каждый KPI имеет владельца, единицу, формулу, срез и event source | SEC-03 |
| **P1 KPI-02** | CODE | Закрыть операционную воронку регистрация → посещение → партнёр → возврат | Registration, attendance, consent, follow-up, replay | Один participant counted once по заданному grain; отсутствующие данные ≠ 0 | DB-08, PAR-08 |
| **P1 KPI-03** | GATE | Перевести D7/D30 retention/активацию на реальные consented events | Journey365 + cohort identity + clean prod data | Cohorts defined, sample size visible, demo excluded from measurement | KPI-02 |
| **P1 KPI-04** | GATE | Измерить first-value/time-to-action, user errors and support burden | Participant/ops/corporate UX event instrumentation | No PII/medical free text in telemetry, metrics bound to scenario | UX-10, KPI-02 |
| **P1 KPI-05** | CODE | Обновить Investor/Executive/Corporate Room на проверенных состояниях | Readiness + risk register + milestone gating + accepted evidence | На одном экране показаны DEMO/CI/LIVE/GATED, нет invented ARR/valuation | REL-01, KPI-01 |
| **P2 KPI-06** | GATE | Собрать измеренный economic case для заказчика вместо user-input-only сценария | Baseline → observed time/quality/revenue proxy → source proof | ROI = (verified value - verified costs)/verified costs только при измеримых компонентах | INS-12, KPI-03 |
| **P2 KPI-07** | PLAN | Описать пакеты коммерциализации, без фиктивной цены/конверсии | Annual licence, event operating package, partner activation, syndication | Есть версия offer, exclusions, contract boundary, no synthetic pipeline | KPI-06 |
| **P2 KPI-08** | PLAN | Сформировать повторяемый investor demo: 3 роли, 3 маршрута, evidence pack | Participant + organizer + buyer → measurable outcome → signed acceptance | Investor can trace every reported result to verified evidence | KPI-05, INS-12 |

### 10 — Интеграции и инновации после подтверждения спроса

| Priority / ID | Evidence state | Work and expected capability | Integration / source of truth | Completion test | Depends on |
|---|---|---|---|---|---|
| **P2 ADV-01** | PLAN | Внедрять Meilisearch лишь при доказанной необходимости поиска | Promomed canonical content → rebuildable search sidecar | Index rebuilt from authority, provider outage falls back to native search | MED-05 |
| **P2 ADV-02** | PLAN | Owncast/Video.js/Jitsi выбирать только как replaceable media adapters | Media governance → provider → player/event room → attendance link | Provider cannot write DB directly or become unapproved telemedicine | MED-07, SEC-04 |
| **P2 ADV-03** | PLAN | OpenTelemetry/observability в bounded tracing без медицинских текстов | API → auth/consent → domain → DB/provider → response | Latency/error visibility, redaction tested, operating cost=0 within limits | SEC-07 |
| **P2 ADV-04** | PLAN | Завершить DOI/Citation.js/Zotero-style export UX как derivative metadata | Reviewed citations + source identifier + CSL metadata | Формат воспроизводим; DOI не означает научно доказанный claim | EVD-07 |
| **P2 ADV-05** | CODE | Развивать governed Evidence Syndication API только после проверенного лицензионного basis | Publisher/Consumer roles, signed package, contract and revocation | External verification independent; partner consent and source rights valid | INS-10, EVD-08 |
| **P2 ADV-06** | PLAN | Курсы/обучение и verifiable credentials — после issuer authority | Completed learning evidence → approved issuer → signed credential | Без формального issuer/accreditation нельзя обещать баллы/сертификат | MED-10, INS-12 |
| **P3 ADV-07** | DEFER | Metarank/сложная персонализация и AI recommendation не нужны до реальных cohort signals | User explicit interests → verified behavior → explainable ranking | No inferred patient health risk; metric-backed improvement before adoption | KPI-03 |
| **P3 ADV-08** | DEFER | Medplum/FHIR, patient records и диагностические агенты не входят в текущий продукт | Separate clinical purpose, consent, security, clinical governance | Запрет сохраняется до конкретного законного сценария | SEC-04 |
| **P3 ADV-09** | DEFER | Discourse/Moodle/Ghost parallel platforms откладываются до нагрузочных/UX обоснований | Native community, learning, editorial remain source of truth | No duplicate authority, no added vendor cost without measurable benefit | KPI-04 |
| **P3 ADV-10** | PLAN | AI summarization/NLP/knowledge graph использовать только как reviewable proposals | Approved text → candidate term/summary → human review → publication | Логи происхождения и reviewer approve, никакой автоматической медистины | MED-03, EVD-10 |

## Focused acceptance matrix by role (minimum)

| Role | Successful flow | Required failure/negative proof | Devices |
|---|---|---|---|
| Guest | Home → Media → topic → programme → non-private CTA | cannot read profile/lead/booking and no forced login just for reading | iPhone, iPad, desktop |
| Participant | login → save → booking → schedule → QR → replay → follow-up | invalid token, duplicate booking, capacity full, withdrawn consent, offline | iPhone, tablet |
| Staff | shift → scan → check-in → incident escalation | invalid QR, repeat scan, no venue scope, expired staff session | iPhone landscape, tablet |
| Organizer | create/update schedule → venue state → broadcast → recovery | role denial, concurrency/retry duplication, provider outage | tablet, monitor |
| Editor / scientific reviewer | draft → source → disclosure → distinct review → approve/correct | forged credential, expired scope, same-actor bypass, retracted source | monitor |
| Partner / sales | appointment → consented lead → scoped outcome/receipt | external partner sees another partner's data; consent removed | iPad, desktop |
| Corporate / buyer | Buyer Fit → Proposal → Outreach → Export → Diligence | non-demo identity absent, no contract/ARR, READY_FOR_DECISION ≠ APPROVED | tablet, monitor |

## Test inventory and a release checklist

- **Programmatic:** all current test suites on PostgreSQL and SQLite; role negatives; migration checksums; clean DB seeding; isolated restore; idempotent requests; provider outage; consent withdraw; source change/retraction; malicious/invalid inputs.
- **Browser:** 7 existing viewport configs are a regression baseline, not physical-device equivalence. Add click-through success/error journeys per role; keep deterministic screenshots and manual comparison for phone/tablet/monitor.
- **Accessibility:** keyboard-only, skip link, focus lifecycle, text resize, contrast/reduced motion, correctly named buttons, sensible field errors. Track unresolved issues in a defect register.
- **Security:** active session/revocation, privilege escalation, XSS/template escaping, rate limiting, credential recovery, CSRF/CORS expectations for chosen auth transport, no logging of sensitive data, cross-organization leakage.
- **Operational:** restart after data write, email/push/video/provider failure fallback, queue replay, backup/restore measured RTO/RPO, no fake LIVE, protected commercial export.
- **Data quality:** event identity, date/timezone, stage transition, callback idempotency, exact source of metric, no stale production-like synthetic count.
- **Live:** exact main SHA, Render config drift check, API health + readiness, authenticated smoke, per-device E2E, screen captures, audit and rollback record. Build green alone never completes a feature.

## Release/adoption statuses (do not conflate)

- **Repository complete**: file exists, suitable code reviewed, exact-head test success.
- **Demo live**: runtime exact SHA, demo UI with API proof; data must remain explicitly synthetic.
- **Technical Phase 0 complete**: independent durable DB, restore, non-demo identity and PostgreSQL ready proof.
- **Pilot usable**: real user workflows accepted with security/privacy and operator support.
- **Institutional validated**: externally attributable buyer evidence, signed scope/participation when applicable, verified outcome.
- **Sellable enterprise product**: legal/privacy/contractual/service terms and support obligations fit actual client requirements, not just investor UI.

## Recommended next delivery sequence

1. First PR: docs-only admission/real-party checkpoint (#61) — review and merge only on verified state.
2. Next P0 technical PR: Render deploy/build/health and isolated PostgreSQL admission preflight without touching public demo or MFW.
3. Actual DB gate (provider setup and independent restore target): execute manual admission, exact-main Render /health and /ready, operator bootstrap, protected authenticated smoke; save proof.
4. UX & coverage wave: inventory all clickable controls, run each of six E2E routes with deliberate failures across devices, fix broken or misleading states. No new synthetic executive modules.
5. Media/editorial wave: phase 1 controlled publication, medical reviewer authority, evidence admission+scheduled watch, real licensed media, public citation panels.
6. Event/partner wave: signed QR, live/check-in/booking/queue, verified attendance, scoped consented lead handoff, reliable delivery and operational reporting.
7. First independent institutional working session: obtain real requirements, agree proof boundary, then add *only necessary* document receipts, review decisions and participation authority.
8. Investor-ready wave: actual pilot KPIs, independently supported economic case, 3-role product walkthrough, procurement pack, contract-ready exclusions and value proof.

## What is not done / cannot be claimed

- Production PostgreSQL, clean non-demo accounts, actual backup/restore on a provider and `production_ready=true` are not evidenced as complete.
- The public Render service still uses ephemeral SQLite; Render Free terms do not meet a promised SLA by themselves.
- The external PostgreSQL admission service observed HTTP 503 in this audit; root cause requires further diagnosis; last deploy logs confirm only previous SQLite startup.
- The existence of four licensed photos and responsive CI screenshots does not mean all visuals are aesthetically and legally approved.
- Read-only procurement/follow-up screens are not actual document receipt/approval authority.
- Signed identity/trust demo, compatibility, and evidence exports do not prove participation by an external institution.
- Content/catalog/demo activity and user-input-only economics are not actual Promomed patient outcomes, sales pipeline, ARR, revenue, or validated ROI.
- Clinical diagnosis, prescription, FHIR/EHR, formal medical accreditation and credential authority remain outside current approved scope.

## Permanent project conventions

- Keep `docs/PROMOMED_INTEGRATION_MASTER_PLAN_2026-10-01.md` as long-horizon capability/source plan. Use **this audit backlog** as implementation-order and release-evidence register. Reconcile rather than overwrite historical design choices.
- After each accepted PR, update `docs/IMPLEMENTED_SCOPE.md`, `docs/DEPLOYMENT_STATE.md`, `CHANGELOG.md`, this backlog's affected rows, and screenshot/test manifest. No silent PLAN→DONE transition.
- Every future task must name role, UI action, API command/query, data owner, consent/safety rule, failure path, and proof link. If one is missing, do not accept it as complete.
- Prefer use of existing code and no-charge open-source/free-tier options. Do not introduce billable provider services or silently activate overage charges.
- Never commit DSN, secrets, personal health data or third-party confidential correspondence. Do not alter unrelated project databases.

## Source index

- Canonical Master Plan: https://github.com/PetrFedin/promomed/blob/main/docs/PROMOMED_INTEGRATION_MASTER_PLAN_2026-10-01.md
- Current Scope: https://github.com/PetrFedin/promomed/blob/main/docs/IMPLEMENTED_SCOPE.md
- Database admission runbook: https://github.com/PetrFedin/promomed/blob/main/docs/PHASE0_POSTGRES_ADMISSION.md
- Corporate readiness gaps: https://github.com/PetrFedin/promomed/blob/main/docs/CORPORATE_SECURITY_PRIVACY_VENDOR_PACK_2026-10-05.md
- UI/photography rules: https://github.com/PetrFedin/promomed/blob/main/docs/UI_SYSTEM_V2.md
- Live deployment ledger: https://github.com/PetrFedin/promomed/blob/main/docs/DEPLOYMENT_STATE.md
- Verified live service: https://sostoyanie-promomed-live.onrender.com
- GitHub Actions current main: https://github.com/PetrFedin/promomed/actions/runs/38006961632
- Render Free limitations: https://render.com/docs/free
- Neon Free updated limits on 2026-10-02: https://neon.com/blog/neon-free-plan-1-gb-per-project

**Register size:** 114 work packages (P0 26, P1 62, P2 19, P3 7). These are planned work packages, **not** measured defects or remaining failure counts.
