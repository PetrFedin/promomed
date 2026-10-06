import os
import tempfile
import unittest
from pathlib import Path


class CapitalPlanExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "capital-execution.db")
        os.environ["PROMOMED_SEED_DEMO"] = "true"
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("PROMOMED_REQUIRE_POSTGRES", None)

        import importlib
        import app.db as db
        import app.capital_execution as capital_execution
        import server

        importlib.reload(db)
        importlib.reload(capital_execution)
        importlib.reload(server)
        self.execution = capital_execution
        self.server = server
        self.server.init()
        self.c = self.server.conn()

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def test_seeded_execution_reconciles_plan_commit_actual(self):
        d = self.execution.snapshot(self.c)
        t = d["totals"]
        self.assertEqual(t["planned_rub"], 10_000_000)
        self.assertEqual(t["committed_rub"], 5_500_000)
        self.assertEqual(t["actual_rub"], 3_270_000)
        self.assertEqual(t["uncommitted_rub"], 4_500_000)
        self.assertEqual(t["committed_unspent_rub"], 2_230_000)
        self.assertEqual(t["unlocked_value_rub"], 0)
        self.assertEqual(t["evidence_accepted_count"], 1)
        self.assertEqual(t["package_count"], 4)

    def test_spend_does_not_unlock_value_without_evidence_gate(self):
        self.execution.update_demo(
            self.c,
            "s2",
            "sales@demo.ru",
            status="in_progress",
            committed_rub=3_000_000,
            actual_rub=2_900_000,
            evidence_status="partial",
            evidence_ref="demo://partial",
        )
        self.c.commit()
        d = self.execution.snapshot(self.c)
        s2 = {x["package_id"]: x for x in d["packages"]}["s2"]
        self.assertEqual(s2["actual_rub"], 2_900_000)
        self.assertFalse(s2["evidence_accepted"])
        self.assertEqual(s2["unlocked_value_rub"], 0)

    def test_actual_cannot_exceed_commitment(self):
        with self.assertRaisesRegex(ValueError, "actual_exceeds_committed"):
            self.execution.update_demo(
                self.c,
                "s2",
                "sales@demo.ru",
                committed_rub=2_000_000,
                actual_rub=2_500_000,
            )

    def test_commitment_cannot_exceed_plan(self):
        with self.assertRaisesRegex(ValueError, "committed_exceeds_plan"):
            self.execution.update_demo(
                self.c,
                "s1",
                "sales@demo.ru",
                committed_rub=2_000_000,
            )

    def test_s4_cannot_unlock_before_prerequisites(self):
        with self.assertRaisesRegex(ValueError, "security_prerequisites_not_accepted"):
            self.execution.update_demo(
                self.c,
                "s4",
                "sales@demo.ru",
                status="accepted_demo",
                committed_rub=3_000_000,
                actual_rub=2_500_000,
                evidence_status="accepted_demo",
                evidence_ref="demo://security-final",
            )

    def test_reset_restores_seeded_execution(self):
        self.execution.update_demo(
            self.c,
            "s2",
            "sales@demo.ru",
            status="accepted_demo",
            committed_rub=3_000_000,
            actual_rub=2_850_000,
            evidence_status="accepted_demo",
            evidence_ref="demo://restore-proof",
        )
        self.c.commit()
        self.execution.reset_demo(self.c, "sales@demo.ru")
        self.c.commit()
        d = self.execution.snapshot(self.c)
        s2 = {x["package_id"]: x for x in d["packages"]}["s2"]
        self.assertEqual(s2["status"], "in_progress")
        self.assertEqual(s2["actual_rub"], 1_850_000)
        self.assertEqual(s2["evidence_status"], "partial")

    def test_truth_boundary_is_fail_closed(self):
        d = self.execution.snapshot(self.c)
        self.assertTrue(d["truth_boundary"]["demo_execution"])
        self.assertFalse(d["truth_boundary"]["actual_erp_spend"])
        self.assertFalse(d["truth_boundary"]["actual_purchase_orders"])
        self.assertFalse(d["truth_boundary"]["actual_payment_authority"])


if __name__ == "__main__":
    unittest.main()
