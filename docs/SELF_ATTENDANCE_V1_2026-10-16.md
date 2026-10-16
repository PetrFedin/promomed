# SELF ATTENDANCE V1 — participant self-report boundary (2026-10-16)

Status: Draft source candidate stacked after SEC-11 activity-booking Draft #114. Not deployed.

## Purpose

Create a participant-owned way to say "I am here / I left" without turning that statement into verified attendance evidence.

New mutation route:

- `POST /api/self-attendance/v1`
- exact body: `{"item_id":"...","action":"arrive|leave"}`
- authenticated active `participant` only;
- no target email field;
- query selectors are rejected before body parsing, authentication or database access.

Legacy `/api/session-attendance` remains in the SEC-11 non-demo deny registry.

## Arrive

`action=arrive` requires:

1. active participant account for the authenticated email;
2. exact current event payload is admitted through public-state v1;
3. the participant owns an `activity_bookings` row with status `booked`;
4. no existing staff/organizer attendance record occupies the same participant+session key.

The stored row is:

- `status='self_reported'`
- `source='participant_self_report'`
- participant's own email from server authentication.

Response explicitly states:

- `verifiedAttendance=false`
- `countsAsAttendanceKpi=false`

Repeated `arrive` while the same self-report is active is idempotent and does not rewrite the timestamp.

## Leave

`action=leave` only modifies an existing row whose source is `participant_self_report`.

It changes status to `self_reported_complete` and sets `checkout_ts`.

Leave remains available after event publication withdrawal. This preserves owner control over the participant's own record without re-opening a withdrawn event for new self-reports.

Repeated leave is idempotent.

## No overwrite of verified/internal records

If a `session_attendance` row already exists with another source such as `staff` or `organizer`, participant self-report returns a conflict and leaves the row unchanged.

The participant route therefore cannot downgrade, rewrite or erase an operational attendance record.

## Analytics boundary

Existing aggregate attendance queries count `present/completed`. Client365 counts only its explicit `ATTENDED_STATES`.

`self_reported` and `self_reported_complete` are intentionally outside both sets.

The versioned route also creates **no** `partner_engagement`, lead, consent or revenue row.

`/api/my-state/v1` exposes only the current account's `participant_self_report` rows and publishes explicit flags:

- `selfAttendanceIsVerifiedAttendance=false`
- `selfAttendanceCountsAsAttendanceKpi=false`

## Qualification

The same test suite runs in SQLite and PostgreSQL persistence jobs and proves:

- exact-admitted event + own booked session permits self-report;
- waitlist/unbooked state is rejected;
- withdrawn event blocks new self-report;
- owner can leave after withdrawal;
- repeated leave is idempotent;
- participant cannot overwrite staff attendance;
- request cannot carry another email;
- organizer cannot use the participant route;
- query selectors are rejected before body/auth/DB;
- partner engagement count remains zero;
- attendance KPI count remains zero;
- Client365 does not classify the self-report as attendance;
- another participant's my-state cannot see the record.

## Truth boundary

A participant self-report is not:

- independently verified attendance;
- check-in evidence;
- medical evidence;
- partner consent;
- partner lead;
- retention;
- revenue evidence.

No production data, schema migration, Render setting or paid resource is changed by this candidate.
