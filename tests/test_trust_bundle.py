import base64
import importlib
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app import evidence_checkpoint, evidence_interchange, syndication_network, trust_bundle
from app.auth import seed_demo_accounts


def _key_b64():
    private=Ed25519PrivateKey.generate()
    raw=private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


class PartnerTrustBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(
            os.environ,
            {
                "SQLITE_PATH":str(Path(self.tmp.name)/"trust.db"),
                "PROMOMED_SEED_DEMO":"true",
                "PROMOMED_EVIDENCE_ISSUER_ID":"promomed-trust-test",
                "PROMOMED_EVIDENCE_KEY_ID":"trust-key-v1",
                "PROMOMED_EVIDENCE_SIGNING_PRIVATE_KEY_B64":_key_b64(),
            },
            clear=False,
        )
        self.env.start()
        import app.db as db
        importlib.reload(db)
        self.db=db
        self.c=db.connect()
        db.migrate(self.c)
        seed_demo_accounts(self.c)
        self._register_subject()
        self._qualify_subject()
        self._register_verifier()

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.tmp.cleanup()

    def _register_subject(self):
        evidence_interchange.register_organization(
            self.c,
            organization_id="INST-TRUST-001",
            name="Synthetic Trust Society",
            organization_type="scientific_society",
            actor="governance@demo.ru",
            external_ref="urn:synthetic:trust:001",
            credential_source="synthetic test fixture",
            demo_only=True,
        )

    def _qualify_subject(self):
        q=syndication_network.start_qualification(
            self.c,"INST-TRUST-001","governance@demo.ru",
            validity_seconds=864000,demo_only=True,
        )
        qid=q["qualification"]["id"]
        for scope in syndication_network.REQUIRED_CONFORMANCE_SCOPES:
            syndication_network.record_conformance(
                self.c,qid,scope,"passed","governance@demo.ru",
                "urn:test:"+scope,"Synthetic evidence."
            )
        syndication_network.finalize_qualification(
            self.c,qid,"governance@demo.ru",validity_seconds=864000
        )

    def _register_verifier(self):
        evidence_interchange.register_organization(
            self.c,
            organization_id="INST-VERIFY-001",
            name="Synthetic Verifier University",
            organization_type="university",
            actor="governance@demo.ru",
            external_ref="urn:synthetic:verifier:001",
            credential_source="synthetic test fixture",
            demo_only=True,
        )
        syndication_network.bind_member(
            self.c,
            "INST-VERIFY-001",
            "participant2@demo.ru",
            "operator",
            "governance@demo.ru",
            "synthetic-membership-proof",
            demo_only=True,
        )

    def test_snapshot_is_stable_without_state_change(self):
        now=int(time.time())
        first=trust_bundle.issue_snapshot(
            self.c,"INST-TRUST-001","governance@demo.ru",now=now
        )
        replay=trust_bundle.issue_snapshot(
            self.c,"INST-TRUST-001","governance@demo.ru",now=now+10
        )
        self.assertEqual(first["id"],replay["id"])
        self.assertEqual(first["snapshotSha256"],replay["snapshotSha256"])
        self.assertTrue(replay["idempotentReplay"])

        body=first["envelope"]["payload"]["body"]
        self.assertEqual(body["snapshotVersion"],trust_bundle.SNAPSHOT_VERSION)
        self.assertFalse(body["medicalEfficacyCertified"])
        self.assertFalse(body["state"]["truthBoundary"]["professionalAccreditation"])
        self.assertFalse(body["state"]["deliveryTrust"]["hasActiveEndpoint"])

    def test_state_change_creates_new_snapshot_and_supersedes_old(self):
        now=int(time.time())
        first=trust_bundle.issue_snapshot(
            self.c,"INST-TRUST-001","governance@demo.ru",now=now
        )
        syndication_network.suspend_qualification(
            self.c,"INST-TRUST-001","Synthetic suspension","governance@demo.ru"
        )
        second=trust_bundle.issue_snapshot(
            self.c,"INST-TRUST-001","governance@demo.ru",now=now+1
        )
        self.assertNotEqual(first["id"],second["id"])
        old=trust_bundle.snapshot_document(self.c,first["id"])
        new=trust_bundle.snapshot_document(self.c,second["id"])
        self.assertEqual(old["status"],"superseded")
        self.assertEqual(new["status"],"current")
        self.assertEqual(new["supersedesSnapshotId"],first["id"])
        self.assertEqual(
            new["envelope"]["payload"]["body"]["state"]["certification"]["qualificationStatus"],
            "suspended",
        )

    def test_bundle_verifies_without_database_or_private_key(self):
        snapshot=trust_bundle.issue_snapshot(
            self.c,"INST-TRUST-001","governance@demo.ru"
        )
        document=trust_bundle.create_trust_bundle(
            self.c,snapshot["id"],"governance@demo.ru"
        )["bundle"]
        with patch.dict(os.environ,{},clear=False):
            os.environ.pop("PROMOMED_EVIDENCE_SIGNING_PRIVATE_KEY_B64",None)
            result=trust_bundle.verify_bundle_portable(document)
        self.assertEqual(result["status"],"VALID_TRUST_BUNDLE")
        self.assertTrue(result["bundleHashValid"])
        self.assertTrue(result["snapshotSignatureValid"])
        self.assertFalse(result["currentPromomedStateVerified"])
        self.assertFalse(result["medicalEfficacyCertified"])

        tampered={**document,"createdAt":document["createdAt"]+1}
        bad=trust_bundle.verify_bundle_portable(tampered)
        self.assertEqual(bad["status"],"INVALID_BUNDLE_HASH")

    def test_fresh_status_material_exposes_snapshot_revocation(self):
        snapshot=trust_bundle.issue_snapshot(
            self.c,"INST-TRUST-001","governance@demo.ru"
        )
        bundle=trust_bundle.create_trust_bundle(
            self.c,snapshot["id"],"governance@demo.ru"
        )["bundle"]
        trust_bundle.revoke_snapshot(
            self.c,snapshot["id"],"Synthetic trust revocation","governance@demo.ru"
        )
        fresh_status=trust_bundle.signed_status_statement(
            self.c,"INST-TRUST-001","governance@demo.ru"
        )
        issuer=evidence_checkpoint.issuer_document(self.c)
        result=trust_bundle.verify_bundle_portable(
            bundle,
            current_status_statement=fresh_status,
            current_issuer_document=issuer,
        )
        self.assertEqual(result["status"],"REVOKED_SNAPSHOT")
        self.assertTrue(result["currentPromomedStateVerified"])
        self.assertEqual(result["revocation"]["reason"],"Synthetic trust revocation")

    def test_new_snapshot_preserves_lineage_after_revoked_predecessor(self):
        now=int(time.time())
        first=trust_bundle.issue_snapshot(
            self.c,"INST-TRUST-001","governance@demo.ru",now=now
        )
        trust_bundle.revoke_snapshot(
            self.c,first["id"],"Synthetic predecessor revocation",
            "governance@demo.ru",now=now+1
        )
        second=trust_bundle.issue_snapshot(
            self.c,"INST-TRUST-001","governance@demo.ru",now=now+2
        )
        old=trust_bundle.snapshot_document(self.c,first["id"])
        new=trust_bundle.snapshot_document(self.c,second["id"])
        self.assertEqual(old["status"],"revoked")
        self.assertEqual(new["status"],"current")
        self.assertEqual(new["supersedesSnapshotId"],first["id"])

    def test_snapshot_expiry_is_distinct_from_revocation(self):
        now=int(time.time())
        snapshot=trust_bundle.issue_snapshot(
            self.c,"INST-TRUST-001","governance@demo.ru",
            validity_seconds=3600,now=now,
        )
        bundle=trust_bundle.create_trust_bundle(
            self.c,snapshot["id"],"governance@demo.ru",now=now
        )["bundle"]
        result=trust_bundle.verify_bundle_portable(bundle,now=now+3601)
        self.assertEqual(result["status"],"EXPIRED_SNAPSHOT")
        self.assertTrue(result["snapshotExpired"])

    def test_current_issuer_key_revocation_is_distinct(self):
        snapshot=trust_bundle.issue_snapshot(
            self.c,"INST-TRUST-001","governance@demo.ru"
        )
        bundle=trust_bundle.create_trust_bundle(
            self.c,snapshot["id"],"governance@demo.ru"
        )["bundle"]
        payload=snapshot["envelope"]["payload"]
        evidence_checkpoint.revoke_key(
            self.c,payload["issuerId"],payload["keyId"],
            "Synthetic issuer key revocation","governance@demo.ru"
        )
        current_issuer=evidence_checkpoint.issuer_document(self.c,payload["issuerId"])
        result=trust_bundle.verify_bundle_portable(
            bundle,current_issuer_document=current_issuer
        )
        self.assertEqual(result["status"],"REVOKED_ISSUER_KEY")

    def test_external_verification_receipt_is_idempotent_and_non_authoritative(self):
        snapshot=trust_bundle.issue_snapshot(
            self.c,"INST-TRUST-001","governance@demo.ru"
        )
        bundle=trust_bundle.create_trust_bundle(
            self.c,snapshot["id"],"governance@demo.ru"
        )
        before=syndication_network.qualification_snapshot(
            self.c,"INST-TRUST-001"
        )["qualification"]["status"]

        receipt=trust_bundle.record_cross_organization_verification(
            self.c,bundle["id"],"INST-VERIFY-001","participant2@demo.ru"
        )
        self.assertEqual(receipt["verificationStatus"],"valid_bundle")
        self.assertFalse(receipt["authorityBoundary"]["changesPartnerQualification"])
        self.assertFalse(receipt["authorityBoundary"]["changesCanonicalEvidence"])
        self.assertFalse(receipt["authorityBoundary"]["changesIssuerState"])
        self.assertFalse(receipt["authorityBoundary"]["externalEndorsementInferred"])

        replay=trust_bundle.record_cross_organization_verification(
            self.c,bundle["id"],"INST-VERIFY-001","participant2@demo.ru"
        )
        self.assertTrue(replay["idempotentReplay"])
        self.assertEqual(replay["id"],receipt["id"])

        after=syndication_network.qualification_snapshot(
            self.c,"INST-TRUST-001"
        )["qualification"]["status"]
        self.assertEqual(before,after)

    def test_snapshot_bundle_and_verification_audits_are_immutable(self):
        snapshot=trust_bundle.issue_snapshot(
            self.c,"INST-TRUST-001","governance@demo.ru"
        )
        bundle=trust_bundle.create_trust_bundle(
            self.c,snapshot["id"],"governance@demo.ru"
        )
        receipt=trust_bundle.record_cross_organization_verification(
            self.c,bundle["id"],"INST-VERIFY-001","participant2@demo.ru"
        )
        self.c.commit()

        with self.assertRaises(Exception):
            self.c.execute(
                "UPDATE institutional_status_snapshots SET schema_version='bad' WHERE id=?",
                (snapshot["id"],),
            )
        self.c.rollback()
        with self.assertRaises(Exception):
            self.c.execute(
                "DELETE FROM institutional_trust_bundles WHERE id=?",
                (bundle["id"],),
            )
        self.c.rollback()
        with self.assertRaises(Exception):
            self.c.execute(
                "UPDATE institutional_trust_verifications SET verification_status='invalid_bundle' WHERE id=?",
                (receipt["id"],),
            )
        self.c.rollback()


if __name__=="__main__":
    unittest.main()
