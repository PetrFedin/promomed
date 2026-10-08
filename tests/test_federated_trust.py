import base64
import importlib
import json
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
    syndication_network,
    trust_bundle,
)
from app.auth import seed_demo_accounts


def _keypair():
    private=Ed25519PrivateKey.generate()
    public=private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private,base64.urlsafe_b64encode(public).decode("ascii").rstrip("=")


def _promomed_private_b64():
    private=Ed25519PrivateKey.generate()
    raw=private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _sign(private,payload):
    raw=json.dumps(
        payload,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str
    ).encode("utf-8")
    return base64.urlsafe_b64encode(private.sign(raw)).decode("ascii").rstrip("=")


class FederatedTrustAnchorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(
            os.environ,
            {
                "SQLITE_PATH":str(Path(self.tmp.name)/"federation.db"),
                "PROMOMED_SEED_DEMO":"true",
                "PROMOMED_EVIDENCE_ISSUER_ID":"promomed-federation-test",
                "PROMOMED_EVIDENCE_KEY_ID":"promomed-federation-key-v1",
                "PROMOMED_EVIDENCE_SIGNING_PRIVATE_KEY_B64":_promomed_private_b64(),
                "PROMOMED_TRUST_PUBLIC_HOST":"trust.example.test",
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
        self._register_verifier()
        self._qualify_subject()
        self.subject_snapshot=trust_bundle.issue_snapshot(
            self.c,"INST-FED-SUBJECT","governance@demo.ru"
        )
        self.bundle=trust_bundle.create_trust_bundle(
            self.c,self.subject_snapshot["id"],"governance@demo.ru"
        )
        self.private1,self.public1=_keypair()
        self.anchor1=self._admit_anchor(
            self.private1,self.public1,"federated-key-v1",None
        )

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.tmp.cleanup()

    def _register_subject(self):
        evidence_interchange.register_organization(
            self.c,
            organization_id="INST-FED-SUBJECT",
            name="Synthetic Subject Society",
            organization_type="scientific_society",
            actor="governance@demo.ru",
            external_ref="urn:synthetic:federation:subject",
            credential_source="synthetic test fixture",
            demo_only=True,
        )

    def _register_verifier(self):
        evidence_interchange.register_organization(
            self.c,
            organization_id="INST-FED-VERIFY",
            name="Synthetic Verifier University",
            organization_type="university",
            actor="governance@demo.ru",
            external_ref="urn:synthetic:federation:verifier",
            credential_source="synthetic test fixture",
            demo_only=True,
        )
        syndication_network.bind_member(
            self.c,
            "INST-FED-VERIFY",
            "participant2@demo.ru",
            "administrator",
            "governance@demo.ru",
            "synthetic-membership-proof",
            demo_only=True,
        )

    def _qualify_subject(self):
        q=syndication_network.start_qualification(
            self.c,"INST-FED-SUBJECT","governance@demo.ru",
            validity_seconds=864000,demo_only=True,
        )
        qid=q["qualification"]["id"]
        for scope in syndication_network.REQUIRED_CONFORMANCE_SCOPES:
            syndication_network.record_conformance(
                self.c,qid,scope,"passed","governance@demo.ru",
                "urn:test:"+scope,"Synthetic conformance proof."
            )
        syndication_network.finalize_qualification(
            self.c,qid,"governance@demo.ru",validity_seconds=864000
        )

    def _admit_anchor(self,private,public,key_id,rotated_from):
        proposed=federated_trust.propose_anchor(
            self.c,
            "INST-FED-VERIFY",
            "urn:synthetic:verifier",
            key_id,
            public,
            "participant2@demo.ru",
            source_ref="urn:test:institution-key",
            metadata={"purpose":"trust-verification"},
            rotated_from_anchor_id=rotated_from,
            demo_only=True,
        )
        signature=_sign(private,proposed["proof"])
        proved=federated_trust.verify_anchor_proof(
            self.c,proposed["anchor"]["id"],signature,"participant2@demo.ru"
        )
        self.assertEqual(proved["status"],"pending_governance")
        return federated_trust.activate_anchor(
            self.c,proposed["anchor"]["id"],"governance@demo.ru",
            validity_seconds=864000,
        )

    def _receipt(self,anchor,private,verified_at=None,material=None):
        verified_at=int(verified_at or time.time())
        bundle_doc=trust_bundle.bundle_document(self.c,self.bundle["id"])
        material=material or {}
        result=trust_bundle.verify_bundle_portable(
            bundle_doc["bundle"],
            current_status_statement=material.get("current_status_statement"),
            current_issuer_document=material.get("current_issuer_document"),
            now=verified_at,
        )
        body=federated_trust.verification_receipt_body(
            bundle_doc,
            "INST-FED-VERIFY",
            anchor["id"],
            anchor["issuerId"],
            anchor["keyId"],
            result,
            verified_at,
            material,
        )
        signature=_sign(private,body)
        return body,signature

    def test_proof_of_possession_and_governance_are_separate_authorities(self):
        private,public=_keypair()
        proposed=federated_trust.propose_anchor(
            self.c,"INST-FED-VERIFY","urn:synthetic:verifier","pending-key",
            public,"participant2@demo.ru",demo_only=True,
            rotated_from_anchor_id=self.anchor1["id"],
        )
        with self.assertRaisesRegex(ValueError,"federated_anchor_proof_invalid"):
            federated_trust.verify_anchor_proof(
                self.c,proposed["anchor"]["id"],"bad-signature","participant2@demo.ru"
            )
        signature=_sign(private,proposed["proof"])
        proved=federated_trust.verify_anchor_proof(
            self.c,proposed["anchor"]["id"],signature,"participant2@demo.ru"
        )
        self.assertEqual(proved["status"],"pending_governance")
        with self.assertRaisesRegex(ValueError,"federated_anchor_governance_required"):
            federated_trust.activate_anchor(
                self.c,proposed["anchor"]["id"],"participant2@demo.ru"
            )

    def test_did_and_jwks_publish_promomed_hosted_identity_without_accreditation_claim(self):
        did=federated_trust.did_document(self.c,"INST-FED-VERIFY")
        self.assertEqual(
            did["id"],"did:web:trust.example.test:trust:INST-FED-VERIFY"
        )
        self.assertEqual(len(did["assertionMethod"]),1)
        self.assertFalse(did["promomed"]["externalDomainControlInferred"])
        self.assertFalse(did["promomed"]["professionalAccreditation"])

        jwks=federated_trust.jwks_document(self.c,"INST-FED-VERIFY")
        self.assertEqual(jwks["keys"][0]["kty"],"OKP")
        self.assertEqual(jwks["keys"][0]["crv"],"Ed25519")
        self.assertEqual(jwks["keys"][0]["alg"],"EdDSA")
        self.assertEqual(jwks["keys"][0]["promomedStatus"],"active")
        self.assertFalse(jwks["truthBoundary"]["professionalAccreditation"])

    def test_rotation_retires_old_anchor_and_keeps_historical_verifiability(self):
        verified_at=int(time.time())
        old_body,old_signature=self._receipt(
            self.anchor1,self.private1,verified_at=verified_at
        )
        private2,public2=_keypair()
        anchor2=self._admit_anchor(
            private2,public2,"federated-key-v2",self.anchor1["id"]
        )
        old=federated_trust._safe_anchor(
            federated_trust._anchor_row(self.c,self.anchor1["id"])
        )
        self.assertEqual(old["status"],"retired")
        self.assertEqual(anchor2["status"],"active")
        self.assertEqual(anchor2["rotatedFromAnchorId"],self.anchor1["id"])

        admitted=federated_trust.submit_signed_verification_receipt(
            self.c,self.bundle["id"],"INST-FED-VERIFY",self.anchor1["id"],
            old_body,old_signature,"participant2@demo.ru",
        )
        self.assertEqual(admitted["verificationStatus"],"VALID_TRUST_BUNDLE")

        did=federated_trust.did_document(self.c,"INST-FED-VERIFY")
        self.assertEqual(len(did["verificationMethod"]),2)
        self.assertEqual(len(did["assertionMethod"]),1)
        self.assertTrue(did["assertionMethod"][0].endswith("#federated-key-v2"))

    def test_suspended_anchor_requires_explicit_rotation_link(self):
        federated_trust.suspend_anchor(
            self.c,self.anchor1["id"],"Synthetic suspension","governance@demo.ru"
        )
        private2,public2=_keypair()
        with self.assertRaisesRegex(ValueError,"federated_anchor_rotation_link_required"):
            federated_trust.propose_anchor(
                self.c,"INST-FED-VERIFY","urn:synthetic:verifier","replacement",
                public2,"participant2@demo.ru",demo_only=True
            )
        proposed=federated_trust.propose_anchor(
            self.c,"INST-FED-VERIFY","urn:synthetic:verifier","replacement",
            public2,"participant2@demo.ru",rotated_from_anchor_id=self.anchor1["id"],
            demo_only=True
        )
        proof=_sign(private2,proposed["proof"])
        federated_trust.verify_anchor_proof(
            self.c,proposed["anchor"]["id"],proof,"participant2@demo.ru"
        )
        replacement=federated_trust.activate_anchor(
            self.c,proposed["anchor"]["id"],"governance@demo.ru"
        )
        prior=federated_trust._safe_anchor(
            federated_trust._anchor_row(self.c,self.anchor1["id"])
        )
        self.assertEqual(prior["status"],"retired")
        self.assertEqual(replacement["status"],"active")

    def test_active_institution_signed_receipt_is_reproducible_and_non_authoritative(self):
        before=syndication_network.qualification_snapshot(
            self.c,"INST-FED-SUBJECT"
        )["qualification"]["status"]
        body,signature=self._receipt(self.anchor1,self.private1)
        admitted=federated_trust.submit_signed_verification_receipt(
            self.c,self.bundle["id"],"INST-FED-VERIFY",self.anchor1["id"],
            body,signature,"participant2@demo.ru",
        )
        self.assertEqual(admitted["verificationStatus"],"VALID_TRUST_BUNDLE")
        replay=federated_trust.submit_signed_verification_receipt(
            self.c,self.bundle["id"],"INST-FED-VERIFY",self.anchor1["id"],
            body,signature,"participant2@demo.ru",
        )
        self.assertTrue(replay["idempotentReplay"])

        after=syndication_network.qualification_snapshot(
            self.c,"INST-FED-SUBJECT"
        )["qualification"]["status"]
        self.assertEqual(before,after)
        self.assertFalse(admitted["authorityBoundary"]["changesPartnerQualification"])
        self.assertFalse(admitted["authorityBoundary"]["externalEndorsementInferred"])

    def test_receipt_result_or_bundle_binding_cannot_be_forged(self):
        body,signature=self._receipt(self.anchor1,self.private1)
        tampered=dict(body)
        tampered["verificationStatus"]="REVOKED_SNAPSHOT"
        forged=_sign(self.private1,tampered)
        with self.assertRaisesRegex(ValueError,"institution_signed_receipt_result_mismatch"):
            federated_trust.submit_signed_verification_receipt(
                self.c,self.bundle["id"],"INST-FED-VERIFY",self.anchor1["id"],
                tampered,forged,"participant2@demo.ru"
            )

        tampered2=dict(body)
        tampered2["bundleSha256"]="0"*64
        forged2=_sign(self.private1,tampered2)
        with self.assertRaisesRegex(ValueError,"institution_signed_receipt_bundle_hash_mismatch"):
            federated_trust.submit_signed_verification_receipt(
                self.c,self.bundle["id"],"INST-FED-VERIFY",self.anchor1["id"],
                tampered2,forged2,"participant2@demo.ru"
            )

    def test_suspended_or_revoked_anchor_cannot_admit_new_receipt(self):
        body,signature=self._receipt(self.anchor1,self.private1)
        federated_trust.suspend_anchor(
            self.c,self.anchor1["id"],"Synthetic suspension","governance@demo.ru"
        )
        with self.assertRaisesRegex(ValueError,"federated_anchor_not_usable_for_receipt"):
            federated_trust.submit_signed_verification_receipt(
                self.c,self.bundle["id"],"INST-FED-VERIFY",self.anchor1["id"],
                body,signature,"participant2@demo.ru"
            )

    def test_offline_chain_verifies_promomed_anchor_status_and_institution_receipt(self):
        body,signature=self._receipt(self.anchor1,self.private1)
        admitted=federated_trust.submit_signed_verification_receipt(
            self.c,self.bundle["id"],"INST-FED-VERIFY",self.anchor1["id"],
            body,signature,"participant2@demo.ru"
        )
        receipt=federated_trust.signed_receipt_document(self.c,admitted["id"])
        anchor_status=federated_trust.signed_anchor_status(
            self.c,"INST-FED-VERIFY","governance@demo.ru"
        )
        issuer=evidence_checkpoint.issuer_document(self.c)
        bundle_doc=trust_bundle.bundle_document(self.c,self.bundle["id"])
        with patch.dict(os.environ,{},clear=False):
            os.environ.pop("PROMOMED_EVIDENCE_SIGNING_PRIVATE_KEY_B64",None)
            result=federated_trust.verify_signed_receipt_portable(
                receipt,bundle_doc["bundle"],anchor_status,issuer
            )
        self.assertEqual(result["status"],"VALID_INSTITUTION_SIGNED_RECEIPT")
        self.assertTrue(result["signatureValid"])
        self.assertFalse(result["externalEndorsementInferred"])
        self.assertFalse(result["professionalAccreditation"])
        self.assertFalse(result["medicalEfficacyCertified"])

    def test_fresh_anchor_revocation_invalidates_offline_current_trust(self):
        body,signature=self._receipt(self.anchor1,self.private1)
        admitted=federated_trust.submit_signed_verification_receipt(
            self.c,self.bundle["id"],"INST-FED-VERIFY",self.anchor1["id"],
            body,signature,"participant2@demo.ru"
        )
        receipt=federated_trust.signed_receipt_document(self.c,admitted["id"])
        federated_trust.revoke_anchor(
            self.c,self.anchor1["id"],"Synthetic key compromise","governance@demo.ru"
        )
        anchor_status=federated_trust.signed_anchor_status(
            self.c,"INST-FED-VERIFY","governance@demo.ru"
        )
        issuer=evidence_checkpoint.issuer_document(self.c)
        bundle_doc=trust_bundle.bundle_document(self.c,self.bundle["id"])
        result=federated_trust.verify_signed_receipt_portable(
            receipt,bundle_doc["bundle"],anchor_status,issuer
        )
        self.assertEqual(result["status"],"ANCHOR_NOT_TRUSTED")
        self.assertEqual(result["anchorStatus"],"revoked")

    def test_anchor_and_signed_receipt_audit_rows_are_immutable(self):
        body,signature=self._receipt(self.anchor1,self.private1)
        admitted=federated_trust.submit_signed_verification_receipt(
            self.c,self.bundle["id"],"INST-FED-VERIFY",self.anchor1["id"],
            body,signature,"participant2@demo.ru"
        )
        self.c.commit()
        with self.assertRaises(Exception):
            self.c.execute(
                "UPDATE institutional_federated_anchors SET key_id='bad' WHERE id=?",
                (self.anchor1["id"],),
            )
        self.c.rollback()
        with self.assertRaises(Exception):
            self.c.execute(
                "DELETE FROM institutional_signed_verification_receipts WHERE id=?",
                (admitted["id"],),
            )
        self.c.rollback()


if __name__=="__main__":
    unittest.main()
