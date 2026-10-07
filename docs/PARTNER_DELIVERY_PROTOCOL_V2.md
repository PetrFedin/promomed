# Partner Delivery Protocol v2 + Continuous Requalification

**Status:** repository implementation candidate  
**Base:** exact synchronized `main` after PR #40 merge and master-plan sync: `6acd73b3f37eeecf6e82e2001db69418e9ca9eee`.

## 1. Purpose

This layer turns Certified Syndication Partner status into an operationally observed integration protocol.

Flow:

`qualified institution -> verified HTTPS endpoint -> immutable delivery event -> signed webhook attempt -> retry/backoff -> partner-signed acknowledgement -> cursor advancement -> SLA evidence -> behaviour scorecard -> requalification trigger`.

It does not grant partners authority over Promomed canonical scientific content.

## 2. Endpoint registry

Endpoint registration is governance-only.

Required:

- existing active institutional organisation;
- explicit HTTPS URL;
- matching demo/production boundary;
- Promomed webhook master secret configured.

Registration returns:

- endpoint metadata;
- verification challenge;
- endpoint secret **once**.

Subsequent read projections never expose:

- secret;
- secret hash;
- verification challenge;
- governance account identities.

An idempotent registration replay returns no secret. Recovery requires explicit secret rotation.

## 3. Secret derivation and rotation

Endpoint webhook secrets are derived from server-side master secret using:

`HMAC-SHA256(master, protocolVersion | endpointId | secretVersion)`.

The derived endpoint secret is returned to the integration only at registration or explicit rotation.

The database stores only the current secret hash and version.

Every concrete delivery attempt stores the secret version used for that attempt. This allows an acknowledgement for a previously delivered event to remain verifiable after routine endpoint secret rotation.

## 4. Endpoint verification

Pending endpoints are activated only after a signed challenge round-trip.

Promomed sends:

- JSON challenge body;
- event ID;
- payload SHA-256;
- timestamp;
- protocol version;
- webhook signature.

The partner endpoint must return the exact challenge, either as raw text or JSON:

`{"challenge":"..."}`.

Endpoint verification uses HTTPS only.

Before default outbound transport, host DNS resolution is checked and non-global addresses are rejected. Loopback/private/link-local/reserved addresses are not accepted as webhook targets.

Production deployments should still use controlled egress/DNS policy because application-layer pre-resolution alone is not a substitute for network-level egress controls.

## 5. Immutable event identity

Event types:

- `package_delivery`;
- `package_update`;
- `package_withdrawal`;
- `contribution_admission`;
- `qualification_status`.

Business event identity is deterministic over:

- institution;
- event type;
- subject;
- obligation identity;
- canonical data SHA-256.

Retry never creates another business event.

The event core is immutable at database level.

Mutable state is stored separately:

`queued -> delivered -> acknowledged`

or:

`queued -> dead`.

## 6. Sequence and cursor

Each organisation has a monotonically increasing delivery sequence.

Promomed maintains:

- `next_sequence`;
- `last_acked_sequence`.

An acknowledgement may arrive out of order and is still preserved, but the cursor advances only through contiguous acknowledged sequence numbers.

Therefore acknowledging sequence 12 does not skip an unacknowledged sequence 11.

## 7. Webhook signature

Request headers include:

- `X-Promomed-Protocol`;
- `X-Promomed-Event-Id`;
- `X-Promomed-Sequence`;
- `X-Promomed-Timestamp`;
- `X-Promomed-Payload-SHA256`;
- `X-Promomed-Signature`;
- `X-Promomed-Secret-Version`.

Signature input:

`timestamp + "." + eventId + "." + payloadSha256`

Signature:

`v1=HMAC-SHA256(endpointSecret, signingInput)`.

The receiver must independently hash the raw request body and compare it to `X-Promomed-Payload-SHA256` before trusting the signature binding.

## 8. Retry and failure classification

Maximum attempts: **8**.

Retry schedule:

- 60 s;
- 300 s;
- 900 s;
- 3600 s;
- 10800 s;
- 21600 s;
- 21600 s;
- 21600 s.

Retryable responses:

- HTTP 408;
- HTTP 425;
- HTTP 429;
- HTTP 5xx;
- transport exception.

HTTP 2xx is delivery success.

Other HTTP 4xx responses are terminal failures.

Every attempt is append-only and records:

- attempt number;
- secret version;
- request timestamp/signature;
- send/complete times;
- HTTP status;
- response digest;
- failure class;
- next retry time.

## 9. Partner acknowledgement

Partner acknowledgement is intentionally public from the Promomed-session perspective: the external machine does not need a Promomed user account.

It is authenticated by endpoint-specific HMAC instead.

Ack payload:

`eventId`  
`payloadSha256`  
`status = accepted`.

Acknowledgement signature uses the same canonical signature formula, but signs the SHA-256 of the canonical acknowledgement body.

Promomed verifies against the secret version of the **successful delivery attempt** being acknowledged.

This preserves valid acknowledgements across routine secret rotation.

Acknowledgements are immutable and idempotent.

## 10. Automatic SLA evidence

If an event is bound to a syndication update/withdrawal obligation, accepted acknowledgement automatically writes:

`evidence_ref = delivery-event:<eventId>`.

If the SLA deadline has already passed:

- the acknowledgement is still preserved;
- the obligation remains `breached`;
- a critical behaviour observation is recorded.

Late evidence is evidence of execution, not retroactive evidence of SLA compliance.

## 11. Lifecycle integration

The protocol is wired into existing authority transitions:

### Evidence package delivery

`deliver_package -> package_delivery event`.

### Package supersession

`supersession -> update obligation -> package_update event`.

### Evidence withdrawal / source retraction

`withdrawal -> withdrawal obligation -> package_withdrawal event`.

The same path is used when withdrawal originates from Change Impact Engine.

### External contribution admission

`governance admission -> signed admission receipt -> contribution_admission event`.

If a qualified organisation has no verified active endpoint, canonical governance action still succeeds and no outbound event is claimed.

## 12. Behaviour observations

Append-only observations include:

- delivery success;
- retryable failure;
- terminal failure;
- acknowledgement success;
- late acknowledgement;
- SLA breach;
- dead event.

These records describe integration behaviour only.

They do not measure:

- medical efficacy;
- clinical quality;
- commercial outcomes.

## 13. Continuous requalification

Current deterministic rule version:

`promomed-delivery-behaviour-requalification-v1`.

Within a 30-day observation window, requalification is triggered when any applies:

- at least 2 SLA breaches;
- at least 2 dead delivery events;
- at least 10 retryable failures;
- any withdrawal SLA breach.

A withdrawal SLA breach or at least 3 dead events additionally creates:

`suspensionReviewRecommended = true`.

Automatic effects are deliberately limited:

- system **may** move `qualified -> requalification_due`;
- system does **not** automatically suspend;
- system does **not** automatically revoke.

Suspension/revocation remain governance authority.

## 14. Worker model

Worker:

`ops/run_partner_delivery_worker.py`.

One execution:

1. reads due queued events;
2. dispatches with signed webhook protocol;
3. stores append-only attempts;
4. reconciles overdue SLA obligations;
5. emits behaviour observations;
6. evaluates requalification evidence;
7. commits durable state.

Scheduling is deployment-platform responsibility.

The worker is intentionally stateless; queue/cursor/retry state lives in PostgreSQL/SQLite authority.

## 15. Security boundary

Implemented safeguards:

- HTTPS-only endpoint registration;
- no URL userinfo;
- no URL fragments;
- non-global resolved IP rejection in default outbound transport;
- secrets never returned from read projections;
- one-time secret issuance on registration/rotation;
- per-attempt secret version binding;
- raw response stored only as SHA-256 digest;
- no external response body persisted;
- signed acknowledgement instead of user-session impersonation;
- immutable event/attempt/ack/observation audit tables.

Remaining production infrastructure dependency:

- controlled outbound egress / DNS policy is still recommended to eliminate DNS-rebinding class risk beyond application-level resolution checks.

## 16. Machine-readable contracts

JSON Schema:

- `docs/schemas/partner-delivery-event-v2.schema.json`;
- `docs/schemas/partner-delivery-ack-v2.schema.json`.

OpenAPI 3.1:

`docs/openapi/partner-delivery-v2.openapi.json`.

Internal observability:

`GET /api/syndication/delivery-runtime`.

Public signed acknowledgement:

`POST /api/syndication/delivery/acknowledge`.

## 17. Truth boundary

Repository implementation may become CI-PROVEN.

This checkpoint does **not** claim:

- any real partner endpoint is registered;
- any production webhook has been sent;
- any external traffic or uptime;
- any SLA has been achieved in production;
- any production partner has passed behaviour-based requalification;
- any contract, paid subscription, ARR, MRR or revenue.

## 18. Commercial consequence

The Certified Syndication Partner Network can now evolve from static conformance evidence into an operational service level:

**deliver -> observe -> acknowledge -> prove -> requalify**.

That creates a stronger enterprise moat than a badge alone because accumulated delivery history, correction responsiveness and requalification evidence become part of the institutional relationship.

## 19. Next strong layer

After green merge, the next institutional step should be:

**Signed Status Snapshots + Partner Trust Bundle + Cross-Organisation Verification**

so an external institution can independently verify:

- current partner certification state;
- endpoint protocol version;
- delivery cursor checkpoint;
- recent SLA status;
- revocation/requalification state;

without access to internal Promomed database.
