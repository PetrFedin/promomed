import os
import tempfile
import unittest
from pathlib import Path


class PilotGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "pilot-governance.db")
        os.environ["PROMOMED_SEED_DEMO"] = "true"
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("PROMOMED_REQUIRE_POSTGRES", None)

        import importlib
        import app.db as db
        import app.pilot_governance as pilot_governance
        import app.pilot_commands as pilot_commands
        import server

        importlib.reload(db)
        importlib.reload(pilot_governance)
        importlib.reload(pilot_commands)
        importlib.reload(server)
        self.pilot = pilot_governance
        self.commands = pilot_commands
        self.server = server
        self.server.init()
        self.c = self.server.conn()

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def _set_all_targets(self):
        for kpi in self.pilot.snapshot(self.c)["kpis"]:
            out = self.commands.handle_command(
                self.c,
                "/api/pilot/kpi-target",
                "sales",
                "sales@demo.ru",
                {"kpi_id": kpi["id"], "target": "USER-APPROVED TARGET " + kpi["id"]},
            )
            self.assertEqual(out.status, 200)

    def _sign_and_lock(self):
        for role in ("sales", "organizer"):
            out = self.commands.handle_command(
                self.c,
                "/api/pilot/signoff",
                role,
                role + "@demo.ru",
                {},
            )
            self.assertEqual(out.status, 200)
        out = self.commands.handle_command(
            self.c,
            "/api/pilot/lock-baseline",
            "sales",
            "sales@demo.ru",
            {},
        )
        self.assertEqual(out.status, 200)
        return out.payload

    def test_initial_charter_is_draft_and_targets_are_not_invented(self):
        proof = self.pilot.snapshot(self.c)
        self.assertEqual(proof["charter"]["status"], "draft")
        self.assertTrue(proof["kpis"])
        self.assertTrue(all(x["target"] == "TO_AGREE" for x in proof["kpis"]))
        self.assertFalse(proof["gates"]["targets_ready"])
        self.assertFalse(proof["gates"]["signoffs_ready"])
        self.assertFalse(proof["gates"]["baseline_locked"])
        self.assertFalse(proof["gates"]["go_allowed"])

    def test_baseline_cannot_lock_before_targets_and_signoffs(self):
        out = self.commands.handle_command(
            self.c, "/api/pilot/lock-baseline", "sales", "sales@demo.ru", {}
        )
        self.assertEqual(out.status, 409)
        self.assertEqual(out.payload["error"], "kpi_targets_incomplete")

        self._set_all_targets()
        out = self.commands.handle_command(
            self.c, "/api/pilot/lock-baseline", "sales", "sales@demo.ru", {}
        )
        self.assertEqual(out.status, 409)
        self.assertEqual(out.payload["error"], "required_signoffs_incomplete")

    def test_two_role_signoff_locks_baseline_and_prevents_rewrite(self):
        self._set_all_targets()
        proof = self._sign_and_lock()
        self.assertTrue(proof["gates"]["baseline_locked"])
        self.assertEqual(proof["charter"]["status"], "approved")
        self.assertTrue(all(x["status"] == "approved" for x in proof["kpis"]))

        out = self.commands.handle_command(
            self.c,
            "/api/pilot/kpi-target",
            "sales",
            "sales@demo.ru",
            {"kpi_id": "KPI01", "target": "CHANGED AFTER RESULT"},
        )
        self.assertEqual(out.status, 409)
        self.assertEqual(out.payload["error"], "baseline_locked")

    def test_post_lock_change_uses_change_request_not_direct_mutation(self):
        self._set_all_targets()
        self._sign_and_lock()
        old = self.c.execute("SELECT target FROM pilot_kpis WHERE id='KPI01'").fetchone()["target"]
        out = self.commands.handle_command(
            self.c,
            "/api/pilot/change-request",
            "organizer",
            "organizer@demo.ru",
            {
                "item_type": "kpi",
                "item_id": "KPI01",
                "field_name": "target",
                "new_value": "PROPOSED NEW TARGET",
                "rationale": "Material scope change requested by pilot committee.",
            },
        )
        self.assertEqual(out.status, 200)
        current = self.c.execute("SELECT target FROM pilot_kpis WHERE id='KPI01'").fetchone()["target"]
        self.assertEqual(current, old)
        self.assertEqual(out.payload["changes"][0]["status"], "proposed")

    def test_go_remains_fail_closed_in_demo_even_with_complete_evidence(self):
        self._set_all_targets()
        self._sign_and_lock()

        for kpi in self.pilot.snapshot(self.c)["kpis"]:
            out = self.commands.handle_command(
                self.c,
                "/api/pilot/kpi-actual",
                "sales",
                "sales@demo.ru",
                {
                    "kpi_id": kpi["id"],
                    "actual_value": "DEMO ACTUAL " + kpi["id"],
                    "actual_source": "demo evidence fixture",
                },
            )
            self.assertEqual(out.status, 200)

        for item in self.pilot.snapshot(self.c)["deliverables"]:
            owner = item["owner_role"]
            owner_email = "partner@demo.ru" if owner == "partner" else owner + "@demo.ru"
            out = self.commands.handle_command(
                self.c,
                "/api/pilot/deliverable-evidence",
                owner,
                owner_email,
                {"deliverable_id": item["id"], "evidence": "DEMO EVIDENCE " + item["id"]},
            )
            self.assertEqual(out.status, 200)
            acceptor = item["acceptor_role"]
            out = self.commands.handle_command(
                self.c,
                "/api/pilot/deliverable-accept",
                acceptor,
                acceptor + "@demo.ru",
                {"deliverable_id": item["id"]},
            )
            self.assertEqual(out.status, 200)

        proof = self.pilot.snapshot(self.c)
        self.assertTrue(proof["gates"]["actuals_complete"])
        self.assertTrue(proof["gates"]["deliverables_accepted"])
        self.assertFalse(proof["gates"]["production_ready"])
        self.assertFalse(proof["gates"]["go_allowed"])

        out = self.commands.handle_command(
            self.c,
            "/api/pilot/decision",
            "sales",
            "sales@demo.ru",
            {"decision": "GO", "rationale": "Attempted demo GO."},
        )
        self.assertEqual(out.status, 409)
        self.assertEqual(out.payload["error"], "go_gate_not_satisfied")
        self.assertIn("production_ready", out.payload["blockers"])

    def test_iterate_or_stop_requires_locked_baseline_and_rationale(self):
        out = self.commands.handle_command(
            self.c,
            "/api/pilot/decision",
            "sales",
            "sales@demo.ru",
            {"decision": "ITERATE", "rationale": "Scope needs revision."},
        )
        self.assertEqual(out.status, 409)
        self.assertEqual(out.payload["error"], "baseline_not_locked")

        self._set_all_targets()
        self._sign_and_lock()
        out = self.commands.handle_command(
            self.c,
            "/api/pilot/decision",
            "sales",
            "sales@demo.ru",
            {"decision": "ITERATE", "rationale": "Scope needs revision."},
        )
        self.assertEqual(out.status, 200)
        self.assertEqual(out.payload["decisions"][0]["decision"], "ITERATE")

    def test_demo_reset_restores_clean_draft_and_is_role_gated(self):
        self._set_all_targets()
        denied = self.commands.handle_command(
            self.c, "/api/pilot/reset-demo", "organizer", "organizer@demo.ru", {}
        )
        self.assertEqual(denied.status, 403)
        out = self.commands.handle_command(
            self.c, "/api/pilot/reset-demo", "sales", "sales@demo.ru", {}
        )
        self.assertEqual(out.status, 200)
        self.assertEqual(out.payload["charter"]["status"], "draft")
        self.assertTrue(all(x["target"] == "TO_AGREE" for x in out.payload["kpis"]))
        self.assertTrue(all(x["status"] == "pending" for x in out.payload["signoffs"]))
        self.assertEqual(out.payload["changes"], [])
        self.assertEqual(out.payload["decisions"], [])

    def test_partner_cannot_set_kpi_target_or_sign_baseline(self):
        target = self.commands.handle_command(
            self.c,
            "/api/pilot/kpi-target",
            "partner",
            "partner@demo.ru",
            {"kpi_id": "KPI01", "target": "SHOULD NOT WRITE"},
        )
        self.assertEqual(target.status, 403)
        signoff = self.commands.handle_command(
            self.c,
            "/api/pilot/signoff",
            "partner",
            "partner@demo.ru",
            {},
        )
        self.assertEqual(signoff.status, 403)


if __name__ == "__main__":
    unittest.main()
