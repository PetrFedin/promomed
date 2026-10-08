# Institutional Pilot Readiness Workspace v1

**Status:** implementation candidate  
**Base:** `main@4ba84009857f1c0e35b37104e1683f214a06cfef`  
**Purpose:** turn the existing institutional/federation authority into a practical pre-pilot onboarding workspace without fabricating partner adoption.

## Product flow

`institution identity -> verified human authority -> institution role -> technical/process qualification -> independently controlled public key -> federation compatibility -> portable evidence pack -> delivery readiness -> explicit participation evidence -> governance admission review`

The workspace is a **read-only orchestration projection** over existing authorities. It does not create a second source of truth.

Internal route:

`GET /api/institutional-pilot-readiness?organization_id=...`

Allowed Promomed roles in v1:

- governance;
- editor;
- sales.

External partner self-service is intentionally not opened yet because the current HTTP read layer does not bind the authenticated account identity to the exact institutional membership on this route.

## Reused authorities

The workspace reads existing records only:

- `institutional_organizations`;
- `institutional_memberships`;
- `institutional_role_bindings`;
- `syndication_partner_qualifications`;
- `institutional_federated_anchors` + current anchor state;
- `federation_profile_evaluations`;
- `federation_discovery_bundles`;
- `syndication_delivery_endpoints`.

No new migration is required.

## Readiness semantics

Required readiness steps:

1. attributable non-demo institutional identity;
2. verified non-demo administrator/operator;
3. active non-demo publisher/consumer/contributor role;
4. current qualified syndication status;
5. active proof-verified non-demo institutional anchor;
6. compatible federation-profile evaluation;
7. current non-demo portable discovery bundle;
8. explicit external pilot participation evidence.

A verified production delivery endpoint is visible as an operational readiness step but is not required for admission review.

## Hard truth boundary

The workspace:

- does not create an organisation;
- does not bind membership;
- does not qualify a partner;
- does not admit or activate a trust anchor;
- does not create accreditation or endorsement;
- does not infer adoption from compatibility;
- never upgrades a `demo_only=true` organisation into a real pilot;
- does not yet implement canonical participation evidence.

Therefore current synthetic fixtures remain visibly blocked.

## Why participation evidence stays blocked

The existing master plan requires explicit participation by a real non-demo institution before Promomed records a real external pilot.

Until the first real participant exists, a new canonical participation/terms authority would be premature and could encourage synthetic traction. The workspace therefore exposes this as a deliberate blocker:

`no_canonical_participation_evidence_authority_implemented_until_real_participant_exists`.

When a real institution is available, the next implementation may add a narrowly scoped admission record bound to:

- attributable organisation identity;
- named verified institutional administrator;
- participation terms/version;
- explicit consent/acceptance timestamp;
- evidence reference;
- independently controlled key/proof;
- governance decision and immutable audit.

## Commercial consequence

This is the bridge from deep federation infrastructure to procurement/pilot execution.

A CEO, strategic partner or institutional buyer can see one clear answer:

**what is already proven, what is missing, who must act next, and why the organisation is or is not ready for a governed pilot.**

It is not a traction counter and must never be presented as one.
