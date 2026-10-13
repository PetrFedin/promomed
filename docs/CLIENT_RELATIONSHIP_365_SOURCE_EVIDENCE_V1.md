# Client Relationship 365 — source-backed account timeline v1

**Status:** implemented in Draft PR, NOT merged and NOT live-admitted. Date: 2026-10-13.
**Priority:** P1 after #69/#70/#73/#79/#82 integration and P0 Render #64 + dedicated 0-additional-cost PostgreSQL #65.

## What exists in this PR
- Authenticated read-only `GET /api/client-365`. Server resolves the identity from the session; an arbitrary email/user selector causes HTTP 422. Unauthenticated HTTP 401; any role other than participant HTTP 403; account role changed or status suspended/revoked HTTP 403 even if its existing session still says participant.
- `app/client365.py` constructs a bounded, account-scoped list from existing registrations, activity_bookings, session_attendance, takeaways, audited account actions, followups and product-interest information requests. No new database tables, providers or cost.
- Public app `#me` now shows **own** evidence dates, source and assurance type. Switching accounts/logout clears cached visible personal history and pending responses cannot repopulate another account's screen.
- Existing `journey365` remains a **behavioral plan**, not a verified retention computation. The home text now says so explicitly.

## What D1, D7, D30 mean, mathematically
- Cohort baseline: account's saved **confirmed registration timestamp** `t0`; not event date, subscription date, selected topic or notification schedule.
- A due milestone at Dn requires `now >= t0 + n * 86400` seconds. Uses UTC epoch arithmetic; calendar-local 7-day behavior and due messaging will need a separately agreed timezone methodology.
- Observed account activity Dn: at least one eligible **explicitly audited action** (replay opened, takeaway saved, learning enrolled/advanced, discovery saved, feedback) with source timestamp `ts >= t0 + n * 86400`.
- Statuses: no_registration_baseline / not_due / observed_account_activity / no_observed_account_activity. Action count is bounded audit evidence, not a validated retention ratio.
- A followup with status `planned`, `active`, `sent` or `completed` is **not** counted as an observed account return. Booking, attendance check-in, learning enrollment without a later action, and imported demo content do not automatically establish D7/D30 return.
- **No cohort retention rate** is calculated (field `cohortRetentionRate=null`). Real cohort calculations need active non-demo identities, timestamps, duplicate filtering, a defined observation window, an admissible source of meaningful sessions and consent/erasure treatment.

## Evidence/source boundaries
| Event | Source | What it proves | What it does not prove |
| --- | --- | --- | --- |
| Registration | registrations | backend-confirmed registration record | actual attendance |
| Booking/waitlist | activity_bookings | reservation or waitlist state | check-in |
| Attendance | session_attendance | staff or participant recorded a presence | independently validated physical presence |
| Takeaway | takeaways | account saved a note | validity of its medical content |
| Account action | events | recorded interaction at timestamp | verified real-person return |
| Followups | followups | planned/updated follow-up item | a returning person |
| Interest request | product_interests | recorded explicit request for an information material | consent to disclose health data or a partner marketing lead |

Never join participants to `partner_collab_*` tenant records, marketing contacts or financial attribution without separate purpose-scoped consent and accepted source evidence. No medical diagnosis, behavior-derived treatment, pharmaceutical offer or incentive inference.

## Acceptance checks
- `tests/test_client365_evidence.py`: no baseline means no fabricated retention; due/not_due; D1/D7/D30 only after elapsed time + audited account action; no future timestamp; staff vs self event labels; no foreign data; role, query and revoked-account negative access.
- `tests/test_client365_browser.py`: participant login, read-only personal timeline, direct foreign selector denied, role-switch clears data, organizer denied, no mobile/tablet/desktop horizontal overflow.
- Existing UI, architecture (server.py <=405 lines), SQLite and PostgreSQL tests must remain GREEN on **exact head SHA**. Screenshots and independent review required before approval.
- Backend is read-only. No new migration or credentials, no data copied between projects. Costs: **no new paid resources**; existing GitHub Actions quota usage must be evaluated separately.
- Missing /ready proof and verified durable postgres keeps customer operation and investor traction claims blocked.

## Handoff to Client 365 v2 and investor proof
After release gates: consent revision/revocation and verified attendance scan identities; only then cohort D7/D30 with explicit eligible denominator, non-demo account proof, source timestamps, late-arriving correction and data deletion policy. Investor value tower consumes independently accepted stage evidence, not demo timelines, planned followups or engagement badges.
