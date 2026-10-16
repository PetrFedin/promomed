# PARTNER COMMERCIAL V1 — organization-scoped placement and voluntary leads

Status: Draft qualification candidate. Not deployed.

## Why this exists

Legacy routes `/api/placement` and `/api/lead` mutate singleton/global records and are blocked outside demo by SEC-11. Partner Commercial v1 replaces that model with verified institutional scope.

Route:
- `GET /api/partner-commercial/v1`
- `POST /api/partner-commercial/v1`

The authority reuses:
- `institutional_organizations`
- `institutional_memberships`
- active account role `partner`
- non-empty `verification_ref`
- effective/expiry membership windows.

No client-provided organization id is trusted without that membership proof.

## Placement

A partner member with role `operator` or `administrator` may update only its own organization.

Operational states:
- `planned`
- `enabled`
- `paused`
- `ended`

These are platform operational states only. They do **not** mean:
- executed contract;
- accepted invoice;
- recognized revenue;
- finance acceptance;
- campaign delivery;
- participant consent.

Optimistic `expected_version` prevents lost updates. An ended placement is terminal.

## Voluntary lead

A participant may submit a lead only when:
1. the authenticated account is an active participant;
2. target organization exists, is active and has a partner binding;
3. target organization has Partner Commercial placement `enabled`;
4. request carries `consent=true`;
5. request id is a 32-char lowercase hex idempotency key.

Stored lead data:
- lead id;
- target organization;
- participant email;
- lead kind;
- explicit consent timestamp;
- created timestamp;
- status.

A submitted lead is visible only to active verified members of the target organization. Other partner organizations receive neither the lead nor target-organization metadata through this route.

## Withdrawal

Participant may withdraw only their own lead by lead id.

After withdrawal:
- partner snapshots no longer include the participant contact;
- participant snapshot retains a withdrawn status for audit/UX;
- the record remains in authoritative storage.

This is **not** a claim that historical backups have already been erased. Backup retention/deletion policy remains a separate privacy control.

## Idempotency

`lead_submit` uses `(participant email, request_id)`.

Replay with same organization and kind returns the existing lead.
Reusing the same idempotency key with different content returns `409 idempotency_conflict`.

## Migration 034

Adds:
- `partner_commercial_placements_v1`
- `participant_partner_leads_v1`

SQLite additionally uses DB triggers to enforce parent organization/account existence because repository runtime does not globally enable `PRAGMA foreign_keys=ON`.

Source/restore fingerprint and parallel migration proof include both tables.

## Qualification

SQLite proves:
- partner A cannot mutate organization B;
- optimistic versioning;
- lead blocked unless placement enabled;
- explicit consent requirement;
- target-org-only lead visibility;
- withdrawal removes partner visibility;
- idempotent replay/conflict;
- query selectors rejected;
- organizer/foreign roles rejected;
- no contract/revenue claim.

PostgreSQL 17 proves:
- two non-demo organizations remain isolated;
- partner B cannot update A;
- lead visibility is scoped to A;
- membership revocation immediately removes A from partner snapshot and blocks further writes.

## Not solved in this slice

- appointment scheduling v1;
- participant-facing partner directory/discovery admission;
- CRM export;
- legal contract acceptance;
- invoicing/payment;
- marketing-consent lifecycle;
- backup erasure policy;
- production SMTP/Render/PostgreSQL admission;
- independent security/privacy review.

Legacy `/api/placement` and `/api/lead` remain blocked outside demo.
