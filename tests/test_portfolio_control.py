import os
import tempfile
import unittest
from pathlib import Path


class PortfolioCapitalControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "portfolio-control.db")
        os.environ["PROMOMED_SEED_DEMO"] = "true"
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("PROMOMED_REQUIRE_POSTGRES", None)

        import importlib
        import app.db as db
        import app.deal_room as deal_room
        import app.portfolio_control as portfolio_control
        import server

        importlib.reload(db)
        importlib.reload(deal_room)
        importlib.reload(portfolio_control)
        importlib.reload(server)
        self.deal_room = deal_room
        self.portfolio_control = portfolio_control
        self.server = server
        self.server.init()
        self.c = self.server.conn()

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def test_initial_75m_portfolio_reconciles_exactly(self):
        d = self.portfolio_control.snapshot(self.c)
        t = d["totals"]
        self.assertEqual(t["committed"], 75_000_000)
        self.assertEqual(t["paid"], 10_000_000)
        self.assertEqual(t["eligible"], 20_000_000)
        self.assertEqual(t["blocked"], 32_500_000)
        self.assertEqual(t["at_risk"], 12_500_000)
        self.assertEqual(
            t["paid"] + t["eligible"] + t["blocked"] + t["at_risk"],
            t["committed"],
        )

    def test_programme_is_iterate_with_three_overdue_obligations(self):
        d = self.portfolio_control.snapshot(self.c)
        self.assertEqual(d["programme"]["decision"], "ITERATE")
        self.assertEqual(d["totals"]["overdue_obligations"], 3)
        self.assertGreaterEqual(d["totals"]["blocked_share_pct"], 40.0)
        self.assertFalse(d["truth_boundary"]["actual_payment_authority"])

    def test_next_expected_release_is_security_gate(self):
        d = self.portfolio_control.snapshot(self.c)
        n = d["next_expected_release"]
        self.assertEqual(n["amount_rub"], 10_000_000)
        self.assertEqual(n["dependency"], "Security acceptance")
        self.assertEqual(n["owner"], "IT / Security")
        self.assertFalse(n["payment_authorized"])

    def test_deal_room_remediation_moves_12_5m_from_at_risk_to_eligible(self):
        before = self.portfolio_control.snapshot(self.c)
        self.assertEqual(before["totals"]["at_risk"], 12_500_000)
        self.assertEqual(before["totals"]["eligible"], 20_000_000)

        self.deal_room.attach_and_accept_demo(
            self.c,
            "t50",
            "m3",
            "partner_delivery",
            "sales@demo.ru",
            "demo://signed-partner-acceptance",
        )
        self.c.commit()

        after = self.portfolio_control.snapshot(self.c)
        self.assertEqual(after["totals"]["at_risk"], 0)
        self.assertEqual(after["totals"]["eligible"], 32_500_000)
        self.assertEqual(after["totals"]["committed"], 75_000_000)
        self.assertEqual(after["programme"]["decision"], "ITERATE")

    def test_workstreams_reconcile_to_programme_total(self):
        d = self.portfolio_control.snapshot(self.c)
        self.assertEqual(sum(x["committed_rub"] for x in d["workstreams"]), 75_000_000)
        self.assertEqual(len(d["workstreams"]), 4)
        for ws in d["workstreams"]:
            self.assertEqual(
                ws["paid_rub"] + ws["eligible_rub"] + ws["blocked_rub"] + ws["at_risk_rub"],
                ws["committed_rub"],
            )

    def test_forecast_is_not_a_commitment(self):
        d = self.portfolio_control.snapshot(self.c)
        self.assertGreaterEqual(len(d["forecast_cash_release"]), 5)
        self.assertTrue(d["truth_boundary"]["demo_portfolio"])
        self.assertFalse(d["truth_boundary"]["actual_budget"])
        self.assertFalse(d["truth_boundary"]["forecast_is_commitment"])


if __name__ == "__main__":
    unittest.main()
