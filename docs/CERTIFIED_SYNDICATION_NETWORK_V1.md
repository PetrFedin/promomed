# Certified Syndication Partner Network + External Contribution Admission v1

**Status:** repository implementation candidate  
**Base:** exact `main` after PR #39 merge: `be47c32be4d8972cff5e64e959a6a1df844fc2c8`  
**Scope:** institutional qualification, conformance, subscriptions, update/withdrawal SLA, external contribution review/admission, requalification/suspension/revocation.  
**Truth boundary:** technical/process certification only. No medical efficacy, safety, diagnosis, treatment, regulator approval, professional accreditation or commercial endorsement is inferred.

## 1. Institutional adoption contour

`institution identity -> verified member -> qualification -> conformance -> certified status -> evidence subscription -> package delivery -> update/withdrawal obligation -> acknowledgement / breach -> requalification / suspension / revocation`

External contribution contour:

`verified contributor -> immutable submission -> editorial review -> scientific review -> governance admission -> signed admission receipt -> domain workflow`

Admission does **not** write directly into canonical claims or sources.

## 2. Qualification standard

Runtime version:

`promomed-syndication-qualification-v1`

Required conformance scopes:

- Evidence API Integration;
- Withdrawal Propagation;
- Disclosure Workflow.

Optional scoped certifications:

- Credential Verification;
- Education Completion Sync.

A required scope cannot be waived.

A passed conformance check requires an evidence reference.

Qualification lifecycle:

`pending -> qualified -> requalification_due -> qualified`

or:

`qualified -> suspended -> new qualification cycle`

or:

`qualified|suspended -> revoked`

or:

`qualified -> expired`.

Routine requalification may reuse the same standard version. Qualification version is not a one-time identity.

## 3. Public certification registry

Public route:

`GET /api/syndication/certification?organization_id=...`

Published fields include:

- organisation identity;
- qualification state;
- qualification version;
- effective / valid-until / requalification timestamps;
- passed certification scopes;
- explicit process-only truth boundary.

Internal conformance evidence references and reviewer/checker identities are not exposed by the public projection.

Schema:

`docs/schemas/syndication-certification-v1.schema.json`

## 4. Institutional account membership

An `organization_id` supplied by a client is not trusted by itself.

Governance binds an authenticated Promomed account to an institution through:

`account -> organisation -> member role -> validity -> verification reference`

Member roles:

- `contributor`;
- `operator`;
- `administrator`.

This authority is separate from institutional publisher/consumer/contributor roles.

Organisation role answers **what the institution is allowed to do**.  
Membership answers **which authenticated human account may act for that institution**.

## 5. Subscriptions

Certified organisations with an active `consumer` or `publisher` institutional role may create subscriptions scoped to:

- all evidence;
- artifact kind;
- exact artifact;
- topic.

Each subscription defines:

- update SLA;
- withdrawal SLA;
- effective/expiry time.

A subscription is considered matchable only while the organisation remains currently `qualified`.

`requalification_due`, `expired`, `suspended` and `revoked` states stop certified matching.

## 6. Update / withdrawal obligations

Package supersession creates an `update` obligation for matching certified subscriptions.

Package withdrawal creates a `withdrawal` obligation.

Each obligation records:

- delivery;
- obligation type;
- due time;
- acknowledgement time;
- acknowledgement evidence reference;
- state.

States:

`pending -> acknowledged`

or:

`pending -> breached`.

An acknowledgement after the deadline remains evidence, but the state is `breached`; lateness is not silently converted into success.

## 7. External contribution types

Qualified institutions with active institutional `contributor` role and verified contributor membership may submit:

- source recommendation;
- review input;
- disclosure record;
- programme material;
- correction notice;
- institutional metadata.

Every submission is canonicalized and SHA-256 bound.

Exact duplicate payloads are idempotent replays, not new submissions.

## 8. Review authority

External contributors cannot self-approve.

Every contribution requires:

1. editorial review;
2. scientific review;
3. governance admission.

Editorial review requires an active editor/governance account.

Scientific review uses the existing Reviewer Authority and scope:

`external_contribution.general`.

Production scientific review therefore inherits existing reviewer requirements:

- verified reviewer identity;
- active reviewer profile;
- independently attested reviewer where production requires it;
- non-expired credential;
- active review scope.

Conflict state is explicit:

- none;
- potential;
- material.

A potential/material conflict cannot be accepted.

Editorial and scientific reviewers must be distinct.

The submitter cannot review their own submission.

The governance actor admitting the contribution cannot be the submitter or either reviewer.

## 9. Signed admission receipt

After independent editorial + scientific acceptance, governance may admit the contribution into the governed downstream queue.

The receipt is a portable Ed25519 statement using the existing issuer/key lifecycle.

Statement type:

`promomed-external-contribution-admission-v1`

Receipt body binds:

- contribution ID;
- institution;
- contribution type;
- payload SHA-256;
- editorial review digest;
- scientific review digest;
- admission decision;
- downstream authority.

Critical fields:

`canonicalMutation = false`

`nextAuthority = domain_editorial_evidence_workflow`

`medicalEfficacyCertified = false`.

Admission means the contribution passed intake governance. It does **not** mean that a claim was published, a source was accepted as scientific truth or a medical statement was approved.

Schema:

`docs/schemas/external-contribution-admission-receipt-v1.schema.json`

## 10. Independent verification

Public verification:

`POST /api/external-contribution/receipt/verify-portable`

The verifier needs:

- admission receipt;
- trusted Promomed issuer document.

It does not require:

- Promomed database access;
- signing private key;
- contributor account.

Receipt retrieval:

`GET /api/external-contribution/receipt?contribution_id=...`

## 11. Suspension and revocation

Suspension:

- marks qualification suspended;
- pauses active subscriptions;
- blocks new certified subscriptions and contributions.

Revocation:

- marks qualification revoked;
- revokes active/paused subscriptions;
- blocks new certified operations.

Historical certification, contribution and receipt records remain available for audit.

They are not deleted to make the history look cleaner.

## 12. Requalification

A qualification has both:

- `valid_until`;
- `next_requalification_at`.

When requalification becomes due, certified subscription matching stops until the mandatory conformance set is passed again.

This prevents an old integration test from being treated as permanent certification.

## 13. Machine-readable contract

OpenAPI 3.1:

`docs/openapi/certified-syndication-v1.openapi.json`

Core routes:

- `GET /api/syndication/certification`
- `GET /api/syndication-network`
- `POST /api/institution/member`
- `POST /api/syndication/qualification/start`
- `POST /api/syndication/qualification/conformance`
- `POST /api/syndication/qualification/finalize`
- `POST /api/syndication/qualification/suspend`
- `POST /api/syndication/qualification/revoke`
- `POST /api/syndication/subscription`
- `POST /api/syndication/obligation/acknowledge`
- `POST /api/external-contribution/submit`
- `POST /api/external-contribution/review`
- `POST /api/external-contribution/admit`
- `GET /api/external-contribution/receipt`
- `POST /api/external-contribution/receipt/verify-portable`.

## 14. Investor / commercial consequence

This layer enables future commercial products such as:

- qualified Evidence API distribution;
- governed knowledge feeds;
- certified partner integrations;
- enterprise knowledge subscriptions;
- external expert/institution contribution programmes;
- auditable correction/withdrawal service levels.

Current truth:

- repository capability may be CI-proven;
- no production partner is claimed as qualified;
- no external institution is claimed as adopted;
- no paid subscription, contract, ARR, MRR or revenue is claimed;
- process certification is not medical or professional accreditation.

## 15. Next dependency

After this layer is merged and green, the next strong institutional step is:

**Partner Delivery Protocol v2 + Webhook/Event Delivery + Continuous Requalification**

with:

- signed delivery events;
- partner endpoint registration;
- retry/idempotency contract;
- webhook signature verification;
- per-partner delivery cursor;
- automatic SLA evidence;
- requalification based on observed production behaviour rather than questionnaire-only proof.
