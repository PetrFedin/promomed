import importlib.util
import unittest
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "ops/render_configuration_audit.py"
s = importlib.util.spec_from_file_location("render_audit", P)
a = importlib.util.module_from_spec(s)
s.loader.exec_module(a)


def service(role):
    sid, name, mode = a.SERVICES[role]
    return {"id": sid, "name": name, "repo": a.REPO, "branch": "main",
            "type": "web_service", "autoDeployTrigger": mode,
            "serviceDetails": {"plan": "free", "region": "frankfurt", "healthCheckPath": "/health",
                               "envSpecificDetails": {"buildCommand": a.BUILD, "startCommand": a.START}}}


class RenderAuditTest(unittest.TestCase):
    def test_both_configurations_pass(self):
        for role in a.SERVICES:
            self.assertEqual(a.check(service(role), role), [])

    def test_real_public_drift_detected(self):
        x = service("public")
        x["serviceDetails"]["healthCheckPath"] = ""
        x["serviceDetails"]["envSpecificDetails"]["buildCommand"] = "python -m py_compile server.py"
        self.assertEqual(a.check(x, "public"), ["BUILD", "HEALTH"])

    def test_real_admission_drift_detected(self):
        x = service("admission")
        x["serviceDetails"]["healthCheckPath"] = ""
        self.assertEqual(a.check(x, "admission"), ["HEALTH"])

    def test_cross_project_and_paid_configuration_rejected(self):
        x = service("public")
        x["repo"] = "https://github.com/PetrFedin/mfw"
        x["serviceDetails"]["plan"] = "starter"
        self.assertIn("REPOSITORY", a.check(x, "public"))
        self.assertIn("FREE_PLAN", a.check(x, "public"))

    def test_deployment_sha_and_status_fail_closed(self):
        x = [{"deploy": {"status": "live", "commit": {"id": "abc"}}}]
        self.assertEqual(a.check_deploy(x, "abc"), [])
        self.assertEqual(a.check_deploy(x, "def"), ["DEPLOY_SHA_MISMATCH"])
        self.assertEqual(a.check_deploy([], "abc"), ["MISSING_DEPLOY"])

    def test_secret_fields_not_inspected(self):
        x = service("public")
        x["envVars"] = [{"key": "DATABASE_URL", "value": "secret"}]
        self.assertEqual(a.check(x, "public"), [])


if __name__ == "__main__":
    unittest.main()
