import os
import tempfile
import unittest
from pathlib import Path


class PilotDealRoomTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "deal-room.db")
        os.environ["PROMOMED_SEED_DEMO"] = "true"
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("PROMOMED_REQUIRE_POSTGRES", None)

        import importlib
        import app.db as db
        import app.deal_room as deal_room
        import server

        importlib.reload(db)
        importlib.reload(deal_room)
        importlib.reload(server)
        self.deal_room = deal_room
        self.server = server
        self.server.init()
        self.c = self.server.conn()

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def test_seeded_case_is_four_of_five_and_payment_blocked(self):
        d = self.deal_room.snapshot(self.c)
        self.assertEqual(d["deal"]["tranche_id"], "t50")
        self.assertEqual(d["deal"]["milestone_id"], "m3")
        self.assertEqual(d["deal"]["amount_rub"], 12_500_000)
        self.assertEqual(d["readiness"]["accepted_count"], 4)
        self.assertEqual(d["readiness"]["required_count"], 5)
        self.assertEqual(d["readiness"]["open_issue_count"], 1)
        self.assertEqual(d["readiness"]["state"], "BLOCKED")
        self.assertFalse(d["readiness"]["demo_payment_eligible"])
        self.assertFalse(d["readiness"]["actual_payment_authorized"])

    def test_missing_partner_acceptance_is_the_blocker(self):
        d = self.deal_room.snapshot(self.c)
        partner = {x["id"]: x for x in d["obligations"]}["partner_delivery"]
        self.assertEqual(partner["status"], "awaiting")
        self.assertEqual(partner["owner"], "Commercial Director")
        self.assertIn("Signed partner delivery acceptance", partner["required_evidence"])
        self.assertEqual(len([x for x in d["issues"] if x["status"] == "open"]), 1)

    def test_demo_remediation_makes_only_demo_preview_eligible(self):
        self.deal_room.snapshot(self.c)
        self.deal_room.attach_and_accept_demo(
            self.c,
            "t50",
            "m3",
            "partner_delivery",
            "sales@demo.ru",
            "demo://signed-partner-acceptance",
        )
        self.c.commit()
        d = self.deal_room.snapshot(self.c)
        self.assertEqual(d["readiness"]["accepted_count"], 5)
        self.assertEqual(d["readiness"]["open_issue_count"], 0)
        self.assertEqual(d["readiness"]["state"], "ELIGIBLE_DEMO_PREVIEW")
        self.assertTrue(d["readiness"]["demo_payment_eligible"])
        self.assertFalse(d["readiness"]["actual_payment_authorized"])
        self.assertEqual(d["board_packet"]["decision_preview"], "GO_TO_FINANCE_REVIEW")
        self.assertEqual(d["board_packet"]["legal_effect"], "NONE")
        self.assertEqual(d["board_packet"]["payment_authority"], "NONE")

    def test_reset_restores_blocked_case(self):
        self.deal_room.attach_and_accept_demo(
            self.c,
            "t50",
            "m3",
            "partner_delivery",
            "sales@demo.ru",
            "demo://signed-partner-acceptance",
        )
        self.c.commit()
        self.deal_room.reset_demo(self.c, "sales@demo.ru")
        self.c.commit()
        d = self.deal_room.snapshot(self.c)
        self.assertEqual(d["readiness"]["accepted_count"], 4)
        self.assertEqual(d["readiness"]["open_issue_count"], 1)
        self.assertEqual(d["readiness"]["state"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
