import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import evidence_interchange, institutional_followup_board, syndication_network
from app.auth import seed_demo_accounts


class InstitutionalFollowupBoardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "SQLITE_PATH":str(Path(self.tmp.name)/"followup.db"),
            "PROMOMED_SEED_DEMO":"true",
        },clear=False)
        self.env.start()
        import app.db as db
        importlib.reload(db)
        self.c=db.connect()
        db.migrate(self.c)
        seed_demo_accounts(self.c)
        evidence_interchange.register_organization(
            self.c,
            organization_id="INST-FOLLOWUP-DEMO-001",
            name="Synthetic Follow-up Institution",
            organization_type="strategic_partner",
            actor="governance@demo.ru",
            external_ref="urn:synthetic:followup:001",
            credential_source="synthetic test fixture",
            demo_only=True,
        )
        syndication_network.bind_member(
            self.c,"INST-FOLLOWUP-DEMO-001","participant2@demo.ru","administrator",
            "governance@demo.ru","synthetic-membership-proof",demo_only=True
        )
        evidence_interchange.bind_role(
            self.c,
            organization_id="INST-FOLLOWUP-DEMO-001",
            role_scope="consumer",
            actor="governance@demo.ru",
            verification_ref="synthetic-role-proof",
            demo_only=True,
        )
        self.c.commit()

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.tmp.cleanup()

    def test_board_is_read_only(self):
        board=institutional_followup_board.snapshot(self.c,"INST-FOLLOWUP-DEMO-001")
        self.assertTrue(board["truthBoundary"]["readOnly"])
        self.assertFalse(board["truthBoundary"]["documentReceiptPersistedHere"])
        self.assertFalse(board["truthBoundary"]["reviewDispositionPersistedHere"])
        self.assertFalse(board["truthBoundary"]["approvalPersistedHere"])

    def test_ready_for_decision_is_not_approval(self):
        board=institutional_followup_board.snapshot(self.c,"INST-FOLLOWUP-DEMO-001")
        self.assertFalse(board["truthBoundary"]["readyForDecisionEqualsApproved"])
        self.assertIn("READY_FOR_DECISION",board["summary"]["counts"])

    def test_items_cannot_be_manually_advanced_or_approved_here(self):
        board=institutional_followup_board.snapshot(self.c,"INST-FOLLOWUP-DEMO-001")
        self.assertTrue(board["items"])
        for item in board["items"]:
            self.assertFalse(item["canMarkReceivedHere"])
            self.assertFalse(item["canStartReviewHere"])
            self.assertFalse(item["canApproveHere"])

    def test_participation_acceptance_remains_gap_and_gated(self):
        board=institutional_followup_board.snapshot(self.c,"INST-FOLLOWUP-DEMO-001")
        item=next(x for x in board["items"] if x["id"]=="participation_acceptance")
        self.assertEqual(item["state"],"GAP")
        self.assertTrue(item["blocksPilot"])
        self.assertEqual(board["truthBoundary"]["externalParticipationAcceptance"],"GATED")
        self.assertFalse(board["truthBoundary"]["realPilotClaimed"])

    def test_export_is_deterministic(self):
        first=institutional_followup_board.snapshot(self.c,"INST-FOLLOWUP-DEMO-001",now=1234567890)
        second=institutional_followup_board.snapshot(self.c,"INST-FOLLOWUP-DEMO-001",now=1234567890)
        self.assertEqual(first["export"]["sha256"],second["export"]["sha256"])
        self.assertEqual(len(first["export"]["sha256"]),64)

    def test_columns_are_exact_contract(self):
        board=institutional_followup_board.snapshot(self.c,"INST-FOLLOWUP-DEMO-001")
        states=[x["state"] for x in board["columns"]]
        self.assertEqual(states,["REQUESTED","RECEIVED","UNDER_REVIEW","GAP","READY_FOR_DECISION"])


if __name__=="__main__":
    unittest.main()
