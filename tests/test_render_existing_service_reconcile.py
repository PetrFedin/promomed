import importlib.util
import unittest
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "ops"
import sys
sys.path.insert(0, str(P))
import render_existing_service_reconcile as m


def fixture(role):
    id_, name, deploy = m.SERVICES[role]
    return {"id": id_, "name": name, "repo": "https://github.com/PetrFedin/promomed",
            "type": "web_service", "branch": "main", "autoDeployTrigger": deploy,
            "serviceDetails": {"plan": "free", "region": "frankfurt",
                               "healthCheckPath": "",
                               "envSpecificDetails": {
                                   "buildCommand": m.LEGACY_PUBLIC_BUILD if role == "public" else m.BUILD,
                                   "startCommand": "python server.py"}}}


class ReconcileTest(unittest.TestCase):
    def test_exact_allowlist(self):
        public = m.plan_change("public", fixture("public"))
        self.assertEqual(public, {"serviceDetails": {"healthCheckPath": "/health",
                         "envSpecificDetails": {"buildCommand": m.BUILD}}})
        self.assertEqual(m.plan_change("admission", fixture("admission")),
                         {"serviceDetails": {"healthCheckPath": "/health"}})

    def test_noop(self):
        x = fixture("public")
        x["serviceDetails"]["healthCheckPath"] = "/health"
        x["serviceDetails"]["envSpecificDetails"]["buildCommand"] = m.BUILD
        self.assertEqual(m.plan_change("public", x), {})

    def test_reject_other_project_or_paid(self):
        for role in m.SERVICES:
            x = fixture(role)
            x["serviceDetails"]["plan"] = "starter"
            with self.assertRaises(m.ReconcileError):
                m.plan_change(role, x)
            x = fixture(role)
            x["repo"] = "https://github.com/PetrFedin/mfw"
            with self.assertRaises(m.ReconcileError):
                m.plan_change(role, x)

    def test_reject_unexpected_commands(self):
        x = fixture("public")
        x["serviceDetails"]["envSpecificDetails"]["buildCommand"] = "echo other"
        with self.assertRaisesRegex(m.ReconcileError, "UNEXPECTED_PUBLIC_BUILD"):
            m.plan_change("public", x)

    def test_dry_run_never_patches(self):
        called = []
        def fake(method, path, token, body=None):
            called.append(method)
            if "deploys" in path:
                return [{"deploy": {"status": "live", "commit": {"id": "abc"}}}]
            return fixture("admission")
        result = m.reconcile("admission", "token", api=fake)
        self.assertEqual(result["status"], "DRIFT_DRY_RUN")
        self.assertEqual(called, ["GET", "GET"])

    def test_apply_checks_live_metadata(self):
        state = fixture("admission")
        methods = []
        def fake(method, path, token, body=None):
            methods.append(method)
            if "deploys" in path:
                return [{"deploy": {"status": "live", "commit": {"id": "abc"}}}]
            if method == "PATCH":
                state["serviceDetails"]["healthCheckPath"] = body["serviceDetails"]["healthCheckPath"]
                return {}
            return state
        result = m.reconcile("admission", "token", apply=True, api=fake)
        self.assertEqual(result["status"], "CONFIG_PATCH_VERIFIED_NOT_DEPLOYED")
        self.assertEqual(methods, ["GET", "GET", "PATCH", "GET"])

    def test_missing_token_fail_closed(self):
        from unittest.mock import patch
        with patch.dict("os.environ", {"RENDER_API_KEY": ""}):
            self.assertEqual(m.main(["--apply"]), 2)


if __name__ == "__main__":
    unittest.main()
