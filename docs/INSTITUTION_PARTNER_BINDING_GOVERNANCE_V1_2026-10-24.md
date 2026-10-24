# Promomed / Institution partner binding governance v1

Candidate: 2026-10-24. Stacked Draft on PR #142, NOT merged, deployed or released.

## Authority and HTTP contract

POST /api/institution/partner-binding/v1 has two actions. Both require an authenticated active governance account; the reviewer must not be the proposer. Proposals are valid for 48 hours.

PROPOSE fields: action=propose, request_id (32 lowercase hex), organization_id, expected_version (integer >=0), expected_partner_id (string or null), new_partner_id (string or null), reason (12-500 characters), evidence_ref (8-200 characters). All fields required. Exactly one of old/new must be null: new clean institution binding or explicit revoke, never replacement.

REVIEW fields: action=review, request_id, decision_id (32 lowercase hex), decision=approve|reject, review_reason (12-500 characters). A separate active governance account must decide.

GET /api/institution/partner-binding/v1?organization_id=... returns the organization binding revision, current partner id, proposal statuses and local decision receipts for governance only. Participant emails and contact records are excluded.

## Allowed and rejected transitions

| From | To | Rule |
| --- | --- | --- |
| Never-bound clean organization | Active existing partner | Two-person review, version CAS, no prior commercial history and no pre-existing active member grants |
| Active bound organization | Unbound | Two-person review, version CAS, placement paused, open slots closed |
| Partner A | Partner B | DENIED: historical contact and consent rights cannot silently transfer |
| Previously revoked / prior commercial history | Bound partner | DENIED: create new verified organization or separately design purpose-by-purpose legal migration |
| Pending request past 48-hour expiry | Any | DENIED; no late approval |
| Same proposer and reviewer | Any | DENIED |
| Stale binding or revision | Any | DENIED |

## Transactional source of truth

Migration 037 (SQLite and PostgreSQL 17) adds per-institution revision, time-bound decision request, and update-protected hash-linked audit events. Audit events use increasing event_no, previous_receipt_sha256 and receipt_sha256, providing internal chain-of-custody metadata, not external independent tamper-proof timestamps. The reviewer locks the institution and request before applying; PostgreSQL SELECT FOR UPDATE and SQLite BEGIN IMMEDIATE control concurrent decisions. A failed command must roll back before commit via the application command framework. Membership creation now also locks the same institutional parent row, preventing a stale first-binding review from racing an older membership activation.

On accepted revoke, institution partner_id becomes NULL; admitted commercial reads and new lead/meeting writes should fail closed through existing authority checks. Planned/enabled placements become paused and open slots become closed. Source booking and consent records remain available for the participant's own cancellation and audit; the participant agenda marks such partner meetings unavailable and excludes them from confirmed ICS. No historical contact is transferred to another partner. Before any first commercial binding, existing active institutional memberships are also a deny condition: assigning a partner may not implicitly grant its contacts to old collaboration members.

**Independent collaboration access:** institutional membership and separate demo collaboration permissions are NOT automatically revoked by commercial unbinding. Issue #133 remains open for policy approval. No third-party CRM export can be recalled without explicit counterparty cooperation. External deletion/acknowledgment is explicitly not claimed; Issue #140 covers export notices and downstream obligations.

## Acceptance and engineering evidence

- SQLite and real PostgreSQL 17 fresh/upgrade migrations, migration checksum continuity and restore qualification.
- Distinct active proposer/reviewer, suspended-account and wrong-role negatives, explicit request/decision idempotency.
- Expiry, concurrent proposals, two simultaneous independent reviewers, stale versions and cross-org denial.
- Commercial lead/partner-appointment read revocation, participant-owner cancellations and unavailable-state ICS.
- Initial clean binding never implicitly grants unverified partner membership.
- Event sequence and hash linkage, reject prior receipt rewrites.
- API route plus app/UI/browser regression checks on one exact SHA.

## Release hold

This is code and a technical acceptance candidate, not a production governance or legal approval. Independent review of operator identity, evidence_ref authenticity, contract/DPA and retention, privacy/security policy and external integrations is outstanding. No production DB mutation, branch main merge or paid resource. Required infrastructure gates: #64 (Render), #65 (isolated PG), #94 (protected main), #133 (collaboration policy), #135 (full binding lifecycle).