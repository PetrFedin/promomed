# Participant ↔ Partner internal link qualification — 2026-10-16

Status: **Draft only, no merge/deploy**. Source parent: APPT-02 PR #120 at `1663c66f248156d7daf2ff6aebfbc704fdf3315a`.

## Data and authority map

| Producer / authority | Owner consumer | Partner consumer | Boundary |
|---|---|---|---|
| `partner_commercial_placements_v1` | enables consented lead submission | active verified institutional member | enabled does not imply contract or revenue |
| `participant_partner_leads_v1` | `/api/partner-commercial/v1` -> `/personal/` | organization-specific submitted only | withdrawal hides active contact; no backup-erasure claim |
| `partner_appointment_slots_v1` | appointment read + owner cancel | organization-scoped create/update | status, validity window, placement, institution |
| `participant_partner_appointments_v1` | `/api/partner-appointments/v1` -> `/personal/` | only own organization's booked/waitlist contacts | booking is not attendance |
| `activity_bookings`, `session_attendance` | `/api/my-state/v1` | no implicit partner disclosure | self-reports must never enter verified attendance KPIs |
| `participant_event_registrations_v1` | `/api/event-registration/v1` | no automatic visibility | event confirmation does not constitute partner consent |

## Hardening

- Parent capacity lock now precedes participant booking-row read during appointment cancellation to prevent stale duplicate-cancel decisions.
- Waitlist promotion excludes suspended/deactivated participants while preserving their audit/owner state.
- A previously closed slot cannot be reopened while its commercial placement is paused/ended.
- Participant UI displays only owner-scoped appointment and lead reads and submits exact owner-cancel/withdraw commands. No public browsing of slots is implied.
- Partner endpoints load using independent settled results: an unavailable partner subsystem displays an unavailable state, not empty/no-record truth.
- The UI keeps bearer tokens in JS memory and renders external text through `textContent`.

## Verification requirements

- Exact-HEAD SQLite, PostgreSQL, UI-contract workflows via isolated push triggers; no production secrets or deployment.
- Validate duplicate cancel, suspended waitlist, two-tenant isolation, lead consent/withdrawal, no PII in public state, and owner-only visibility.
- Full responsive browser and database-restore suite must be rerun at integrated candidate SHA before production admission.
- Verify separate production infrastructure issues #64 (Render), #65 (isolated PostgreSQL), #94 (branch governance).
- Do not convert recorded booking, self-attendance, partner lead, or operational placement into verified attendance, sale, revenue or clinical claim.
