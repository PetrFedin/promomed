# Federated Trust Anchors v1 + Institution-Signed Verification Receipts

**Status:** repository implementation candidate  
**Base authority:** exact merged `main` after Partner Trust Bundle v1 — `bd642bd28ea974e9a5635d9a90cc3beb6c4c1868`.

## 1. Objective

Extend Promomed institutional trust from a Promomed-signed trust bundle into a federated chain where an external institution controls its own signing key.

Canonical flow:

`institution identity -> public key proposal -> proof-of-possession -> governance admission -> active federated anchor -> DID/JWKS-compatible publication -> institution-signed verification receipt -> offline chain verification`.

Promomed does **not** receive or store the external institution's private key.

## 2. Trust authority split

Three distinct authorities exist:

1. **Key possession** — the institution proves it controls the private key corresponding to the submitted Ed25519 public key.
2. **Institution binding** — Promomed governance decides whether that proven key is admitted as a trust anchor for a canonical institutional organisation.
3. **Verification receipt** — the institution may sign a receipt describing the exact Partner Trust Bundle result it independently obtained.

Possession does not imply governance admission.

Governance admission does not imply accreditation, endorsement or scientific authority.

## 3. Anchor lifecycle

Anchor version:

`promomed-federated-trust-anchor-v1`.

Lifecycle:

`pending_proof -> pending_governance -> active`

then one of:

`active -> retired`

`active -> suspended -> retired`

`active|suspended|retired|pending_* -> revoked`.

A new key may become active only after:

- explicit rotation lineage where a current active/suspended predecessor exists;
- proof-of-possession;
- governance activation.

Suspended predecessor state cannot be bypassed by proposing an unlinked "new first key".

## 4. Proof-of-possession

Promomed creates a random challenge and deterministic proof payload:

- proof version;
- anchor ID;
- canonical organisation ID;
- external issuer ID;
- key ID;
- algorithm;
- challenge.

The institution signs the canonical payload with its private Ed25519 key.

Promomed verifies the signature using only the supplied public key.

Successful proof changes state only to:

`pending_governance`.

It does not activate the anchor.

## 5. External private-key custody

Promomed stores:

- Ed25519 public key;
- key/issuer identity;
- proof challenge;
- proof signature;
- lifecycle timestamps;
- governance evidence / metadata;
- rotation lineage.

Promomed does **not** store:

- external private key;
- seed phrase;
- recovery secret;
- HSM credentials.

Public projections explicitly state:

`privateKeyStored = false`.

## 6. DID web-compatible publication

Promomed publishes a Promomed-hosted identity:

`did:web:<PROMOMED_TRUST_PUBLIC_HOST>:trust:<organization_id>`.

Default host in the current repository:

`sostoyanie-promomed-live.onrender.com`.

Production may override it through:

`PROMOMED_TRUST_PUBLIC_HOST`.

Resolution surface:

`GET /trust/<organization_id>/did.json`.

The DID document:

- uses the canonical Promomed organisation identity;
- includes Ed25519 verification methods;
- exposes current active keys in `assertionMethod`;
- retains historical non-pending key material for verification lineage;
- links to a public JWKS surface.

Important boundary:

The DID is **Promomed-hosted**. It does not claim control of an external university, society or partner domain.

## 7. JWKS-compatible publication

Public surface:

`GET /trust/<organization_id>/jwks.json`.

Each key uses:

- `kty=OKP`;
- `crv=Ed25519`;
- `alg=EdDSA`;
- public `x`;
- stable `kid`;
- Promomed anchor ID;
- lifecycle status;
- validity interval;
- rotation lineage.

Lifecycle metadata is an extension for Promomed trust semantics; standard JWKS consumers may ignore it.

## 8. Signed anchor-status statement

Promomed issues a portable Ed25519 statement:

`promomed-federated-anchor-status-v1`.

It binds:

- organisation identity;
- Promomed-hosted DID;
- all non-pending anchors;
- public key material;
- status;
- validity;
- rotation lineage;
- suspension/revocation evidence;
- short status validity window.

This status statement is signed by the existing Promomed evidence issuer/key authority.

It allows offline verification of:

`Promomed issuer -> admitted institutional anchor state`.

## 9. Institution-signed verification receipt

Receipt version:

`promomed-institution-signed-verification-receipt-v1`.

The external institution signs a deterministic receipt body containing:

- exact trust bundle ID;
- trust bundle SHA-256;
- exact snapshot SHA-256;
- verifier organisation ID;
- exact federated anchor / issuer / key identity;
- verification time;
- Partner Trust Bundle verification result;
- verification result digest;
- exact fresh status/issuer material used, if any;
- hashes of that verification material;
- explicit authority boundary.

Promomed verifies the institution signature and independently recomputes the Partner Trust Bundle result.

A receipt is rejected if the signed result cannot be reproduced.

## 10. Historical rotation semantics

Routine rotation:

`key v1 active -> key v2 proof -> governance activation -> key v1 retired -> key v2 active`.

A receipt signed by key v1 while v1 was active remains historically verifiable if:

- receipt verification time is inside v1 validity interval;
- v1 is retired, not revoked;
- signature remains valid.

Retirement is not revocation.

## 11. Suspension and revocation

A suspended or revoked anchor cannot admit a new institution-signed receipt.

Fresh Promomed anchor-status material exposes the changed trust state.

Offline verifier returns a distinct untrusted-anchor result when a fresh anchor-status statement marks the key:

- suspended;
- revoked.

No revoked/suspended key is silently treated as active.

## 12. Portable federation verifier

Reference verifier:

`ops/verify_institution_signed_receipt.py`.

Inputs:

1. institution-signed receipt;
2. exact Partner Trust Bundle;
3. fresh Promomed-signed anchor-status statement;
4. trusted Promomed issuer document.

Verification chain:

`Promomed issuer signature -> anchor status -> institution public key -> institution receipt signature -> exact trust-bundle result reproduction`.

No Promomed DB is required.

No private key is required.

## 13. Public / governed surfaces

Public:

- `GET /trust/<organization_id>/did.json`;
- `GET /trust/<organization_id>/jwks.json`;
- `GET /api/federation/receipt?id=...`;
- `POST /api/federation/receipt/verify-portable`.

Authenticated institution/governance:

- `POST /api/federation/anchor/propose`;
- `POST /api/federation/anchor/prove`;
- `POST /api/federation/receipt/submit`.

Governance only:

- `POST /api/federation/anchor/activate`;
- `POST /api/federation/anchor/suspend`;
- `POST /api/federation/anchor/revoke`;
- `POST /api/federation/anchor/status/issue`.

Internal governed registry:

- `GET /api/federation`.

## 14. Persistence authority

Migration:

`024_federated_trust_anchors`.

Immutable:

- anchor identity/public-key core;
- anchor lifecycle events;
- institution-signed verification receipts.

Mutable state is isolated in:

`institutional_federated_anchor_state`.

SQLite and PostgreSQL have equivalent lifecycle/status constraints and immutable-audit enforcement.

## 15. Machine-readable contracts

JSON Schema:

- `docs/schemas/federated-trust-anchor-v1.schema.json`;
- `docs/schemas/institution-signed-verification-receipt-v1.schema.json`.

OpenAPI 3.1:

`docs/openapi/federated-trust-v1.openapi.json`.

## 16. Security boundaries

Implemented:

- Ed25519 only in v1;
- proof-of-possession before governance activation;
- exact canonical payload signatures;
- no external private-key custody;
- rotation lineage;
- suspension/revocation state;
- receipt result recomputation;
- exact bundle/snapshot hash binding;
- immutable receipt audit;
- Promomed-signed anchor-status material.

Not claimed:

- external domain ownership;
- W3C conformance certification;
- accreditation;
- professional credential recognition;
- consortium membership;
- legal identity verification beyond admitted source evidence;
- medical/scientific endorsement.

## 17. Current production boundary

Repository/CI capability may be proven.

Current live Render service is **not** exact-main admitted at this checkpoint.

The live-proof workflow for `main@bd642bd28ea974e9a5635d9a90cc3beb6c4c1868` timed out because live `/health` remained at:

`148083d5ae03b8da2973efde6d5eceed8844d304`.

Repository `render.yaml` explicitly records that the existing service was created through Public Git and requires explicit deploy API triggering until the Git provider webhook is reconnected.

Therefore:

- current federation work remains repository-only;
- no production DID/JWKS endpoint is claimed;
- no production external anchor is claimed;
- no institution-signed production receipt is claimed.

## 18. Commercial consequence

Potential enterprise uses:

- portable partner due diligence;
- supplier / university / society key binding;
- procurement verification;
- federated evidence-distribution networks;
- institution-authenticated trust receipts;
- multi-organisation governance without shared private-key custody.

The moat is the accumulated verifiable chain:

`organisation -> admitted key -> rotation/revocation -> trust bundle -> independent result -> institution signature -> portable verification`.

## 19. Next dependency

After green repository merge and exact-main live restoration:

**Federation Interoperability Profile + Trust Anchor Discovery + External Pilot Admission**

with real non-demo institutional participation as the gate for any adoption claim.
