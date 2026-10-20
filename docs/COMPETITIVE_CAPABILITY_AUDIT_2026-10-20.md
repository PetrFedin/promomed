# СОСТОЯНИЕ × Promomed — конкурентный функциональный аудит

**Дата проверки:** 2026-10-20  
**Объект:** концепт СОСТОЯНИЕ; не официальный продукт Промомед.  
**Baseline:** Draft PR #136 (`e11a396c0afb86c88a58626758e11e29c5b789dc`).  
**Метод:** сверка публично описанных функций производителей с `docs/IMPLEMENTED_SCOPE.md`, исходниками `app/`, `public/personal/`, миграциями и пройденным CI. Ни один признак на маркетинговой странице не является независимым функциональным тестом чужого продукта. Не исследованы закрытые enterprise-тарифы, договоры и внутренние платформы — заявлять «проверен весь функционал конкурентов» без доступа к их ПО нельзя.

## 1. Подтверждённые публичные референсы

| Аналог | Рынок / задача | Публично подтверждённый функционал | Источник |
|---|---|---|---|
| Timepad | Россия: билеты и регистрация | Страницы события, платные и бесплатные регистрации, проверка входа, промокоды, онлайн-статистика | [Timepad for Business](https://for-business.timepad.ru/), [продукт](https://timepad.ru/about/product/) |
| Nethouse.События | Россия: билетный/операторский контур | Категории билетов, модерация, статистика, возвраты, офлайн QR-сканер с последующей синхронизацией, бейджи | [Сервис](https://events.nethouse.ru/), [офлайн-проверка](https://events.nethouse.ru/help/proverit-bilety-prilozhenie/) |
| Eventicious / Event.Rocks | Россия: мобильный опыт события | Расписание, интерактивные вопросы к докладам, участники, встречи и переносы через админку, QR сканер лекций | [Встречи](https://help.eventicious.com/ru_RU/521804), [вопросы](https://help.eventicious.com/ru_RU/engagement/360002924478-questions), [сканер](https://help.eventicious.com/ru_RU/qr-session-scanner-installation-and-use) |
| МТС Линк | Россия: вебинары | Тесты/голосования, аналитика участия и источников, экспорт, счётчики, CRM/API | [Аналитика вебинаров](https://mts-link.ru/products/webinar/analytics/) |
| Teachbase | Россия: LMS | Курсы, SCORM, смешанное обучение, тесты, сертификаты, учебная аналитика, форум, календарь | [Функционал Teachbase](https://teachbase.ru/functional-teachbase/) |
| Cvent | Международный: enterprise events | Динамическая регистрация, badge/QR check-in, управление посещением, survey/poll, календарные приглашения, API/CRM, отчёты ROI | [Функции](https://www.cvent.com/en/event-management-software/features), [reporting](https://www.cvent.com/en/event-management-software/event-reporting) |
| Swapcard | Международный: B2B / expo | Exhibitor Center, 1:1 встречи, matchmaking, lead capture, настройка sponsor tools, AI assistant и аналитика | [Платформа](https://www.swapcard.com/), [центр экспонента](https://www.swapcard.com/features/exhibitor-center), [AI](https://www.swapcard.com/features/event-virtual-ai-agent) |
| Whova | Международный: attendee experience | Персональная программа, community/chat, Q&A, live, polls, feedback, exhibitor страницы | [Инструкции приложения](https://whova.com/pages/attendee-mobile-app-instructions/), [типы событий](https://whova.com/pages/use-whova-event/) |
| Bizzabo | Международный: события и спонсоры | Программа, push, email-автоматизация, event app, спонсорский lead capture QR/Klik, анкеты квалификации, CSV, ROI-панель | [Платформа](https://www.bizzabo.com/), [лиды](https://www.bizzabo.com/event-management-software/lead-capture-app) |
| Glue Up | Международный: year-round community/CRM | Членство, мероприятия, счета, обновление статуса подписки, сообщества и peer-общение, CRM, email journey | [Community](https://www.glueup.com/blog/membership-community-platform-engagement), [CRM](https://www.glueup.com/blog/best-crm-membership-organisations) |

**Никакой ценовой, юридический или SLA-паритет не утверждается.** Доступность функций зависит от продукта, модуля, контракта и региона, а в отдельных случаях от устройства и провайдера.

## 2. Матрица capability: конкуренты → Promomed → решение

`CODE` = присутствует в репозитории; `CI` = проверено автоматизированными тестами; `DEMO` = демонстрация, не внешняя система; `GAP` = отсутствует достаточное доказательство реализации; `GATED` = требует юридических, инфраструктурных или продуктовых входов.

| Функция | Подтверждённый аналог | Promomed на текущем baseline | Действие / усиление | Очередь |
|---|---|---|---|---|
| Регистрация, статус, вместимость, waitlist | Timepad, Cvent | CODE/CI: участник и событие, атомарная очередь | единый cross-event booking ledger, SLA отмены, без oversell | P1 |
| Оплата, тарифы, возвраты, промокоды | Timepad, Nethouse | GAP для реальной платёжной/фискальной эксплуатации | модуль only after contractual/tax/payment decisions, refunds ledger | P2-GATED |
| Offline QR и синхронизация | Nethouse, Cvent | DEMO check-in, нет подтверждённой подписанной offline authority | signed expiring QR, offline idempotent scans, conflicts, device revocation | P1-GATED |
| Личное расписание, iCal, интервалы | Cvent, Whova, Eventicious | регистрация, события и встречи раздельно | Draft: единая owner-only проекция + ICS без выдуманного конца события | P1, текущий PR |
| Управление встречами и перенос | Eventicious, Swapcard | CODE/CI: slots, booking/waitlist/cancel | explicit reschedule, actor permissions, owner notice, versioned audit | P1 |
| Smart matchmaking | Swapcard, Bizzabo | CODE объяснимого ранжирования контента; не полноценное AI matchmaking | opt-in цели B2B, объяснение связи, no health-sensitive inferences | P2 |
| Exhibitor self-service portal | Swapcard | CODE частичной партнёрской authority; нет live self-onboarding | verified org grants, profile, onsite staff, controlled service catalogue | P2-GATED |
| Lead capture и квалификация | Bizzabo, Swapcard | CODE/CI: добровольный lead и немедленный отзыв | reason-coded consent, validated meeting outcome, TTL & scoped export | P1 |
| Sponsor ROI attribution | Bizzabo, Cvent | DEMO + evidence-labelled commercial views | signed event → approved lead → confirmed outcome, never invent revenue | P2 |
| Уведомления и email journey | Whova, Glue Up | CODE UI/notification patterns; real delivery provider not proven | notification outbox, preferences, retries, opt-out & bounce reconciliation | P1-GATED |
| Онлайн трансляции, записи | МТС Линк, Bizzabo | DEMO live/replay states, source-labelled transcripts | provider adapter, caption SLA, player accessibility, fallback | P2-GATED |
| Q&A, polls, surveys | Eventicious, Whova | CODE части вопросов/feedback | one moderated queue, anti-spam, surveys by event, no clinical advice | P1 |
| LMS, tests, certificates | Teachbase | CODE learning tracks, progress; accreditation not claimed | content review, quizzes, learning evidence, optional independent accreditation | P2-GATED |
| Year-round community | Glue Up | CODE/DEMO community + Relationship 365 | unified journey, privacy-safe messaging, meaningful return reasons | P1 |
| Enterprise integrations | Cvent, Swapcard | CODE adapters/contracts; external CRM authority not admitted | outbox, signed webhooks, retry/dedup, export revocation | P2-GATED |
| Medical source verification | Not comparable with general event tools | CODE: Claim Evidence Graph + review/retraction, demo sources | external source provenance, reviewer identity, medical/legal approvals | P0/P1-GATED |
| Corporate & investor governance | Enterprise platforms vary | CODE investor/control room, assumptions-only scenarios | exact SHA evidence, immutable review decisions, real contracts only | P0 |
| Security/tenancy/consent | All, product- and tier-dependent | CI tenant negatives, demo isolation; production admission missing | complete P0 #64/#65/#94/#133/#135, explicit audit & retention | P0 |

## 3. Product differentiation — proposed, not global uniqueness claim

**Promomed proposition:** an evidence-labelled health-education and event engagement system with three independent, verifiable authorities:
1. **Audience**: registration, participation, notes, learner activity, D1/D7/D30 observed events; no medical risk inference.
2. **Partner**: purpose-specific explicit consent, valid institution/member binding, appointments and receipts; not a medical-data feed.
3. **Editorial trust**: cited statement → version/source → qualified reviewer → publication → retract/hold → notification of correction.

Potential UX advantage is to display *what is known*, *why*, *what remains unverified*, and *who can revoke it* directly in the relevant screen. This advantage must be tested with users; superiority or uniqueness versus competitors is not yet established.

## 4. Implementation order — source-of-truth-first

### P0: Release admission — non-negotiable
- GitHub protected main, independent reviewers, exact SHA (#94).
- Render build/health SHA and separate Promomed-only PostgreSQL + restore (#64, #65).
- Governing policy for partner vs collaboration scopes (#133), audited partner reassignment (#135).
- Secret management, privacy retention/erasure and clinical/editorial review before external PII.
- All demo metrics clearly DEMO; no unsupported ROI/clinical outcomes.

### P1: Most useful participant & organizer functions
- **Unified Agenda v1:** event starts, partner meeting intervals, waitlist/cancelled indicators, true-overlap warnings, owner-only ICS; no fabricated meeting/event time.
- Verified capacity, organizer schedule version control and rescheduling notifications.
- Staff QR check-in proof with offline signatures, replay rejection and reconciliation.
- Agenda→session resources→reviewed replay→learning→explicit D7 follow-up, no individual medical recommendations.
- Accessible real-time Q&A, interpreter/caption settings and participant assistance.

### P2: Partner ROI and community
- Consent-scoped exhibitor dashboard, 1:1 meeting reminders, note-taking, operator assignment.
- Sponsor activation value ladder: impression ≠ lead ≠ independently validated commercial outcome.
- Optional event API/webhooks, CRM exports with revocation tracking, segment-safe dashboards.
- Opt-in matchmaking driven by professional interests (not health conditions or inferred patient status).
- LMS certificates only within approved educational claims; accredited CME only with actual authority.

### P3: Scale, after P0–P2 acceptance
- Venue maps and indoor navigation with accessible route alternatives.
- Multilingual, replay search/chapters, human-approved AI topic summaries.
- Event-series / corporate / community multi-tenant configurations.
- AI support agent limited to approved knowledge and reversible delegated actions.

## 5. Criteria for feature acceptance

For each feature demand: source URL + source date (when known); exact code SHA; API contract; positive and negative tenant cases; SQLite and PostgreSQL 17; browser phone/tablet/desktop; authorized live deployment SHA (if admitted); latency/accessibility; support runbook. Duplicating a competitor's marketing screenshot does not qualify.

### KPI definitions (no invented targets)
- **Confirmed registration rate:** unique confirmed participant-event pairs / unique submitted eligible participant-event pairs (event authority).
- **Waitlist conversion:** distinct promoted registrations / distinct waitlisted registrations in same edition (transition ledger, not UI clicks).
- **Verified visit rate:** independently admitted staffed check-ins / eligible confirmed registrations; self-report excluded.
- **Consented lead yield:** unique, unwithdrawn lead IDs linked to explicit purpose/time/partner / eligible authenticated partner interactions; define denominator with the buyer before commercial reporting.
- **Observed D7 activity:** participant accounts with observed action after D7 threshold / eligible cohort with actual confirmed registration baseline; **not clinical retention or proof of externally measured reach**.
- **Meeting overlap warnings:** count of owner-held bookings with known interval overlap; unknown event end stays separate, not assumed conflict-free.

## 6. Release boundaries
- This audit benchmarks **publicly documented vendor functionality**; it is neither a live demo of each platform nor proof of feature completeness of any competitor.
- Latest source code is stacked Draft PR, not public Render. No production deployment or commercial offer implied.
- Medical/health personalization, drug recommendation, diagnosis and patient records are outside MVP.
- No cost/ROI/business outcome has been established by these source comparisons.

## 7. Medical-professional platforms — supplementary functional comparison

The event SaaS category is not enough for health media. Medical-learning and professional tools expose additional mechanisms that must be **governed separately** from consumer participation and commercial partner leads.

| Reference | Region | Publicly described specialty/medical function | Promomed comparison and disposition | Source |
|---|---|---|---|---|
| Medpoint | Russia | Physician-targeted educational portal, webinar activity and an NMO code workflow (provider's claim; program-level confirmation required) | **GAP / GATED** for verified HCP identity and accredited education; define provider-level accreditation proof before awarding credits | https://medpoint.pro/about |
| Врачи РФ | Russia | Doctor-edited professional newsfeed, specialty-specific digest and upcoming medical-event mailings | **CODE + P1 GAP:** content subscriptions exist, verified HCP segmentation and profession-only digest still gated | https://vrachirf.ru/ |
| Росмедлиб / Консультант врача | Russia | Professional medical literature, categorized guidelines, reference materials and AI-assisted navigation | **CODE + GATED:** evidence graph/semantic discovery patterns; external content requires a valid licence, and guidance is not automatically a clinical recommendation | https://www.rosmedlib.ru/index.html |
| Medscape Education | International (US) | CME/CE activities with objectives, financial relationship disclosures, assessments and activity-specific completion certificates | **CODE + GATED:** reviewed learning artifacts exist in code; accredited certificates/CME provider authority not proven; US accreditation is not Russian NMO | https://www.medscape.org/viewarticle/570242 |
| Doximity | International (US) | Professional identity/network, relevant medical information and communications | **GATED:** legal HCP identity and doctor-only communication are distinct from ordinary consumer community and patient data | https://www.doximity.com/ |

Source caveat: Medscape activity URL is an earlier educational illustration; no assertion of the provider's latest course list or current credit count. Medpoint, Врачи РФ and Росмедлиб descriptions are publisher self-descriptions, not third-party audits. Medical usage must not conflate professional educational evidence with medicine prescribing, patient-level data or sales influence.

**P1 physician-education backlog:** governed identity and verification of qualifications; specialist opt-in digest; disclosure of sponsors and conflicts; licensed links to clinical sources and human-reviewed material; content change/retraction alerts; assessment outcome evidence; clear separation of course-completion statement from accredited credit. Professional use case and validation are tracked in [Issue #138](https://github.com/PetrFedin/promomed/issues/138); production remains gated.
