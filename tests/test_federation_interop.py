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

from app import (
    evidence_checkpoint,
    evidence_interchange,
    federated_trust,
    federation_interop,
    syndication_network,
)
from app.auth import seed_demo_accounts


def _promomed_key():
    key=Ed25519PrivateKey.generate()
    raw=key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _institution_keypair():
    private=Ed25519PrivateKey.generate()
    raw=private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private,base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _sign(private,payload):
    import json
    raw=json.dumps(
        payload,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str
    ).encode("utf-8")
    return base64.urlsafe_b64encode(private.sign(raw)).decode("ascii").rstrip("=")


class FederationInteroperabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "SQLITE_PATH":str(Path(self.tmp.name)/"interop.db"),
            "PROMOMED_SEED_DEMO":"true",
            "PROMOMED_EVIDENCE_ISSUER_ID":"promomed-interop-test",
            "PROMOMED_EVIDENCE_KEY_ID":"promomed-interop-key-v1",
            "PROMOMED_EVIDENCE_SIGNING_PRIVATE_KEY_B64":_promomed_key(),
            "PROMOMED_TRUST_PUBLIC_HOST":"trust.example.test",
        },clear=False)
        self.env.start()
        import app.db as db
        importlib.reload(db)
        self.c=db.connect()
        db.migrate(self.c)
        seed_demo_accounts(self.c)
        evidence_interchange.register_organization(
            self.c,
            organization_id="INST-INTEROP-001",
            name="Synthetic Interop University",
            organization_type="university",
            actor="governance@demo.ru",
            external_ref="urn:synthetic:interop:001",
            credential_source="synthetic test fixture",
            demo_only=True,
        )
        syndication_network.bind_member(
            self.c,"INST-INTEROP-001","participant2@demo.ru","administrator",
            "governance@demo.ru","synthetic-membership-proof",demo_only=True
        )

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.tmp.cleanup()

    def _admit_anchor(self):
        private,public=_institution_keypair()
        proposed=federated_trust.propose_anchor(
            self.c,"INST-INTEROP-001","urn:synthetic:interop","interop-key-v1",
            public,"participant2@demo.ru",source_ref="urn:test:key",
            metadata={"purpose":"interoperability"},demo_only=True
        )
        proof=_sign(private,proposed["proof"])
        federated_trust.verify_anchor_proof(
            self.c,proposed["anchor"]["id"],proof,"participant2@demo.ru"
        )
        anchor=federated_trust.activate_anchor(
            self.c,proposed["anchor"]["id"],"governance@demo.ru",
            validity_seconds=864000
        )
        return private,anchor

    def test_public_profile_and_manifest_reads_are_side_effect_free(self):
        before=self.c.execute(
            "SELECT COUNT(*) n FROM federation_interoperability_profiles"
        ).fetchone()["n"]
        profile=federation_interop.public_profile(self.c)
        manifest=federation_interop.discovery_manifest(self.c)
        after=self.c.execute(
            "SELECT COUNT(*) n FROM federation_interoperability_profiles"
        ).fetchone()["n"]
        self.assertEqual(before,0)
        self.assertEqual(after,0)
        self.assertFalse(profile["persisted"])
        self.assertEqual(manifest["profile"]["sha256"],profile["profileSha256"])

    def test_profile_is_deterministic_and_version_collision_safe(self):
        now=int(time.time())
        first=federation_interop.ensure_profile(self.c,"governance@demo.ru",now=now)
        replay=federation_interop.ensure_profile(self.c,"governance@demo.ru",now=now+30)
        self.assertEqual(first["profileSha256"],replay["profileSha256"])
        self.assertEqual(first["id"],replay["id"])
        self.assertTrue(replay["idempotentReplay"])
        self.assertFalse(first["profile"]["governance"]["discoveryDoesNotAdmitKeys"] is False)
        self.assertFalse(first["profile"]["truthBoundary"]["externalAdoptionInferred"])

    def test_no_active_anchor_is_not_compatible_and_does_not_admit_anything(self):
        before=self.c.execute(
            "SELECT COUNT(*) n FROM institutional_federated_anchors"
        ).fetchone()["n"]
        result=federation_interop.evaluate_compatibility(
            self.c,"INST-INTEROP-001","governance@demo.ru"
        )
        self.assertEqual(result["compatibilityStatus"],"no_active_anchor")
        self.assertIn("active_anchor_required",result["failures"])
        after=self.c.execute(
            "SELECT COUNT(*) n FROM institutional_federated_anchors"
        ).fetchone()["n"]
        self.assertEqual(before,after)
        self.assertFalse(result["authorityBoundary"]["changesAnchorAdmission"])

    def test_active_admitted_anchor_is_compatible(self):
        _,anchor=self._admit_anchor()
        result=federation_interop.evaluate_compatibility(
            self.c,"INST-INTEROP-001","governance@demo.ru"
        )
        self.assertEqual(result["compatibilityStatus"],"compatible")
        self.assertEqual(result["anchorId"],anchor["id"])
        self.assertEqual(result["failures"],[])
        self.assertFalse(result["authorityBoundary"]["createsAccreditation"])

    def test_valid_genesis_to_v2_rotation_remains_compatible(self):
        _,first=self._admit_anchor()
        private2,public2=_institution_keypair()
        proposed=federated_trust.propose_anchor(
            self.c,"INST-INTEROP-001","urn:synthetic:interop","interop-key-v2",
            public2,"participant2@demo.ru",source_ref="urn:test:key-v2",
            rotated_from_anchor_id=first["id"],demo_only=True
        )
        proof=_sign(private2,proposed["proof"])
        federated_trust.verify_anchor_proof(
            self.c,proposed["anchor"]["id"],proof,"participant2@demo.ru"
        )
        federated_trust.activate_anchor(
            self.c,proposed["anchor"]["id"],"governance@demo.ru",
            validity_seconds=864000
        )
        result=federation_interop.evaluate_compatibility(
            self.c,"INST-INTEROP-001","governance@demo.ru"
        )
        self.assertEqual(result["compatibilityStatus"],"compatible")
        self.assertEqual(result["warnings"],[])

    def test_public_directory_is_scoped_and_exposes_no_internal_proof_material(self):
        self._admit_anchor()
        directory=federation_interop.anchor_directory(self.c,"INST-INTEROP-001")
        self.assertEqual(len(directory),1)
        doc=directory[0]
        self.assertEqual(doc["organizationId"],"INST-INTEROP-001")
        self.assertTrue(doc["proofVerified"])
        text=str(doc)
        self.assertNotIn("proofChallenge",text)
        self.assertNotIn("proof_signature",text)
        self.assertNotIn("private",text.lower())

    def test_manifest_is_discovery_not_admission(self):
        manifest=federation_interop.discovery_manifest(self.c)
        self.assertEqual(manifest["discoveryVersion"],federation_interop.DISCOVERY_VERSION)
        self.assertFalse(manifest["truthBoundary"]["discoveryIsAdmission"])
        self.assertFalse(manifest["truthBoundary"]["discoveredKeyAutomaticallyTrusted"])
        self.assertFalse(manifest["truthBoundary"]["profileCompatibilityIsAccreditation"])

    def test_signed_discovery_bundle_verifies_without_database_or_private_key(self):
        self._admit_anchor()
        now=int(time.time())
        issued=federation_interop.issue_discovery_bundle(
            self.c,"INST-INTEROP-001","governance@demo.ru",now=now
        )
        issuer=evidence_checkpoint.issuer_document(self.c)
        with patch.dict(os.environ,{},clear=False):
            os.environ.pop("PROMOMED_EVIDENCE_SIGNING_PRIVATE_KEY_B64",None)
            result=federation_interop.verify_discovery_bundle(
                issued["bundle"],issuer,now=now+1
            )
        self.assertEqual(result["status"],"VALID_FEDERATION_DISCOVERY_BUNDLE")
        self.assertTrue(result["valid"])
        self.assertEqual(result["compatibilityStatus"],"compatible")
        self.assertFalse(result["discoveryIsAdmission"])
        self.assertFalse(result["externalAdoptionInferred"])

    def test_discovery_bundle_expiry_and_profile_hash_are_enforced(self):
        self._admit_anchor()
        now=int(time.time())
        issued=federation_interop.issue_discovery_bundle(
            self.c,"INST-INTEROP-001","governance@demo.ru",
            validity_seconds=300,now=now
        )
        issuer=evidence_checkpoint.issuer_document(self.c)
        expired=federation_interop.verify_discovery_bundle(
            issued["bundle"],issuer,now=now+301
        )
        self.assertEqual(expired["status"],"DISCOVERY_BUNDLE_EXPIRED")

        tampered=dict(issued["bundle"])
        payload=dict(tampered["payload"])
        body=dict(payload["body"])
        profile=dict(body["profile"])
        profile["sha256"]="0"*64
        body["profile"]=profile
        payload["body"]=body
        tampered["payload"]=payload
        result=federation_interop.verify_discovery_bundle(tampered,issuer,now=now+1)
        self.assertNotEqual(result["status"],"VALID_FEDERATION_DISCOVERY_BUNDLE")

    def test_profile_evaluation_and_discovery_bundle_audits_are_immutable(self):
        self._admit_anchor()
        evaluation=federation_interop.evaluate_compatibility(
            self.c,"INST-INTEROP-001","governance@demo.ru"
        )
        bundle=federation_interop.issue_discovery_bundle(
            self.c,"INST-INTEROP-001","governance@demo.ru"
        )
        self.c.commit()
        with self.assertRaises(Exception):
            self.c.execute(
                "UPDATE federation_profile_evaluations SET compatibility_status='incompatible' WHERE id=?",
                (evaluation["id"],)
            )
        self.c.rollback()
        with self.assertRaises(Exception):
            self.c.execute(
                "DELETE FROM federation_discovery_bundles WHERE id=?",
                (bundle["id"],)
            )
        self.c.rollback()


if __name__=="__main__":
    unittest.main()
