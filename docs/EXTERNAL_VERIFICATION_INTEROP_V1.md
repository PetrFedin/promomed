# External Verification Interoperability v1

**Status:** repository implementation in progress  
**Scope:** Promomed Evidence Governance checkpoint portability, issuer key lifecycle and external verification.  
**Authority boundary:** process/evidence provenance only. This layer does not certify medical efficacy, safety, diagnosis, treatment or clinical correctness.

## 1. Why this layer exists

The Evidence Governance Seal and signed checkpoint already prove that a reviewed artifact can be bound to a cryptographic envelope.

For institutional use, that is not enough if verification requires the same private signing key or if key rotation cannot be represented explicitly.

External Verification Interoperability v1 therefore separates:

- **issuer** — owns private signing material and creates checkpoints;
- **registry** — publishes public verification keys and key lifecycle;
- **status authority** — publishes checkpoint revocations;
- **verifier** — validates signatures using only public material;
- **canonical Promomed verification** — additionally checks whether the artifact is still current in Promomed authority.

## 2. Key lifecycle

Canonical table: `evidence_issuer_keys`.

Lifecycle:

`active -> retired`

or, for compromise/governance invalidation:

`active|retired -> revoked`

Rules:

- one `issuer_id + key_id` identifies exactly one public key;
- reusing a key ID with different public material fails closed;
- a new configured key must be explicitly activated when an issuer already has key history;
- activation retires the previous active key and records `rotated_from_key_id`;
- retired keys remain valid for checkpoints issued during their validity interval;
- revoked keys invalidate trust in checkpoints signed by that key;
- private key material is never persisted in the database or published by API.

## 3. Issuance registry

Canonical table: `evidence_checkpoint_issuance`.

Each issued checkpoint records:

- checkpoint SHA-256;
- issuer ID;
- key ID;
- artifact kind/ref;
- issued timestamp;
- seal SHA-256.

This allows status publication and audit without storing the private key.

## 4. Public verification material

Public GET surfaces:

- `/api/evidence-checkpoint/public-key` — current active key convenience document;
- `/api/evidence-checkpoint/issuer` — issuer document including active/retired/revoked public keys;
- `/api/evidence-checkpoint/status-list` — key lifecycle plus revoked checkpoint list;
- `/api/evidence-checkpoint/checkpoint?sha256=...` — the immutable signed envelope originally issued for that checkpoint.

Issued envelopes are persisted with their canonical payload and signature so they remain retrievable after routine signing-key rotation. Historical retrieval never requires loading an old private key.

The issuer/status documents contain no private signing material.

## 5. Verification modes

### Portable verification

POST `/api/evidence-checkpoint/verify-portable`

Input:

- checkpoint envelope;
- trusted issuer document;
- optional current status list.

Checks:

- checkpoint schema/version;
- issuer/key binding;
- Ed25519 signature;
- envelope SHA-256;
- key validity interval at issuance;
- key revocation;
- checkpoint revocation.

Success state:

`VALID_PORTABLE`

Important boundary:

Portable verification proves that the envelope was signed by the stated issuer key and is not revoked according to the supplied status material. It **does not** prove that the artifact is still the current canonical Promomed version.

The result therefore exposes:

`currentCanonicalStateVerified = false`.

### Canonical Promomed verification

POST `/api/evidence-checkpoint/verify`

Performs portable cryptographic/status verification and additionally checks:

- publication hold;
- current Evidence Seal state;
- current evidence package hash.

Success state:

`VALID`

with:

`current = true`.

## 6. Offline verifier

`ops/verify_evidence_checkpoint.py`

Usage:

`python ops/verify_evidence_checkpoint.py envelope.json issuer.json [status.json]`

The CLI requires no signing private key.

Exit codes:

- 0 — `VALID_PORTABLE`;
- 1 — verification failed / revoked / unknown key;
- 2 — usage error.

## 7. Public HTTP routing

Verification endpoints are deliberately routed before account authentication.

This is required for external verification by partner systems that do not hold a Promomed user session.

Editorial/key-management mutation endpoints remain role-gated.

## 8. Trust bootstrap and current v1 boundary

The verifier must receive the issuer/status documents from a trusted channel, such as the canonical Promomed HTTPS endpoint or an independently pinned copy.

v1 verifies checkpoint signatures cryptographically but does **not yet sign the issuer/status documents themselves**.

A future interoperability layer may add:

- signed issuer metadata;
- signed/append-only status snapshots;
- trust-anchor pinning;
- JWKS/VC/DID-compatible publication profiles where justified;
- institutional cross-signing.

Those are not claimed as implemented in v1.

## 9. Acceptance criteria

- external verification never loads the issuer private key;
- old checkpoints remain verifiable after routine key rotation;
- key compromise can invalidate affected checkpoints;
- checkpoint revocation is externally visible;
- key-ID collision fails closed;
- public routes work without Promomed login;
- current canonical state is not confused with portable signature validity;
- medical efficacy certification remains explicitly false;
- SQLite and PostgreSQL share the same schema semantics.
