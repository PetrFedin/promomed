# P0 SEC: partner-binding revocation for commercial contact access

Candidate: 2026-10-20, stacked on Draft PR #131. No live/main/database changes.

## Source-verified gap
Previously partner commercial and appointment read projections required active verified membership, but did not require the organization to retain a non-empty partner_id. Placement and slot updates used the same weaker membership check. New appointment bookings already required an assigned partner; old contact data remained accessible by the legacy read paths.
This is a confirmed source-level authority-revocation inconsistency, not evidence that production users were affected.

## New authority contract
- partner_org_scope.commercial_member validates partner-role membership, current active organization and nonblank partner_id.
- Commercial and appointment projections hide the organization and participant contacts immediately after partner_id is revoked.
- Placement and slot updates and slot creation require current commercial membership.
- New lead submissions reject NULL, empty and whitespace-only partner_id.
- Participant-owned lead withdrawal and appointment cancellation remain available after partner unbinding.
- Historic disclosures cannot be recalled. Existing data is not deleted.

## Acceptance tests
- SQLite: consented lead remains owner-withdrawable; partner cannot read or modify placement after unbinding.
- SQLite: active booking and waiting list are hidden from unbound partner; no new slots or updates; owner cancellation remains possible; promotion is suppressed.
- PostgreSQL 17: same partner-unbinding regression for lead and appointment fixtures.
- Re-run participant registration, event registration, UI contract, persistence and browser workflows on exact candidate SHA.

## Release boundaries
Nonempty partner_id is not sufficient alone: verified staff membership continues to be mandatory. This change is scoped to the partner commercial and appointment surfaces; broader institutional access requires separate review. Production remains HOLD until #64 (Render configuration), #65 (isolated PostgreSQL), #94 (release governance), complete exact-SHA CI and independent privacy/security approval.

## Next stacked admission: parallel commercial writes, 2026-10-20

Concurrent placement create uses INSERT ON CONFLICT DO NOTHING plus rowcount CAS.
Concurrent placement updates add version AND status guard and check rowcount.
Concurrent participant lead submissions with one idempotency key return the same existing lead, not a duplicate or database exception.
Repeated withdrawals use the affected-row count so only the first change reports replayed=false.
PostgreSQL 17 tests coordinate independent database connections at the stale read boundary and verify exactly one successful placement transition and one durable lead.
SQLite tests cover first placement conflict and withdrawal idempotency.
These controls do not determine collaboration project authorization; issue #133 remains open.
