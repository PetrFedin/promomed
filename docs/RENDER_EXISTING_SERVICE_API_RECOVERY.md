# Existing Promomed Render Services — PATCH recovery candidate

Issue #64. Status: **Draft / NOT APPLIED / official OpenAPI shape checked, live API permissions unverified**.

The existing Render connector exposes read, deploy and environment-variable mutations, but not build-command or health-check mutations. Instead of creating replacement services, this candidate uses the Render API to PATCH only allowlisted existing IDs:

- Admission: `srv-davsqk942hec73e1vcr0` — `serviceDetails.healthCheckPath=/health`.
- Public: `srv-daug7pnlot8c73b1aja0` — `serviceDetails.healthCheckPath=/health`, `serviceDetails.envSpecificDetails.buildCommand=pip install -r requirements.txt && python -m py_compile server.py app/db.py`.

This code refuses non-Free services, different repository/branch/region/ID, unexpected build commands or health paths, and missing live deploy metadata. First run is dry-run. No deploy or database writes occur. It intentionally never touches secret environments, DATABASE_URL or auto-deploy mode.

**Important verification requirement:** Render API request shape must be validated against actual provider response on a dedicated existing service before use on the public service. The nested `serviceDetails` PATCH fields are defined in Render's published OpenAPI, but the current account's authorization and actual server response have not been validated. A CI PASS proves only mocked contract behavior, not real API support. Do not dispatch `apply=true` until this compatibility is confirmed.

Manual GitHub Action: `Promomed existing Render service reconcile`. Optional secret: `PROMOMED_RENDER_CONFIG_API_KEY` (stored in GitHub Actions secrets only, never source). If the secret is unavailable, the job fails closed. No secret provisioning or user authentication was performed by this PR.

Required acceptance sequence:
1. CI at exact branch SHA GREEN.
2. Read-only audit and compatible PATCH schema confirmed on the actual Render API without changing resources.
3. Explicit admission-only apply, verify metadata.
4. Explicit public-only apply, verify metadata; retain Free plan and demo state.
5. Deploy exact accepted main and verify both Render deploy SHAs and HTTP /health.
6. Verify /ready public production_ready=false and browser QA; record proofs.
7. Keep #64 open until live proofs, #65 open until isolated free PostgreSQL source/restore admissions pass.

Zero added costs is a hard gate. No new services and no shared MFW/Antiqua/Marco/FLASHIN data.

## Additional controls (2026-10-12)

The adapter rejects foreign Render `ownerId`, non-allowlisted service URLs, unexpected PATCH fields, and bulk `--apply`. A mutation requires exactly one `--target` and `--confirm PROMOMED_FREE_EXISTING_ONLY`. The workflow passes the same confirmation only on explicit dispatch. None of these controls enables access to a Render API token: `PROMOMED_RENDER_CONFIG_API_KEY` remains an external secret prerequisite. No API request has been issued by this connector as part of this branch.
