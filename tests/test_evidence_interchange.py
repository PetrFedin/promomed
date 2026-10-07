import base64
import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app import change_impact, evidence_checkpoint, evidence_graph, evidence_interchange


def _key_b64():
    private=Ed25519PrivateKey.generate()
    raw=private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


class EvidenceInterchangeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(
            os.environ,
            {
                "SQLITE_PATH":str(Path(self.tmp.name)/"interchange.db"),
                "PROMOMED_SEED_DEMO":"true",
                "PROMOMED_EVIDENCE_ISSUER_ID":"promomed-interchange-test",
                "PROMOMED_EVIDENCE_KEY_ID":"interchange-key-v1",
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
        evidence_graph.seed_demo(self.c)

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.tmp.cleanup()

    def _organization(self,role_scope="consumer"):
        evidence_interchange.register_organization(
            self.c,
            organization_id="INST-TEST-001",
            name="Synthetic University",
            organization_type="university",
            actor="governance@test",
            external_ref="urn:synthetic:university:001",
            credential_source="synthetic fixture only",
            demo_only=True,
        )
        evidence_interchange.bind_role(
            self.c,
            organization_id="INST-TEST-001",
            role_scope=role_scope,
            actor="governance@test",
            verification_ref="synthetic-role-proof",
            demo_only=True,
        )

    def _package(self):
        evidence_checkpoint.issue(self.c,"content","CT01")
        return evidence_interchange.create_package(
            self.c,
            artifact_kind="content",
            artifact_ref="CT01",
            actor="governance@test",
        )

    def test_profile_is_machine_bounded_and_privacy_minimised(self):
        profile=evidence_interchange.interchange_profile(
            self.c,artifact_kind="content",artifact_ref="CT01"
        )
        self.assertEqual(
            profile["profileVersion"],
            "promomed-evidence-governance-interchange-v1",
        )
        self.assertTrue(profile["approval"]["processValid"])
        self.assertIsNone(profile["approval"]["reviewUntil"])
        self.assertEqual(
            profile["approval"]["reviewValidityPolicy"],
            "not_configured_in_current_authority",
        )
        self.assertFalse(profile["truthBoundary"]["reviewerIdentityExported"])
        self.assertFalse(profile["truthBoundary"]["medicalEfficacyCertified"])
        self.assertGreaterEqual(len(profile["sources"]),1)
        self.assertGreaterEqual(len(profile["claims"]),1)
        self.assertNotIn("reviewer",profile["claims"][0]["review"])

    def test_package_binds_profile_to_current_signed_checkpoint(self):
        package=self._package()
        document=evidence_interchange.package_document(self.c,package["id"])
        self.assertEqual(document["state"],"active")
        self.assertTrue(document["integrity"]["packageHashValid"])
        self.assertEqual(
            document["integrity"]["checkpointVerification"]["status"],
            "VALID_PORTABLE",
        )
        self.assertEqual(
            document["payload"]["profile"]["approval"]["evidencePackageSha256"],
            document["payload"]["checkpoint"]["payload"]["sealSha256"],
        )
        self.assertFalse(
            document["payload"]["profile"]["truthBoundary"]["medicalEfficacyCertified"]
        )
        self.assertFalse(document["payload"]["syndication"]["partnerMayRewriteClaims"])

    def test_delivery_requires_explicit_institutional_role(self):
        package=self._package()
        self._organization("consumer")

        delivery=evidence_interchange.deliver_package(
            self.c,
            package_id=package["id"],
            organization_id="INST-TEST-001",
            actor="governance@test",
            delivery_role="consumer",
        )
        self.assertEqual(delivery["status"],"delivered")

        with self.assertRaisesRegex(ValueError,"institutional_role_not_active"):
            evidence_interchange.deliver_package(
                self.c,
                package_id=package["id"],
                organization_id="INST-TEST-001",
                actor="governance@test",
                delivery_role="publisher",
            )

    def test_source_retraction_propagates_withdrawal_to_delivered_package(self):
        package=self._package()
        self._organization("consumer")
        delivery=evidence_interchange.deliver_package(
            self.c,
            package_id=package["id"],
            organization_id="INST-TEST-001",
            actor="governance@test",
            delivery_role="consumer",
        )
        evidence_interchange.acknowledge_delivery(
            self.c,delivery["id"],"INST-TEST-001"
        )

        change_impact.analyze_source_change(
            self.c,
            "ES01",
            "source_retracted",
            "Synthetic retraction propagation test",
            "editor@test",
        )

        package_row=self.c.execute(
            "SELECT state FROM evidence_exchange_packages WHERE id=?",
            (package["id"],),
        ).fetchone()
        delivery_row=self.c.execute(
            "SELECT status,withdrawal_reason FROM evidence_exchange_deliveries WHERE id=?",
            (delivery["id"],),
        ).fetchone()
        self.assertEqual(package_row["state"],"withdrawn")
        self.assertEqual(delivery_row["status"],"withdrawn")
        self.assertIn("source_retracted",delivery_row["withdrawal_reason"])

    def test_reference_package_is_deterministic_and_non_clinical(self):
        one=evidence_interchange.reference_package()
        two=evidence_interchange.reference_package()
        self.assertEqual(one["referencePackageSha256"],two["referencePackageSha256"])
        self.assertEqual(one["exampleType"],"synthetic_non_clinical")
        self.assertFalse(one["truthBoundary"]["medicalAdvice"])
        self.assertFalse(one["truthBoundary"]["medicalEfficacyCertified"])
        self.assertEqual(one["lifecycle"][-1]["event"],"corrected_package_published")


if __name__=="__main__":
    unittest.main()
