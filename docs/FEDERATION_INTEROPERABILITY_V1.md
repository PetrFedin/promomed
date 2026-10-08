# Federation Interoperability Profile v1 + Trust Anchor Discovery

**Status:** repository implementation candidate  
**Base authority:** live-proven `main@f71f73d6aca36928844fee81d6b2ba7227b33a6a`.

## 1. Purpose

This layer makes Promomed federation capabilities machine-discoverable without turning discovery into trust admission.

Canonical flow:

`profile definition -> public discovery manifest -> scoped organisation discovery -> deterministic compatibility evaluation -> signed discovery bundle -> offline verification`.

A discovered key is never automatically admitted as a trust anchor.

## 2. Interoperability profile

Profile:

`promomed-federation-interop-v1`.

The profile fixes:

- canonical institutional identity semantics;
- supported DID method;
- Ed25519 / OKP / EdDSA cryptography;
- external private-key custody expectations;
- supported Promomed portable statement types;
- institution-signed receipt version;
- anchor lifecycle semantics;
- freshness expectations;
- public interoperability surfaces;
- governance/admission boundaries.

The profile body is deterministic and has a canonical SHA-256.

A material contract change requires a new profile version; the same version may not silently change its hash.

## 3. Read path is side-effect free

Public:

`GET /api/federation/profile`

and:

`GET /.well-known/promomed-federation.json`

are deterministic projections.

They do not create or mutate persistence authority.

The immutable persisted profile is created only through governed evaluation/issuance paths.

## 4. Public discovery manifest

Surface:

`/.well-known/promomed-federation.json`.

It publishes:

- discovery version;
- active profile identity/hash;
- profile URL;
- Promomed DID/JWKS patterns;
- institution-signed receipt surface;
- portable verification endpoint;
- explicit truth boundary.

It does not enumerate all organisations or all anchors.

## 5. Scoped trust-anchor discovery

Surface:

`GET /api/federation/discovery?organization_id=...`.

An organisation ID is mandatory.

The response may include only already-admitted non-pending public material:

- anchor ID;
- institution ID;
- issuer/key ID;
- Ed25519 public key;
- lifecycle status;
- proof-of-possession verified flag;
- validity interval;
- rotation lineage;
- Promomed-hosted DID;
- JWKS URL;
- current DID/JWKS projection.

Never returned:

- private keys;
- proof challenge;
- proof signature;
- internal membership evidence;
- governance account identity.

No bulk public federation address book is exposed.

## 6. Compatibility evaluation

Governed evaluation:

`POST /api/federation/compatibility/evaluate`.

Possible statuses:

- `compatible`;
- `compatible_with_warnings`;
- `incompatible`;
- `no_active_anchor`.

Current deterministic checks include:

- active anchor exists;
- supported Ed25519 algorithm;
- proof-of-possession verified;
- validity window is current;
- historical rotation lineage consistency.

Compatibility evaluation is append-only evidence.

It cannot:

- admit a new anchor;
- change qualification;
- create accreditation;
- create endorsement.

## 7. Signed discovery bundle

Governed issuance:

`POST /api/federation/discovery-bundle/issue`.

Statement type:

`promomed-federation-discovery-bundle-v1`.

The signed body binds:

- exact organisation ID;
- exact interoperability profile ID/version/hash;
- exact compatibility evaluation;
- admitted public anchors;
- DID document;
- JWKS document;
- issue/expiry times;
- explicit truth boundary.

The bundle uses the existing Promomed Ed25519 evidence issuer.

## 8. Portable verification

Public verification:

`POST /api/federation/discovery-bundle/verify-portable`.

Reference CLI:

`ops/verify_federation_discovery_bundle.py`.

Verification requires:

- discovery bundle;
- trusted Promomed issuer document.

It verifies:

- Promomed signature;
- statement type;
- bundle version;
- expiry;
- interoperability profile version;
- canonical profile SHA-256.

No Promomed database or private key is required.

## 9. Persistence authority

Migration:

`025_federation_interoperability`.

Immutable tables:

- `federation_interoperability_profiles`;
- `federation_profile_evaluations`;
- `federation_discovery_bundles`.

SQLite and PostgreSQL carry equivalent state and immutability contracts.

## 10. Machine-readable contracts

JSON Schema:

- `docs/schemas/federation-interoperability-profile-v1.schema.json`;
- `docs/schemas/federation-discovery-bundle-v1.schema.json`.

OpenAPI 3.1:

`docs/openapi/federation-interoperability-v1.openapi.json`.

## 11. Truth boundary

Interoperability compatibility proves protocol compatibility only.

It does **not** prove:

- accreditation;
- endorsement;
- legal identity certification;
- medical/scientific quality;
- regulator approval;
- consortium membership;
- commercial relationship;
- real external adoption.

Discovery does not admit a key.

A synthetic/demo organisation may prove mechanics only.

## 12. External pilot gate

A real external pilot remains blocked until a non-demo institution supplies:

- attributable institutional identity;
- independently controlled public key;
- proof-of-possession;
- governance-admissible source evidence;
- explicit participation in the pilot.

Only then may Promomed record a real external anchor or pilot evidence.

## 13. Commercial consequence

This layer lowers institutional integration friction:

**discover capabilities -> resolve public trust material -> evaluate compatibility -> verify portable bundle**

without exposing internal database authority and without weakening trust-anchor governance.

## 14. Next dependency

After green merge/live proof:

**External Pilot Admission Profile + Partner Onboarding Evidence Pack**

but implementation must remain gated until a real non-demo institutional participant exists.
