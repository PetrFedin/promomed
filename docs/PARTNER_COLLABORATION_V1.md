# Partner Collaboration Workspace v1 — operational MVP

**Branch-only, not accepted or live.** P1 development candidate independent from public stakeholder experience PR #69.

## Implemented scope
- Partner account creates internal planning project in one of five nonclinical formats: event, studio, content, learning, experience.
- Identified owner can create tasks; organizer views all projects and can request changes or mark a project internally reviewed.
- Role-bound read API `GET /api/partner-collaboration[?project_id=]` and POST routes `/api/partner-collaboration/{create,project,task}`.
- Entity version used for status transitions, tenant object-scoped authorization and idempotency ledger for each command.
- Immutable action log without sensitive body details. No contracts, payments, pricing, marketing permissions, external business acceptance, customer database access, or real buyer intent.
- Isolated mirrored SQLite and PostgreSQL migration 026. Existing migrations remain immutable.
- User-facing screen `/partner-collaboration.html`, accessible from Institutional Commercial Workspace.

## Security boundaries
- Only authenticated `partner` / `organizer` roles access routes. No participant, sales, reviewer or governance shortcut.
- Partner project is owned by authenticated account e-mail; foreign ID returns 404 without metadata. Organizer is project review authority ONLY, never legal/billing/external acceptance.
- Internal project uses explicit `demo_only=1`; NOT a real institution or contract. Free SQLite is ephemeral in Render, not durable production.
- No free-form file uploads/PII, no external communication/notifications, no automatic GDPR consent assumptions.
- Replay with same actor and operation id returns canonical response; altered replay 409; optimistic version mismatch 409.
- Separate provider-funded, independently tested PostgreSQL admission remains P0 required before any operational pilot.

## Acceptance gates
1. `test_partner_collaboration.py`: owner isolation, negative roles, allowed transitions, version conflicts, immutability, idempotency.
2. GitHub Actions UI, SQLite and PostgreSQL migration/contract checks all GREEN on exact SHA; browser smoke on phone/tablet/desktop required before merging.
3. Security review: ensure script cannot leak credentials, cannot grant partner data access, cannot mutate cross-tenant records.
4. Live Render config and PostgreSQL admission remain BLOCKED independently of this PR.
5. Expenses: no new paid resources created, but existing GitHub Actions free quota and production hosting limits are not independently cost audited.

## Next release after safe P0
- Task statuses + due dates + assignments with verified partner organization membership rather than just account-level tenancy.
- Consent-bound customer touchpoints and only then cohort measurement D7/D30.
- Investor Value Control Tower consumes independently accepted activities and delivery evidence, never demo task counts as traction.
