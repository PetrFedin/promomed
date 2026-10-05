# Corporate Security / Privacy / Vendor Due Diligence Pack
Date: 2026-10-05
Status: evidence-backed readiness pack; **not a certification**.

## 1. Purpose

This pack prepares СОСТОЯНИЕ for structured corporate review by:
- Information Security;
- Privacy / Legal;
- Procurement;
- Enterprise Architecture;
- Operations / BCP;
- Investment Committee / CVC.

It separates:
- implemented and test-backed controls;
- executable demo controls;
- production controls that remain to be prepared;
- claims that are explicitly not made.

## 2. Current truth boundary

Current state before Phase 0 COMPLETE:

**PRE-PRODUCTION SECURITY REVIEW**

Allowed claims:
- authentication/session controls are implemented and CI-proven;
- role and consent boundaries have negative tests;
- PostgreSQL 17 migration, backup, isolated restore and fingerprint equivalence are CI-proven;
- readiness is fail-closed;
- exact-SHA public release proof exists.

Not allowed:
- security certification;
- approved production RTO/RPO;
- approved DPA/SLA;
- centralized SIEM maturity;
- production medical governance;
- production durable PostgreSQL until Phase 0 live admission is complete.

## 3. Evidence-backed controls

### Identity
- salted scrypt password hashes;
- constant-time password verification;
- random bearer sessions;
- SHA-256 session-token hash at rest;
- session TTL;
- session revocation;
- expired/revoked session cleanup;
- production-account bootstrap and password rotation proven in PostgreSQL CI.

### Authorization
- command handlers enforce role boundaries;
- negative tests cover representative participant, organizer, editor and demo-control actions.

### Consent / privacy boundary
- partner lead and product-interest continuation rejects missing consent;
- participant-to-participant direct messaging requires an allowed mutual relationship path;
- strategic-partner model does not imply hidden access to sensitive health data or silent contact export.

### Data integrity
- schema migrations are versioned;
- migration checksums are stored;
- checksum drift fails readiness/migration flow.

### Continuity
- PostgreSQL 17 backup is created in CI;
- backup is restored into an isolated database;
- source and restore catalog SHA-256, row counts and migration-version fingerprints must match.

### Release
- production readiness is true only when schema is complete, backend is durable, migration checksum drift is absent, demo seed is off and demo accounts are absent;
- public release proof checks exact git SHA and readiness;
- deploy-provider handoff timeout is distinguished from runtime-readiness failure.

## 4. Controls still to prepare before production approval

The following are intentionally **not** presented as completed:

- formal production incident-response runbook;
- incident severity / escalation / notification procedures;
- approved RTO and RPO;
- vendor/subprocessor inventory and approval;
- production DPA / SLA / support terms;
- documented encryption-at-rest / key-management evidence;
- SBOM and dependency/CVE scanning gate;
- vulnerability-remediation SLA;
- approved retention periods;
- DSAR/export/deletion workflow and SLA;
- centralized production audit/SIEM/log-retention evidence;
- production observability / on-call / alerting evidence.

## 5. Data inventory

Current application model contains the following categories.

### Identity & access
Examples: email, display name, role, password hash, session token hash, expiry/revocation.
Purpose: authentication and authorized account access.
Retention: **to define before production**.

### Participant profile
Examples: intent, interests, visibility/networking choices.
Purpose: participant experience and content/event personalization.
Retention: **to define before production**.

### Event participation
Examples: registration, bookings, waitlist, check-in, attendance, replay.
Purpose: event operation and participant journey.
Retention: **to define before production**.

### Consent-first commercial actions
Examples: product interest, partner lead, follow-up enrollment, appointments.
Purpose: explicit participant-requested continuation.
Retention: **to define before production**.

### Community & communication
Examples: community posts, direct messages, meetings, feedback.
Purpose: community, networking and support.
Retention: **to define before production**.

### Operational evidence
Examples: incidents, venue state, staff assignments, broadcasts, audit events.
Purpose: operation, recovery and evidence.
Retention: **to define before production**.

No production retention period is invented in the MVP.

## 6. Current demo infrastructure observation

Verified through the connected Render account on 2026-10-05:

- public service: `sostoyanie-promomed-live`;
- public region: Frankfurt;
- public plan: free;
- public branch: `main`;
- public auto-deploy: enabled on commit;
- admission service: `sostoyanie-promomed-pg-admission`;
- admission region: Frankfurt;
- admission plan: free;
- admission branch: `main`;
- admission auto-deploy: disabled by design.

These observations describe the current demonstration/release contour. They are **not** a production hosting approval, subprocessor approval, DPA or SLA.

## 7. Framework crosswalk

### NIST Cybersecurity Framework 2.0

Reference:
- https://www.nist.gov/cyberframework
- https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1299.pdf

NIST CSF 2.0 is organized around six Functions:
**Govern, Identify, Protect, Detect, Respond, Recover**.

Current high-level crosswalk:

- **Govern** — owners and decision gates exist; approved policies, supplier governance and risk acceptance remain to prepare.
- **Identify** — data categories, product/runtime state and blockers are inventoried; formal production asset/risk inventory remains to prepare.
- **Protect** — identity, session, role and selected consent controls are CI-proven.
- **Detect** — application events exist; centralized production monitoring/SIEM remains to prepare.
- **Respond** — demo incident mechanics exist; production response runbook remains to prepare.
- **Recover** — PostgreSQL backup/restore equivalence is CI-proven; contractual RTO/RPO remains to prepare.

This is a navigation crosswalk only. It is **not** a NIST assessment or certification.

### OWASP Application Security Verification Standard 5.0.0

Reference:
- https://owasp.org/projects/asvs

The official OWASP ASVS project identifies version 5.0.0 as the current application-security verification standard.

Current application has automated evidence around selected:
- authentication;
- session management;
- authorization;
- command/input boundaries.

No full ASVS assessment has been performed and no ASVS compliance level is claimed.

## 8. Vendor questionnaire — current answer states

### Where is production hosted and which subprocessors handle data?
**TO PREPARE.**
Current demo infrastructure is known; the contracted production hosting/subprocessor authority is not approved.

### How are privileged users authenticated and revoked?
**CI-PROVEN.**
Database-backed accounts, scrypt password hashes, hashed sessions, expiry and revocation are implemented.

### Can the service be restored after database loss?
**CI-PROVEN.**
Isolated PostgreSQL restore and fingerprint equality are proven. Contractual RTO/RPO is not yet approved.

### What is the incident/breach notification process?
**TO PREPARE.**
Production incident and notification runbook remains to be approved.

### How can personal data be exported/deleted?
**TO PREPARE.**
Production DSAR/export/deletion workflow and SLA are not claimed.

### Does the platform automate medical decisions or claims?
**GATED / NO ACTIVE PRODUCTION AUTHORITY.**
PROMO-INT-02 and later evidence/claim authorities remain blocked behind Phase 0.

### Is the platform ISO 27001, SOC 2 or otherwise certified?
**NOT CLAIMED.**

## 9. Procurement gates

1. Product / executive demo — **COMPLETE**
2. Technical diligence — **CI-PROVEN**
3. Production persistence admission — **BLOCKING until Phase 0 COMPLETE**
4. Security & privacy approval — **TO PREPARE**
5. Commercial/legal pilot terms — **TO PREPARE**
6. Medical/editorial governance — **GATED**

## 10. Release-engineering note

The Executive/CVC release demonstrated a real provider handoff risk:
the initial exact-SHA workflow timed out while Render still served the prior commit. The application itself later deployed successfully and the same proof was rerun successfully.

The release gate is therefore hardened to:
- permit manual workflow dispatch;
- allow a longer provider webhook/build handoff window;
- distinguish `DEPLOY_HANDOFF_TIMEOUT` from application readiness failure.

This distinction is important for auditability and incident classification.

## 11. Production approval exit criteria

Before presenting the product as production-ready for a corporate pilot, the package should contain at minimum:

- Phase 0 live PostgreSQL admission;
- production identity authenticated smoke;
- approved production hosting/vendor/subprocessor list;
- approved privacy/data-processing terms;
- retention/export/deletion policy;
- security incident runbook;
- RTO/RPO approval;
- dependency/SBOM scanning evidence;
- production logging/monitoring/on-call evidence;
- agreed pilot support/SLA;
- signed pilot KPI dictionary and decision rights.

Phase 1 remains gated until Phase 0 COMPLETE.
