import os
import tempfile
import unittest
from pathlib import Path


class RecoveryReforecastTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "reforecast.db")
        os.environ["PROMOMED_SEED_DEMO"] = "true"
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("PROMOMED_REQUIRE_POSTGRES", None)

        import importlib
        import app.db as db
        import app.recovery_reforecast as recovery_reforecast
        import server

        importlib.reload(db)
        importlib.reload(recovery_reforecast)
        importlib.reload(server)
        self.reforecast = recovery_reforecast
        self.server = server
        self.server.init()
        self.c = self.server.conn()

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def test_recovery_is_primary_and_uses_existing_commitment(self):
        d = self.reforecast.snapshot(self.c)
        self.assertEqual(d["recommendation"]["primary"], "A_RECOVER_S2")
        a = {x["id"]: x for x in d["scenarios"]}["A_RECOVER_S2"]
        self.assertEqual(a["new_commitment_rub"], 0)
        self.assertGreater(a["additional_actual_spend_rub"], 0)
        self.assertEqual(a["decision"], "RECOVER_FIRST")
        self.assertEqual(a["next_unlock_rub"], 10_000_000)

    def test_reallocation_uses_only_uncommitted_capacity(self):
        d = self.reforecast.snapshot(self.c)
        b = {x["id"]: x for x in d["scenarios"]}["B_REALLOCATE_AFTER_S2_FAILURE"]
        self.assertEqual(b["reallocation_candidate_rub"], 4_500_000)
        self.assertEqual(sum(x["amount_rub"] for x in b["reallocation_proposal"]), 4_500_000)
        self.assertIn("committed-but-unspent S2 capital remains ring-fenced", b["reason"])

    def test_payback_is_not_invented(self):
        d = self.reforecast.snapshot(self.c)
        for row in d["scenarios"]:
            self.assertEqual(row["expected_payback_status"], "NOT_CALCULATED_UNTIL_FINANCE_ACCEPTS_VALUE")
        self.assertFalse(d["truth_boundary"]["expected_payback_validated"])
        self.assertFalse(d["truth_boundary"]["actual_forecast"])

    def test_approval_simulation_is_fail_closed(self):
        d = self.reforecast.snapshot(self.c)
        self.assertFalse(d["approval_simulation"]["automatic_actions"])
        self.assertIn("Finance confirmation of uncommitted capacity", d["approval_simulation"]["reallocation_requires"])
        self.assertFalse(d["truth_boundary"]["approved_reallocation"])
        self.assertFalse(d["truth_boundary"]["automatic_money_movement"])


if __name__ == "__main__":
    unittest.main()
