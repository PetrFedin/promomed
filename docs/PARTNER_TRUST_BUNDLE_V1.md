# Partner Trust Bundle v1 + Cross-Organisation Verification

**Status:** repository implementation candidate  
**Base authority:** synchronized `main` checkpoint `c6bd68a497ad1761ca534d322c0ecdcb4b0313b1`.

## 1. Objective

This layer makes institutional trust state portable without exposing Promomed's internal database.

Canonical flow:

`institution state -> deterministic projection -> signed status snapshot -> signed snapshot-status statement -> immutable trust bundle -> offline verification -> external verification receipt`.

It extends the Certified Syndication Partner Network and Partner Delivery Protocol. It does not replace those authorities.

## 2. Signed institutional status snapshot

Snapshot statement type:

`promomed-institutional-status-snapshot-v1`.

The signed body contains:

- institutional organisation identity;
- current qualification state and validity;
- public process certification scopes;
- Partner Delivery Protocol version;
- endpoint lifecycle counts without URLs/secrets/challenges;
- acknowledgement cursor checkpoint;
- explicit observation-window duration;
- event / acknowledgement / attempt aggregates;
- retry / terminal-failure / behaviour observations;
- requalification and suspension-review indicators;
- explicit truth boundary.

A snapshot stores no webhook secret, endpoint secret hash or verification challenge.

## 3. Stable state fingerprint

Snapshot idempotency is based on a deterministic SHA-256 fingerprint of material institutional state.

Wall-clock-only fields such as observation-window start/end are deliberately excluded from the state fingerprint.

Therefore:

- no material state change -> current unexpired snapshot is replayed;
- material state change -> a new signed snapshot is issued.

## 4. Snapshot lifecycle

Immutable core and mutable status are separate.

Core:

`institutional_status_snapshots`.

Status:

`current / superseded / revoked`.

A new snapshot supersedes the previous historical snapshot while preserving the old immutable signed envelope.

A revoked predecessor remains `revoked`; issuing a new snapshot does not rewrite it to `superseded`.

The new snapshot still records the revoked predecessor in `supersedes_snapshot_id`, preserving lineage.

## 5. Snapshot status statement

Statement type:

`promomed-institutional-snapshot-status-v1`.

This is a short-lived signed projection over an organisation's snapshot registry.

It records, for each known snapshot:

- snapshot ID/hash;
- issue/expiry time;
- current/superseded/revoked state;
- revocation time/reason where applicable.

This statement is separate from the immutable snapshot itself.

That separation allows revocation to become visible without rewriting the originally signed snapshot.

## 6. Partner Trust Bundle

Bundle schema:

`urn:promomed:schema:partner-trust-bundle:v1`.

Bundle version:

`promomed-partner-trust-bundle-v1`.

An immutable bundle contains:

- exact signed status snapshot;
- issuer public-key document as packaged;
- issuer status material as packaged;
- signed snapshot-status statement as packaged;
- explicit schema/version identifiers;
- deterministic bundle SHA-256;
- truth boundary.

One immutable bundle is created per exact snapshot.

## 7. Historical validity vs current-state verification

This distinction is mandatory.

### Historical / packaged verification

A standalone trust bundle can prove:

- bundle hash integrity;
- snapshot signature integrity;
- issuer/key identity as supplied in the bundle;
- snapshot expiry;
- snapshot status according to the signed status statement embedded at packaging time.

It returns:

`currentPromomedStateVerified = false`.

This is intentional. An old offline file cannot prove that Promomed has not revoked or superseded it since packaging.

### Current-state verification

To assert current state, the verifier supplies:

- a fresh signed snapshot-status statement;
- a fresh trusted issuer document.

Only then may verification return:

`currentPromomedStateVerified = true`.

## 8. Revocation states are distinct

The verifier distinguishes:

- invalid bundle hash;
- invalid signature;
- unknown issuer/key;
- revoked issuer key;
- expired snapshot;
- revoked snapshot;
- valid trust bundle.

Snapshot revocation, qualification revocation and issuer-key revocation are separate authorities.

No one state is silently substituted for another.

## 9. Key rotation

Snapshots reuse Promomed's existing Ed25519 issuer/key lifecycle.

Historical snapshots remain cryptographically verifiable after routine key rotation when their issuing key remains valid for the issuance interval.

If a fresh trusted issuer document marks the issuing key revoked, the result becomes:

`REVOKED_ISSUER_KEY`.

## 10. Cross-organisation verification receipt

A verifier organisation may record a verification receipt over one exact trust bundle.

Authorised verifier actors are:

- active Promomed governance account; or
- active verified `operator` / `administrator` membership of the verifier organisation.

Receipt binds:

- exact bundle ID/hash;
- exact snapshot hash;
- verifier organisation;
- verification result.

Duplicate verification of the same bundle/result by the same verifier organisation is idempotent.

## 11. Authority separation

A verifier receipt does not:

- alter partner qualification;
- alter evidence/claims;
- alter issuer/key status;
- alter snapshot status;
- create professional accreditation;
- create commercial endorsement;
- create medical efficacy/safety certification.

Verifier identity is source-attributed only.

## 12. Public and governed surfaces

Public exact reads:

- `GET /api/trust/snapshot?id=...`;
- `GET /api/trust/bundle?id=...`.

Public verification:

- `POST /api/trust/verify-portable`.

Governed operations:

- `POST /api/trust/snapshot/issue`;
- `POST /api/trust/snapshot/revoke`;
- `POST /api/trust/status/issue`;
- `POST /api/trust/bundle/create`;
- `POST /api/trust/verification/record`.

Governed aggregate:

- `GET /api/trust-network`.

## 13. Offline verifier

Reference verifier:

`ops/verify_partner_trust_bundle.py`.

Packaged-state mode:

`python ops/verify_partner_trust_bundle.py bundle.json`.

Current-state mode:

`python ops/verify_partner_trust_bundle.py bundle.json fresh-status.json fresh-issuer.json`.

No Promomed DB or signing private key is required.

## 14. Machine-readable contracts

JSON Schema:

- `docs/schemas/institutional-status-snapshot-v1.schema.json`;
- `docs/schemas/partner-trust-bundle-v1.schema.json`;
- `docs/schemas/trust-verification-receipt-v1.schema.json`.

OpenAPI 3.1:

`docs/openapi/partner-trust-v1.openapi.json`.

## 15. Persistence authority

Migration:

`023_partner_trust_bundle` for SQLite and PostgreSQL.

Immutable audit surfaces:

- signed snapshot core;
- snapshot lifecycle events;
- trust bundle;
- cross-organisation verification receipt.

Mutable state is limited to explicit snapshot status.

## 16. Truth boundary

Repository implementation / CI can prove protocol mechanics only.

This layer does **not** claim:

- a production institution has received a trust bundle;
- an external institution has verified one;
- a consortium or accreditation body has adopted the protocol;
- Promomed has obtained external certification;
- any medical efficacy or safety conclusion;
- any paid trust service, contract, ARR/MRR or revenue.

## 17. Investor / commercial consequence

Potential future enterprise products include:

- partner due-diligence trust packs;
- procurement verification packs;
- independently verifiable partner onboarding;
- governed knowledge-network federation;
- embedded partner-status verification;
- institutional compliance evidence exchange.

The defensibility comes from accumulated signed history:

`qualification -> delivery behaviour -> snapshot -> supersession/revocation -> external verification`.

## 18. Next dependency

After this layer is merged and regression-proven, the next strong interoperability layer is:

**Federated Trust Anchors + DID/JWKS-compatible Publication + Institution-Signed Verification Receipts**

but only with explicit trust-anchor governance and no invented accreditation relationships.
