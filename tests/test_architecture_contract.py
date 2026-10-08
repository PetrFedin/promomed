import ast
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "server.py"
SERVER = SERVER_PATH.read_text(encoding="utf-8")
APP = ROOT / "app"
LIVE_ADMISSION_WORKFLOW = (ROOT / ".github" / "workflows" / "phase0-live-postgres-proof.yml").read_text(encoding="utf-8")
LIVE_PROOF_WORKFLOW = (ROOT / ".github" / "workflows" / "live-render-proof.yml").read_text(encoding="utf-8")

EXTRACTED = {
    "sval", "setv", "audit", "notify", "promote_waitlist",
    "commercial", "state", "reset_demo", "run_demo_step",
    "token_hash", "issue_session", "auth", "body",
}
MODULES = {
    "auth.py",
    "core.py",
    "analytics.py",
    "investor.py",
    "executive.py",
    "corporate.py",
    "demo.py",
    "programme.py",
    "content.py",
    "community.py",
    "learning.py",
    "partners.py",
    "operations.py",
    "participant.py",
    "commanding.py",
    "community_commands.py",
    "learning_commands.py",
    "participant_commands.py",
    "programme_commands.py",
    "operations_commands.py",
    "partner_commands.py",
    "editorial_commands.py",
    "demo_commands.py",
    "reviewer_authority.py",
    "evidence_interchange.py",
    "institutional_commands.py",
    "syndication_network.py",
    "syndication_commands.py",
    "delivery_protocol.py",
    "trust_bundle.py",
    "trust_commands.py",
    "federated_trust.py",
    "federation_interop.py",
    "pilot_workspace.py",
    "institutional_onboarding.py",
}


class ArchitectureContractTests(unittest.TestCase):
    def test_server_is_composition_layer_for_extracted_contexts(self):
        tree = ast.parse(SERVER)
        top_defs = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
        self.assertTrue(EXTRACTED.isdisjoint(top_defs), top_defs & EXTRACTED)
        self.assertIn("from app.analytics import commercial, state", SERVER)
        self.assertIn("from app.auth import authenticate, auth, body, issue_session, seed_demo_accounts, token_hash", SERVER)
        self.assertIn("from app.core import audit, notify, promote_waitlist, setv, sval", SERVER)
        self.assertIn("from app.demo import DEMO_STEPS, reset_demo, run_demo_step", SERVER)

    def test_bounded_context_modules_exist(self):
        present = {p.name for p in APP.glob("*.py")}
        self.assertTrue(MODULES.issubset(present), MODULES - present)

    def test_analytics_composes_domain_projections(self):
        analytics = (APP / "analytics.py").read_text(encoding="utf-8")
        for module in ("content", "programme", "community", "learning", "partners", "operations", "participant"):
            self.assertIn(f"{module}.snapshot(", analytics)

    def test_all_runtime_modules_compile(self):
        files = [str(SERVER_PATH)] + [str(p) for p in sorted(APP.glob("*.py"))]
        proc = subprocess.run(
            ["python", "-m", "py_compile", *files],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_write_routes_are_outside_http_monolith(self):
        extracted_routes = {
            "/api/follow-expert", "/api/subscribe-topic", "/api/community-post", "/api/learning",
            "/api/register", "/api/booking", "/api/activity-booking", "/api/challenge",
            "/api/replay", "/api/session-attendance", "/api/journey", "/api/direct-message",
            "/api/profile", "/api/meeting", "/api/mutual-meeting", "/api/takeaway",
            "/api/meeting-action", "/api/feedback", "/api/passport", "/api/product-interest",
            "/api/followup-enroll",
            "/api/demo/reset", "/api/demo/next", "/api/move-session", "/api/live", "/api/checkin",
            "/api/appointment-booking", "/api/appointment-manage", "/api/staff-assignment",
            "/api/speaker-readiness", "/api/broadcast", "/api/venue-state", "/api/incident",
            "/api/stream-control", "/api/venue", "/api/placement", "/api/lead", "/api/question",
            "/api/cms", "/api/phase",
        }
        for route in extracted_routes:
            self.assertNotIn(f'p=="{route}"', SERVER)
        self.assertIn("handle_community_command", SERVER)
        self.assertIn("handle_learning_command", SERVER)
        self.assertIn("handle_participant_command", SERVER)
        self.assertIn("handle_programme_command", SERVER)
        self.assertIn("handle_operations_command", SERVER)
        self.assertIn("handle_partner_command", SERVER)
        self.assertIn("handle_editorial_command", SERVER)
        self.assertIn("handle_institutional_command", SERVER)
        self.assertIn("handle_syndication_command", SERVER)
        self.assertIn("handle_demo_command", SERVER)

    def test_http_layer_has_no_hardcoded_account_credentials(self):
        self.assertNotIn("demo2027", SERVER)
        self.assertNotIn("ACCOUNTS={", SERVER)
        self.assertIn("authenticate(c,email,pw)", SERVER)
        auth = (APP / "auth.py").read_text(encoding="utf-8")
        self.assertIn("hashlib.scrypt", auth)
        self.assertIn("SELECT email,password_hash,role,name,status FROM accounts", auth)

    def test_live_admission_workflow_is_fail_closed(self):
        required = (
            'ADMISSION_URL: https://sostoyanie-promomed-pg-admission.onrender.com',
            'health.get("backend")=="postgres"',
            'health.get("durable") is True',
            'health.get("demo_seed") is False',
            'ready.get("schema_ready") is True',
            'ready.get("demo_seed_enabled") is False',
            'ready.get("demo_accounts")==0',
            'ready.get("production_ready") is True',
        )
        for marker in required:
            self.assertIn(marker, LIVE_ADMISSION_WORKFLOW)
        self.assertIn('ready.get("production_ready") is not False', LIVE_PROOF_WORKFLOW)
        self.assertIn('backend=="postgres"', LIVE_PROOF_WORKFLOW)
        self.assertIn("workflow_dispatch:", LIVE_PROOF_WORKFLOW)
        self.assertIn("DEPLOY_HANDOFF_TIMEOUT", LIVE_PROOF_WORKFLOW)
        self.assertIn("range(1, 121)", LIVE_PROOF_WORKFLOW)

    def test_investor_projection_stays_outside_http_layer(self):
        investor = (APP / "investor.py").read_text(encoding="utf-8")
        self.assertIn('def snapshot(c):', investor)
        self.assertIn('investor.snapshot(c)', SERVER)
        self.assertIn('p=="/api/investor-proof"', SERVER)
        self.assertNotIn('"revenue_architecture" =', SERVER)

    def test_executive_projection_stays_outside_http_layer(self):
        executive = (APP / "executive.py").read_text(encoding="utf-8")
        self.assertIn("def snapshot(c):", executive)
        self.assertIn("executive.snapshot(c)", SERVER)
        self.assertIn('p=="/api/executive-room"', SERVER)
        self.assertIn("from app import corporate, db, executive, investor", SERVER)
        self.assertNotIn('"funding_tranches" =', SERVER)

    def test_corporate_projection_stays_outside_http_layer(self):
        corporate = (APP / "corporate.py").read_text(encoding="utf-8")
        self.assertIn("def snapshot(c):", corporate)
        self.assertIn("corporate.snapshot(c)", SERVER)
        self.assertIn('p=="/api/corporate-readiness"', SERVER)
        self.assertNotIn('"procurement_gates" =', SERVER)

    def test_checkpoint_verification_is_public_before_auth(self):
        self.assertIn(
            "from app.evidence_checkpoint_commands import handle_public as handle_evidence_checkpoint_public",
            SERVER,
        )
        public_idx=SERVER.index("public_outcome=handle_evidence_checkpoint_public(p,data)")
        auth_idx=SERVER.index("a=auth(self)", SERVER.index(" def do_POST(self):"))
        self.assertLess(public_idx,auth_idx)

    def test_institutional_portable_verification_is_public_before_auth(self):
        self.assertIn("handle_institutional_public", SERVER)
        public_idx=SERVER.index("institutional_public=handle_institutional_public(p,data)")
        auth_idx=SERVER.index("a=auth(self)", SERVER.index(" def do_POST(self):"))
        self.assertLess(public_idx,auth_idx)

    def test_institutional_openapi_contract_is_machine_readable(self):
        import json
        spec = json.loads((ROOT / "docs" / "openapi" / "institutional-evidence-v1.openapi.json").read_text(encoding="utf-8"))
        self.assertEqual(spec["openapi"], "3.1.0")
        self.assertIn("/api/evidence-interchange/verify-portable", spec["paths"])
        self.assertIn("/api/evidence-interchange/package/deliver", spec["paths"])

    def test_certified_syndication_openapi_and_schemas_are_machine_readable(self):
        import json
        spec=json.loads((ROOT/"docs"/"openapi"/"certified-syndication-v1.openapi.json").read_text(encoding="utf-8"))
        certification=json.loads((ROOT/"docs"/"schemas"/"syndication-certification-v1.schema.json").read_text(encoding="utf-8"))
        receipt=json.loads((ROOT/"docs"/"schemas"/"external-contribution-admission-receipt-v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(spec["openapi"],"3.1.0")
        self.assertIn("/api/syndication/qualification/finalize",spec["paths"])
        self.assertIn("/api/external-contribution/revise",spec["paths"])
        self.assertIn("/api/external-contribution/receipt/verify-portable",spec["paths"])
        self.assertEqual(certification["$id"],"urn:promomed:schema:syndication-certification:v1")
        self.assertEqual(receipt["$id"],"urn:promomed:schema:external-contribution-admission-receipt:v1")

    def test_contribution_receipt_verification_is_public_before_auth(self):
        self.assertIn("handle_syndication_public", SERVER)
        public_idx=SERVER.index("syndication_public=handle_syndication_public(p,data)")
        auth_idx=SERVER.index("a=auth(self)", SERVER.index(" def do_POST(self):"))
        self.assertLess(public_idx,auth_idx)

    def test_partner_delivery_openapi_and_schemas_are_machine_readable(self):
        import json
        spec=json.loads((ROOT/"docs"/"openapi"/"partner-delivery-v2.openapi.json").read_text(encoding="utf-8"))
        event=json.loads((ROOT/"docs"/"schemas"/"partner-delivery-event-v2.schema.json").read_text(encoding="utf-8"))
        ack=json.loads((ROOT/"docs"/"schemas"/"partner-delivery-ack-v2.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(spec["openapi"],"3.1.0")
        self.assertIn("/api/syndication/delivery/acknowledge",spec["paths"])
        self.assertIn("/api/syndication/endpoint/verify",spec["paths"])
        self.assertEqual(event["$id"],"urn:promomed:schema:partner-delivery-event:v2")
        self.assertEqual(ack["$id"],"urn:promomed:schema:partner-delivery-ack:v2")

    def test_partner_delivery_ack_is_public_before_auth(self):
        self.assertIn("handle_syndication_public", SERVER)
        public_idx=SERVER.index("syndication_public=handle_syndication_public(p,data)")
        auth_idx=SERVER.index("a=auth(self)", SERVER.index(" def do_POST(self):"))
        self.assertLess(public_idx,auth_idx)
        commands=(APP/"syndication_commands.py").read_text(encoding="utf-8")
        self.assertIn('/api/syndication/delivery/acknowledge',commands)
        self.assertIn("delivery_protocol.acknowledge_event",commands)

    def test_partner_delivery_runtime_uses_postgres_portable_dml(self):
        runtime=(APP/"delivery_protocol.py").read_text(encoding="utf-8")
        self.assertNotIn("INSERT OR IGNORE",runtime)
        self.assertNotIn("REPLACE INTO",runtime)
        self.assertIn("ON CONFLICT(id) DO NOTHING",runtime)

    def test_delivery_migration_observation_contract_matches_runtime(self):
        sqlite=(ROOT/"migrations"/"sqlite"/"022_partner_delivery_protocol.sql").read_text(encoding="utf-8")
        postgres=(ROOT/"migrations"/"postgres"/"022_partner_delivery_protocol.sql").read_text(encoding="utf-8")
        for migration in (sqlite,postgres):
            self.assertIn("'ack_missing'",migration)
            self.assertIn("syndication_delivery_observations",migration)
            self.assertIn("syndication_delivery_observations_no_update",migration)
        self.assertIn("immutable_syndication_delivery_observation",sqlite)
        self.assertIn("promomed_block_syndication_delivery_audit_mutation",postgres)
        self.assertIn(
            "FOR EACH ROW EXECUTE FUNCTION promomed_block_syndication_delivery_audit_mutation()",
            postgres,
        )

    def test_partner_trust_verification_is_public_before_auth(self):
        self.assertIn("handle_trust_public",SERVER)
        public_idx=SERVER.index("trust_public=handle_trust_public(p,data)")
        auth_idx=SERVER.index("a=auth(self)",SERVER.index(" def do_POST(self):"))
        self.assertLess(public_idx,auth_idx)

    def test_partner_trust_openapi_and_schemas_are_machine_readable(self):
        import json
        spec=json.loads((ROOT/"docs"/"openapi"/"partner-trust-v1.openapi.json").read_text(encoding="utf-8"))
        snapshot=json.loads((ROOT/"docs"/"schemas"/"institutional-status-snapshot-v1.schema.json").read_text(encoding="utf-8"))
        bundle=json.loads((ROOT/"docs"/"schemas"/"partner-trust-bundle-v1.schema.json").read_text(encoding="utf-8"))
        receipt=json.loads((ROOT/"docs"/"schemas"/"trust-verification-receipt-v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(spec["openapi"],"3.1.0")
        self.assertIn("/api/trust/verify-portable",spec["paths"])
        self.assertIn("/api/trust/verification/record",spec["paths"])
        self.assertEqual(snapshot["$id"],"urn:promomed:schema:institutional-status-snapshot:v1")
        self.assertEqual(bundle["$id"],"urn:promomed:schema:partner-trust-bundle:v1")
        self.assertEqual(receipt["$id"],"urn:promomed:schema:trust-verification-receipt:v1")

    def test_federated_trust_public_verifier_and_dynamic_reads_are_reachable(self):
        commands=(APP/"trust_commands.py").read_text(encoding="utf-8")
        media=(APP/"media_reads.py").read_text(encoding="utf-8")
        self.assertIn('/api/federation/receipt/verify-portable',commands)
        self.assertIn('parsed.path.startswith("/trust/")',media)
        self.assertIn('parsed.path.endswith("/did.json")',media)
        self.assertIn('parsed.path.endswith("/jwks.json")',media)
        self.assertIn("dynamic_federated_public",media)

    def test_federated_trust_openapi_and_schemas_are_machine_readable(self):
        import json
        spec=json.loads((ROOT/"docs"/"openapi"/"federated-trust-v1.openapi.json").read_text(encoding="utf-8"))
        anchor=json.loads((ROOT/"docs"/"schemas"/"federated-trust-anchor-v1.schema.json").read_text(encoding="utf-8"))
        receipt=json.loads((ROOT/"docs"/"schemas"/"institution-signed-verification-receipt-v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(spec["openapi"],"3.1.0")
        self.assertIn("/trust/{organization_id}/did.json",spec["paths"])
        self.assertIn("/trust/{organization_id}/jwks.json",spec["paths"])
        self.assertIn("/api/federation/receipt/verify-portable",spec["paths"])
        self.assertEqual(anchor["$id"],"urn:promomed:schema:federated-trust-anchor:v1")
        self.assertEqual(receipt["$id"],"urn:promomed:schema:institution-signed-verification-receipt:v1")

    def test_federated_trust_runtime_uses_postgres_portable_dml(self):
        runtime=(APP/"federated_trust.py").read_text(encoding="utf-8")
        self.assertNotIn("INSERT OR IGNORE",runtime)
        self.assertNotIn("REPLACE INTO",runtime)
        self.assertIn("ON CONFLICT(event_sha256) DO NOTHING",runtime)

    def test_federated_trust_migration_contract_matches_runtime(self):
        sqlite=(ROOT/"migrations"/"sqlite"/"024_federated_trust_anchors.sql").read_text(encoding="utf-8")
        postgres=(ROOT/"migrations"/"postgres"/"024_federated_trust_anchors.sql").read_text(encoding="utf-8")
        for migration in (sqlite,postgres):
            for state in ("pending_proof","pending_governance","active","retired","suspended","revoked"):
                self.assertIn("'"+state+"'",migration)
            self.assertIn("institutional_signed_verification_receipts",migration)
            self.assertIn("institutional_federated_anchor_events",migration)
        self.assertIn("immutable_institutional_federated_anchor",sqlite)
        self.assertIn("promomed_block_federated_trust_audit_mutation",postgres)

    def test_federation_interop_public_discovery_is_reachable(self):
        media=(APP/"media_reads.py").read_text(encoding="utf-8")
        commands=(APP/"trust_commands.py").read_text(encoding="utf-8")
        for route in (
            "/.well-known/promomed-federation.json",
            "/api/federation/profile",
            "/api/federation/discovery",
            "/api/federation/discovery-bundle",
        ):
            self.assertIn(route,media)
        self.assertIn("/api/federation/discovery-bundle/verify-portable",commands)

    def test_institutional_onboarding_room_is_guarded_and_read_only(self):
        media=(APP/"media_reads.py").read_text(encoding="utf-8")
        runtime=(APP/"institutional_onboarding.py").read_text(encoding="utf-8")
        self.assertIn("/api/institutional-onboarding-room",media)
        self.assertIn("institutional_onboarding.snapshot",media)
        self.assertIn('"readOnlyOrchestration":True',runtime)
        self.assertIn('"externalParticipationAcceptance":"GATED"',runtime)
        self.assertNotIn("INSERT ",runtime)
        self.assertNotIn("UPDATE ",runtime)
        self.assertNotIn("DELETE ",runtime)

    def test_institutional_pilot_readiness_workspace_is_guarded_and_read_only(self):
        media=(APP/"media_reads.py").read_text(encoding="utf-8")
        runtime=(APP/"pilot_workspace.py").read_text(encoding="utf-8")
        self.assertIn("/api/institutional-pilot-readiness",media)
        self.assertIn("pilot_workspace.snapshot",media)
        self.assertIn('role not in ("governance","editor","sales")',media)
        self.assertIn('"readOnlyProjection": True',runtime)
        self.assertIn('"externalAdoptionInferred": False',runtime)
        self.assertNotIn("INSERT ",runtime)
        self.assertNotIn("UPDATE ",runtime)
        self.assertNotIn("DELETE ",runtime)

    def test_federation_interop_runtime_uses_postgres_portable_dml(self):
        runtime=(APP/"federation_interop.py").read_text(encoding="utf-8")
        self.assertNotIn("INSERT OR IGNORE",runtime)
        self.assertNotIn("REPLACE INTO",runtime)

    def test_federation_interop_migration_contract_matches_runtime(self):
        sqlite=(ROOT/"migrations"/"sqlite"/"025_federation_interoperability.sql").read_text(encoding="utf-8")
        postgres=(ROOT/"migrations"/"postgres"/"025_federation_interoperability.sql").read_text(encoding="utf-8")
        for migration in (sqlite,postgres):
            for status in ("compatible","compatible_with_warnings","incompatible","no_active_anchor"):
                self.assertIn("'"+status+"'",migration)
            self.assertIn("federation_interoperability_profiles",migration)
            self.assertIn("federation_profile_evaluations",migration)
            self.assertIn("federation_discovery_bundles",migration)
        self.assertIn("immutable_federation_interoperability_profile",sqlite)
        self.assertIn("promomed_block_federation_interop_audit_mutation",postgres)

    def test_federation_interop_openapi_and_schemas_are_machine_readable(self):
        import json
        spec=json.loads((ROOT/"docs"/"openapi"/"federation-interoperability-v1.openapi.json").read_text(encoding="utf-8"))
        profile=json.loads((ROOT/"docs"/"schemas"/"federation-interoperability-profile-v1.schema.json").read_text(encoding="utf-8"))
        bundle=json.loads((ROOT/"docs"/"schemas"/"federation-discovery-bundle-v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(spec["openapi"],"3.1.0")
        self.assertIn("/.well-known/promomed-federation.json",spec["paths"])
        self.assertIn("/api/federation/discovery",spec["paths"])
        self.assertIn("/api/federation/discovery-bundle/verify-portable",spec["paths"])
        self.assertEqual(profile["$id"],"urn:promomed:schema:federation-interoperability-profile:v1")
        self.assertEqual(bundle["$id"],"urn:promomed:schema:federation-discovery-bundle:v1")

    def test_server_size_moves_down_not_up(self):
        self.assertLessEqual(len(SERVER.splitlines()), 405)


if __name__ == "__main__":
    unittest.main()
