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

    def test_server_size_moves_down_not_up(self):
        self.assertLessEqual(len(SERVER.splitlines()), 400)


if __name__ == "__main__":
    unittest.main()
