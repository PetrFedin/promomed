import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import evidence_interchange, institutional_data_room, syndication_network
from app.auth import seed_demo_accounts


class InstitutionalDataRoomTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "SQLITE_PATH":str(Path(self.tmp.name)/"data-room.db"),
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
            organization_id="INST-DATAROOM-DEMO-001",
            name="Synthetic Data Room Institution",
            organization_type="clinic",
            actor="governance@demo.ru",
            external_ref="urn:synthetic:data-room:001",
            credential_source="synthetic test fixture",
            demo_only=True,
        )
        syndication_network.bind_member(
            self.c,"INST-DATAROOM-DEMO-001","participant2@demo.ru","administrator",
            "governance@demo.ru","synthetic-membership-proof",demo_only=True
        )
        evidence_interchange.bind_role(
            self.c,
            organization_id="INST-DATAROOM-DEMO-001",
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

    def _counts(self):
        tables=(
            "institutional_organizations","institutional_memberships",
            "institutional_role_bindings","syndication_partner_qualifications",
            "institutional_federated_anchors","federation_profile_evaluations",
            "federation_discovery_bundles","syndication_delivery_endpoints",
        )
        return {t:self.c.execute(f"SELECT COUNT(*) n FROM {t}").fetchone()["n"] for t in tables}

    def test_data_room_is_read_only_and_deterministic(self):
        before=self._counts()
        first=institutional_data_room.snapshot(self.c,"INST-DATAROOM-DEMO-001")
        second=institutional_data_room.snapshot(self.c,"INST-DATAROOM-DEMO-001")
        after=self._counts()
        self.assertEqual(before,after)
        self.assertEqual(first["export"]["sha256"],second["export"]["sha256"])
        self.assertTrue(first["truthBoundary"]["readOnly"])

    def test_external_participation_remains_gated(self):
        room=institutional_data_room.snapshot(self.c,"INST-DATAROOM-DEMO-001")
        item=next(x for x in room["artifacts"] if x["id"]=="participation_acceptance")
        decision=next(x for x in room["decisions"] if x["id"]=="external_participation_acceptance")
        self.assertEqual(item["state"],"gated")
        self.assertEqual(decision["state"],"gated")
        self.assertFalse(decision["canResolveHere"])
        self.assertEqual(room["truthBoundary"]["externalParticipationAcceptance"],"GATED")

    def test_room_does_not_persist_meeting_decisions(self):
        room=institutional_data_room.snapshot(self.c,"INST-DATAROOM-DEMO-001")
        self.assertFalse(room["truthBoundary"]["meetingNotesPersisted"])
        self.assertFalse(room["truthBoundary"]["decisionAcceptancePersisted"])
        self.assertFalse(room["truthBoundary"]["commercialCommitmentCreated"])
        for decision in room["decisions"]:
            self.assertFalse(decision["canResolveHere"])

    def test_demo_org_stays_demo_and_real_pilot_is_not_claimed(self):
        room=institutional_data_room.snapshot(self.c,"INST-DATAROOM-DEMO-001")
        self.assertTrue(room["organization"]["demoOnly"])
        self.assertFalse(room["truthBoundary"]["realPilotClaimed"])
        self.assertEqual(room["workingSessionState"],"facilitated_read_only")

    def test_open_items_surface_unresolved_readiness_and_procurement(self):
        room=institutional_data_room.snapshot(self.c,"INST-DATAROOM-DEMO-001")
        self.assertTrue(room["openItems"])
        ids={x["id"] for x in room["openItems"]}
        self.assertTrue(any(x.startswith("readiness:") for x in ids))
        self.assertTrue(any(x.startswith("procurement:") for x in ids))


if __name__=="__main__":
    unittest.main()
