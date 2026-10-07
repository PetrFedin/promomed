# Institutional Evidence Distribution Network v1

**Status:** repository implementation candidate
**Scope:** Evidence Governance Interchange Profile, Reference Evidence Package, Institutional Publisher / Consumer roles.
**Truth boundary:** process provenance and distribution integrity only. No medical efficacy, safety, diagnosis, treatment, regulator approval, external accreditation or customer adoption is inferred.

## 1. Product objective

This layer turns reviewed Promomed evidence assets into machine-readable institutional packages that can be distributed without exposing internal database authority.

Canonical chain:

`source -> claim -> review -> disclosure -> approval -> seal -> signed checkpoint -> package -> delivery -> acknowledgement -> correction/withdrawal`

Promomed remains authority for reviewed claim/evidence state. Institutional recipients receive a governed projection, not write access to canonical scientific claims.

## 2. Evidence Governance Interchange Profile

Runtime version: `promomed-evidence-governance-interchange-v1`

Schema identifier: `urn:promomed:schema:evidence-governance-interchange:v1`

Repository schema: `docs/schemas/evidence-governance-interchange-v1.schema.json`

The profile contains artifact identity, source references, current reviewed claims, superseded/retracted history, source locators, evidence support type, disclosure records, reviewer role without exported reviewer identity, process approval state, current Evidence Seal hash, publication-hold state and explicit truth boundaries.

Current review-validity boundary is deliberately:

`reviewUntil = null`

with:

`reviewValidityPolicy = not_configured_in_current_authority`

The system does not invent an evidence-expiry policy that is not yet governed.

## 3. Reference Evidence Package

Runtime version: `promomed-reference-evidence-package-v1`

Schema identifier: `urn:promomed:schema:reference-evidence-package:v1`

Repository schema: `docs/schemas/reference-evidence-package-v1.schema.json`

A production package contains the Interchange Profile, immutable signed Evidence Checkpoint envelope, checkpoint/seal verification state at packaging, syndication rights boundary and deterministic package SHA-256.

Package creation fails closed when Evidence Seal is not process-valid, publication hold is active, no signed checkpoint exists, or the checkpoint is no longer current.

## 4. Synthetic reference fixture

Public route: `GET /api/evidence-interchange/reference`

Fixture schema identifier: `urn:promomed:schema:evidence-interchange-reference-fixture:v1`

Repository schema: `docs/schemas/evidence-interchange-reference-fixture-v1.schema.json`

The fixture deliberately uses a different schema from the production package so integration examples cannot be mistaken for signed production evidence.

This returns a deterministic non-clinical example of:

`source -> claim -> review -> disclosure -> approval -> package -> syndication -> correction -> withdrawal`

It is explicitly marked synthetic, non-clinical and non-production.

## 5. Institutional organisation authority

Institutional organisations are separate from the commercial `partners` table.

Supported organisation types include medical/scientific societies, universities, education partners, corporate learning teams, media/content partners, conference partners, knowledge platforms and strategic partners.

An institutional organisation may optionally reference an existing commercial partner, but commercial status does not grant scientific publishing rights.

## 6. Institutional role bindings

Supported scoped roles:

- `publisher`
- `consumer`
- `contributor`

Bindings contain organisation, scope, active state, effective/expiry time, governance verifier and source verification reference.

A role never grants permission to rewrite Promomed claims.

## 7. Package lifecycle

**Create:** governance creates a package over a process-valid canonical artifact with a current signed checkpoint.

**Deliver:** package delivery requires an active matching institutional role. A deterministic receipt binds package ID, package SHA-256, organisation ID, delivery role and delivered timestamp.

**Acknowledge:** delivery may be explicitly acknowledged.

**Supersede:** a new package for the same artifact supersedes the prior active package while retaining lineage.

**Withdraw:** high/critical evidence changes that place a publication hold automatically propagate downstream:

`canonical hold -> package withdrawn -> delivered/acknowledged copy withdrawn`

Historical packages remain retrievable for audit and are not silently deleted.

## 8. Public and governed surfaces

Public reads:

- `GET /api/evidence-interchange/reference`
- `GET /api/evidence-interchange/package?id=...`

Public verification:

- `POST /api/evidence-interchange/verify-portable`
- `ops/verify_evidence_package.py package.json issuer.json [status.json]`

Portable package verification recomputes the package SHA-256, validates schema/version identifiers, verifies the embedded signed checkpoint with public key material, checks the package-to-seal binding and confirms the non-rewrite authority boundary. It does not require Promomed database access or the signing private key and explicitly returns `currentCanonicalStateVerified=false`.

Governed read:

- `GET /api/institutional-network`

Governance mutations:

- `POST /api/institution/register`
- `POST /api/institution/role`
- `POST /api/evidence-interchange/package/create`
- `POST /api/evidence-interchange/package/deliver`
- `POST /api/evidence-interchange/package/acknowledge`
- `POST /api/evidence-interchange/package/withdraw`

## 9. Authority separation

Promomed controls source admission, claim state, review, disclosure, Evidence Seal, signed checkpoint, package issuance, supersession and withdrawal.

Institutional publishers may receive and distribute permitted projections, but may not rewrite scientific claims and continue to present them as Promomed-authoritative, suppress withdrawal state, convert a process seal into an efficacy/safety claim, or self-approve evidence.

Institutional consumers may ingest, verify, display within permitted use, acknowledge and respond to withdrawal. Consumer status grants no authoring authority.

## 10. Institutional graph

Existing graph:

`source -> claim -> review -> seal -> checkpoint`

New graph:

`artifact -> package -> organisation -> institutional role -> delivery -> acknowledgement/withdrawal`

Combined:

`source -> claim -> review -> seal -> signed checkpoint -> package -> institution -> downstream status`

## 11. Investor / commercial framing

Potential products enabled by the infrastructure:

- Evidence API
- reviewed institutional knowledge feed
- governed partner knowledge packs
- embedded evidence components
- professional education content distribution
- enterprise knowledge governance

Current truth:

- infrastructure is repository/CI capability;
- no external institution is claimed as onboarded;
- no contract, price, ARR, revenue forecast or market traction is claimed;
- external accreditation/certification remains separately sourced and governed.

## 12. Next dependency

The strongest next institutional step after v1 is:

**Certified Syndication Partner Network + External Contribution Admission**

but only after this package/role/withdrawal contract is merged and regression-proven.
