# Release Ledger

## 2026-09-30 — v1.3 repository consolidation

**Git source-of-truth:** `PetrFedin/promomed/main`

Transferred the complete v1.3 Pilot Command System from temporary deployment branches into the dedicated Promomed repository: participant experience, operational backend, floor/occupancy/queues, staff assignments, incidents/SLA, speaker readiness, attendance, partner appointment desk, participant alerts, stream health, Customer Intelligence and Owner Control Tower.

**Render verified before migration:** operational service and static preview are LIVE on v1.3. Exact deploy IDs are in `docs/DEPLOYMENT_STATE.md`.

**Open infrastructure item:** Render GitHub integration does not yet have fetch access to private `PetrFedin/promomed`; therefore legacy live services still point to two temporary Moscow deploy branches until cutover can be completed.

## Historical live milestones

- v1.2 — session attendance context and session controls.
- v1.1 — operational pilot control room and appointment lifecycle.
- v1.3 — Pilot Command System: floor map, staff, speakers, alerts, Owner Control Tower, partner desk reassignment and SLA signals.

This ledger records product/release milestones. `DEPLOYMENT_STATE.md` records the exact live infrastructure state.
