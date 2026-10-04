# PROMOMED / СОСТОЯНИЕ — Investor Readiness

Updated: 2026-10-05

## 1. Investment thesis

СОСТОЯНИЕ предлагается не как приложение одной конференции.

Рабочая инвестиционная логика:

1. media / topic / expert surfaces создают причины возвращаться между событиями;
2. флагманское событие концентрирует внимание и переводит интерес в наблюдаемое участие;
3. operations authority делает событие управляемым, а не декоративным;
4. partner layer связывает обещанный deliverable с фактическим выполнением и добровольным продолжением;
5. post-event route удерживает relationship после события;
6. governed evidence/editorial modules могут открыть более дорогой enterprise-контур только после соответствующих authorities.

Последний пункт — roadmap, а не текущая production capability.

## 2. What is actually sellable now

### Platform pilot

Покупатель финансирует проектирование, controlled pilot и доказательный цикл, а не набор экранов.

Доказуемые элементы:

- iPhone / iPad / desktop participant experience;
- programme, Smart Route, booking and post-event continuation;
- live operational control;
- partner packages / appointments / consented actions;
- audit trail and investor proof;
- database-backed accounts/sessions;
- PostgreSQL migration/admission/restore path, proven in CI.

### Event operating layer

Коммерческий продукт может включать programme, participant journey, QR/check-in, capacity/waitlist, venue state, incident/recovery, live/replay state and operational command centre.

Current status: DEMO / executable MVP mechanics.

### Partner activation layer

Коммерческий продукт может включать partner package, contractual deliverables, placement state, partner appointment, voluntary lead/consent, post-event continuation and evidence/reporting.

Current status: DEMO / executable MVP mechanics.

### Media & Studio

Коммерческий продукт может включать year-round editorial/content surfaces, Studio, experts, topic hubs, community and learning tracks.

Current status: DEMO.

### Governed scientific information

Medical Information Request Desk and evidence-intelligence products remain GATED until Editorial/Medical Review + Evidence/Claim/Expert authorities exist.

They must never be presented as an already delivered production capability.

## 3. Investor status taxonomy

- **LIVE** — capability works in the current runtime.
- **CI-PROVEN** — production behaviour is reproducibly tested but has not yet passed live infrastructure admission.
- **DEMO** — mechanic is executable on demo data; demo metrics are not market traction.
- **GATED** — deliberately unavailable until dependencies/governance are complete.

## 4. Revenue architecture

The product supports several possible revenue surfaces without assuming any price:

1. platform design / implementation / controlled pilot;
2. annual platform contract;
3. event operating module;
4. partner activation / package module;
5. Studio / media programme;
6. future governed scientific-information module;
7. future evidence/editorial intelligence module.

The Investor Economics Lab allows the buyer/investor to enter assumptions directly.

No repository value should be presented as forecast ARR, MRR, valuation, market share or guaranteed client ROI.

## 5. Defensibility thesis

### Unified journey

content -> topic -> expert -> event -> attendance -> consent -> partner action -> replay / return.

### Consent-first relationship graph

Continuation is observable only after explicit participant action.

### Operations + commercial evidence

Operational execution and partner value share one event/audit substrate.

### Governance architecture

Bounded contexts, migrations, restore proof, durable accounts/sessions and fail-closed readiness lower enterprise integration risk.

### Future evidence governance

Evidence / Claim / Expert authorities may become a higher-value enterprise layer, but only after Phase 1+ governance is implemented.

## 6. Current due-diligence evidence

Repository:

- bounded-context modular monolith;
- database-backed account authority;
- salted scrypt passwords;
- versioned SQLite/PostgreSQL migrations;
- clean PostgreSQL admission probe;
- backup/restore proof;
- source/restore catalog fingerprint;
- production identity bootstrap/rotation/revocation proof;
- fail-closed readiness;
- responsive browser QA;
- exact-SHA Render proof.

Current infrastructure limitation:

- public runtime remains SQLite demo;
- Render free PostgreSQL capacity is occupied by MFW;
- a second Render free database was rejected by the provider limit;
- an external isolated PostgreSQL source + restore target is still required for Phase 0 COMPLETE.

## 7. Investor objections — direct answers

### “Is this just a conference app?”

No. The event is one high-intensity point inside a year-round participant / content / partner relationship model.

### “Where is recurring value?”

Potential recurring value exists in annual platform usage, repeated event modules, partner activation, Studio/media and later governed scientific-information services. Pricing is not yet asserted.

### “What data moat exists?”

Today: journey/audit/consent structure is implemented as product architecture and demo mechanics. It is not yet market-scale data. The moat becomes real only with repeated live usage.

### “Why can’t a normal event platform copy this?”

Individual screens are copyable. The defensibility thesis is the combination of participant journey, live operations, consented commercial evidence and later governed scientific/evidence authority in one auditable system.

### “What still blocks production?”

An isolated durable PostgreSQL source + restore contour and its live admission. Phase 1 is intentionally blocked until this is complete.

## 8. Next investment proof

The strongest next proof is not another feature.

It is:

external PostgreSQL -> live admission -> production account -> authenticated smoke -> Phase 0 COMPLETE -> Editorial & Medical Review Authority.

After that, the investor route can truthfully upgrade PostgreSQL/identity from CI-PROVEN to LIVE and begin showing the first enterprise governance moat rather than only its roadmap.
