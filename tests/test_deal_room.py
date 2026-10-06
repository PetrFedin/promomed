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

    def test_owner_inbox_has_three_day_sla_and_escalation(self):
        d = self.deal_room.snapshot(self.c)
        inbox = d["owner_inbox"]
        self.assertEqual(len(inbox), 1)
        item = inbox[0]
        self.assertEqual(item["owner"], "Commercial Director")
        self.assertEqual(item["days_remaining"], 3)
        self.assertEqual(item["escalation_owner"], "Executive Sponsor")
        self.assertEqual(item["status"], "awaiting")

    def test_evidence_registry_hashes_reference(self):
        self.deal_room.snapshot(self.c)
        doc = self.deal_room.register_demo_evidence(
            self.c,
            "t50",
            "m3",
            "partner_delivery",
            "sales@demo.ru",
            "Signed partner delivery acceptance",
            "acceptance_reference",
            "demo://signed-partner-acceptance",
        )
        self.c.commit()
        d = self.deal_room.snapshot(self.c)
        self.assertEqual(len(d["evidence_registry"]), 1)
        self.assertEqual(d["evidence_registry"][0]["id"], doc["id"])
        self.assertEqual(d["evidence_registry"][0]["content_sha256"], doc["sha256"])
        self.assertEqual(len(doc["sha256"]), 64)

    def test_payment_request_is_blocked_until_demo_readiness(self):
        self.deal_room.snapshot(self.c)
        with self.assertRaisesRegex(ValueError, "milestone_not_eligible"):
            self.deal_room.create_demo_payment_request(self.c, "sales@demo.ru")

        self.deal_room.attach_and_accept_demo(
            self.c,
            "t50",
            "m3",
            "partner_delivery",
            "sales@demo.ru",
            "demo://signed-partner-acceptance",
        )
        self.c.commit()
        request_id = self.deal_room.create_demo_payment_request(self.c, "sales@demo.ru")
        self.c.commit()
        d = self.deal_room.snapshot(self.c)
        self.assertEqual(len(d["payment_requests"]), 1)
        self.assertEqual(d["payment_requests"][0]["id"], request_id)
        self.assertEqual(d["payment_requests"][0]["status"], "finance_review_demo")
        self.assertFalse(d["payment_requests"][0]["payment_authorized"])
        self.assertEqual(d["board_packet"]["payment_authority"], "NONE")

    def test_board_packet_export_is_present_and_non_binding(self):
        d = self.deal_room.snapshot(self.c)
        export = d["board_packet"]["export"]
        self.assertTrue(export["ready"])
        self.assertTrue(export["filename"].endswith(".json"))
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
