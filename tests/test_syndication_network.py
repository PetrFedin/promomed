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
    change_impact,
    evidence_checkpoint,
    evidence_graph,
    evidence_interchange,
    reviewer_authority,
    syndication_network,
)
from app.auth import seed_demo_accounts


def _key_b64():
    private=Ed25519PrivateKey.generate()
    raw=private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


class CertifiedSyndicationNetworkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(
            os.environ,
            {
                "SQLITE_PATH":str(Path(self.tmp.name)/"syndication.db"),
                "PROMOMED_SEED_DEMO":"true",
                "PROMOMED_EVIDENCE_ISSUER_ID":"promomed-syndication-test",
                "PROMOMED_EVIDENCE_KEY_ID":"syndication-key-v1",
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
        evidence_graph.seed_demo(self.c)
        reviewer_authority.seed_demo(self.c)
        reviewer_id=self.c.execute(
            "SELECT id FROM reviewer_profiles WHERE account_email='reviewer@demo.ru'"
        ).fetchone()["id"]
        now=int(time.time())
        self.c.execute(
            """INSERT OR IGNORE INTO reviewer_scopes(
                 id,reviewer_id,scope_key,status,verified_by,verified_at,demo_only
               ) VALUES(?,?,?,'active','governance@demo.ru',?,1)""",
            (
                "scope:"+reviewer_id+":"+syndication_network.SCIENTIFIC_SCOPE,
                reviewer_id,
                syndication_network.SCIENTIFIC_SCOPE,
                now,
            ),
        )
        self._register_org()

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.tmp.cleanup()

    def _register_org(self):
        evidence_interchange.register_organization(
            self.c,
            organization_id="INST-SYND-001",
            name="Synthetic Scientific Society",
            organization_type="scientific_society",
            actor="governance@demo.ru",
            external_ref="urn:synthetic:society:001",
            credential_source="synthetic test fixture",
            demo_only=True,
        )
        for role in ("consumer","contributor"):
            evidence_interchange.bind_role(
                self.c,
                organization_id="INST-SYND-001",
                role_scope=role,
                actor="governance@demo.ru",
                verification_ref="synthetic-role-proof",
                demo_only=True,
            )
        syndication_network.bind_member(
            self.c,
            "INST-SYND-001",
            "participant@demo.ru",
            "contributor",
            "governance@demo.ru",
            "synthetic-membership-proof",
            demo_only=True,
        )
        syndication_network.bind_member(
            self.c,
            "INST-SYND-001",
            "participant@demo.ru",
            "operator",
            "governance@demo.ru",
            "synthetic-membership-proof",
            demo_only=True,
        )

    def _qualify(self,validity_seconds=864000):
        snapshot=syndication_network.start_qualification(
            self.c,
            "INST-SYND-001",
            "governance@demo.ru",
            validity_seconds=validity_seconds,
            demo_only=True,
        )
        qid=snapshot["qualification"]["id"]
        for scope in syndication_network.REQUIRED_CONFORMANCE_SCOPES:
            syndication_network.record_conformance(
                self.c,
                qid,
                scope,
                "passed",
                "governance@demo.ru",
                "urn:test:conformance:"+scope,
                "Synthetic conformance proof.",
            )
        return syndication_network.finalize_qualification(
            self.c,qid,"governance@demo.ru",validity_seconds=validity_seconds
        )

    def _subscription(self,withdrawal_sla=3600):
        self._qualify()
        return syndication_network.create_subscription(
            self.c,
            "INST-SYND-001",
            "artifact",
            "content:CT01",
            "governance@demo.ru",
            update_sla_seconds=3600,
            withdrawal_sla_seconds=withdrawal_sla,
        )

    def _package_delivery(self):
        evidence_checkpoint.issue(self.c,"content","CT01")
        package=evidence_interchange.create_package(
            self.c,artifact_kind="content",artifact_ref="CT01",actor="governance@demo.ru"
        )
        delivery=evidence_interchange.deliver_package(
            self.c,
            package_id=package["id"],
            organization_id="INST-SYND-001",
            actor="governance@demo.ru",
            delivery_role="consumer",
        )
        return package,delivery

    def test_qualification_requires_core_conformance_and_is_process_only(self):
        snapshot=syndication_network.start_qualification(
            self.c,"INST-SYND-001","governance@demo.ru",demo_only=True
        )
        qid=snapshot["qualification"]["id"]
        syndication_network.record_conformance(
            self.c,qid,"evidence_api_integration","passed",
            "governance@demo.ru","urn:test:evidence-api"
        )
        with self.assertRaisesRegex(ValueError,"required_conformance_not_passed"):
            syndication_network.finalize_qualification(
                self.c,qid,"governance@demo.ru"
            )
        for scope in ("withdrawal_propagation","disclosure_workflow"):
            syndication_network.record_conformance(
                self.c,qid,scope,"passed","governance@demo.ru","urn:test:"+scope
            )
        qualified=syndication_network.finalize_qualification(
            self.c,qid,"governance@demo.ru"
        )
        self.assertEqual(qualified["qualification"]["status"],"qualified")
        self.assertTrue(qualified["truthBoundary"]["technicalProcessCertificationOnly"])
        self.assertFalse(qualified["truthBoundary"]["medicalEfficacyCertified"])

    def test_public_certification_is_process_only_and_privacy_minimised(self):
        self._qualify()
        public=syndication_network.public_certification(self.c,"INST-SYND-001")
        self.assertEqual(public["qualificationStatus"],"qualified")
        self.assertTrue(public["truthBoundary"]["technicalProcessCertificationOnly"])
        self.assertFalse(public["truthBoundary"]["medicalEfficacyCertified"])
        text=str(public)
        self.assertNotIn("checkedBy",text)
        self.assertNotIn("evidenceRef",text)
        self.assertNotIn("governance@demo.ru",text)

    def test_requalification_due_blocks_certified_subscription_matching(self):
        self._subscription()
        q=self.c.execute(
            """SELECT id FROM syndication_partner_qualifications
               WHERE organization_id='INST-SYND-001' ORDER BY created_at DESC,id DESC LIMIT 1"""
        ).fetchone()
        self.c.execute(
            "UPDATE syndication_partner_qualifications SET next_requalification_at=? WHERE id=?",
            (int(time.time())-1,q["id"]),
        )
        matched=syndication_network.matching_subscription(
            self.c,"INST-SYND-001","content","CT01"
        )
        self.assertIsNone(matched)
        state=syndication_network.qualification_snapshot(self.c,"INST-SYND-001")
        self.assertEqual(state["qualification"]["status"],"requalification_due")

    def test_contribution_requires_verified_membership_and_cannot_self_review(self):
        self._qualify()
        with self.assertRaisesRegex(ValueError,"institutional_contributor_membership_required"):
            syndication_network.submit_contribution(
                self.c,"INST-SYND-001","source_recommendation","Unverified submitter",
                {"source_ref":"urn:test:source"},"client@demo.ru"
            )
        contribution=syndication_network.submit_contribution(
            self.c,"INST-SYND-001","source_recommendation","Synthetic source recommendation",
            {"source_ref":"urn:test:source","note":"test only"},"participant@demo.ru"
        )
        with self.assertRaisesRegex(ValueError,"contribution_self_review_forbidden"):
            syndication_network.review_contribution(
                self.c,contribution["id"],"editorial","participant@demo.ru",
                "accept","Should not pass."
            )

    def test_two_authority_reviews_then_governance_signed_receipt_without_canonical_mutation(self):
        self._qualify()
        before=self.c.execute("SELECT COUNT(*) n FROM evidence_claims").fetchone()["n"]
        contribution=syndication_network.submit_contribution(
            self.c,
            "INST-SYND-001",
            "correction_notice",
            "Synthetic correction notice",
            {"artifact_kind":"content","artifact_ref":"CT01","reason":"test-only notice"},
            "participant@demo.ru",
        )
        editorial=syndication_network.review_contribution(
            self.c,contribution["id"],"editorial","editor@demo.ru",
            "accept","Editorially admissible for scientific review.","none"
        )
        self.assertEqual(editorial["status"],"scientific_review")
        scientific=syndication_network.review_contribution(
            self.c,contribution["id"],"scientific","reviewer@demo.ru",
            "accept","Synthetic scientific review acceptance.","none"
        )
        self.assertEqual(scientific["status"],"review_ready")

        admitted=syndication_network.admit_contribution(
            self.c,contribution["id"],"governance@demo.ru"
        )
        after=self.c.execute("SELECT COUNT(*) n FROM evidence_claims").fetchone()["n"]
        self.assertEqual(before,after)
        self.assertFalse(admitted["canonicalMutation"])

        document=syndication_network.contribution_receipt(self.c,contribution["id"])
        self.assertEqual(document["admittedByRole"],"governance")
        self.assertNotIn("admittedBy",document)
        issuer=evidence_checkpoint.issuer_document(self.c)
        with patch.dict(os.environ,{},clear=False):
            os.environ.pop("PROMOMED_EVIDENCE_SIGNING_PRIVATE_KEY_B64",None)
            verified=syndication_network.verify_contribution_receipt(document,issuer)
        self.assertEqual(verified["status"],"VALID_CONTRIBUTION_ADMISSION_RECEIPT")
        self.assertTrue(verified["signature_valid"])
        self.assertFalse(verified["canonicalMutation"])
        self.assertFalse(verified["medicalEfficacyCertified"])

    def test_request_changes_creates_new_immutable_contribution_revision(self):
        self._qualify()
        original=syndication_network.submit_contribution(
            self.c,"INST-SYND-001","programme_material","Synthetic programme material",
            {"version":1,"body":"draft"},"participant@demo.ru"
        )
        review=syndication_network.review_contribution(
            self.c,original["id"],"editorial","editor@demo.ru",
            "request_changes","Add source attribution.","none"
        )
        self.assertEqual(review["status"],"changes_requested")

        revised=syndication_network.revise_contribution(
            self.c,original["id"],"Synthetic programme material",
            {"version":2,"body":"draft","source_ref":"urn:test:source"},
            "participant@demo.ru"
        )
        self.assertNotEqual(revised["id"],original["id"])
        self.assertEqual(revised["supersedesContributionId"],original["id"])
        old=self.c.execute(
            "SELECT status,payload_sha256 FROM external_contributions WHERE id=?",
            (original["id"],),
        ).fetchone()
        new=self.c.execute(
            "SELECT status,supersedes_contribution_id,payload_sha256 FROM external_contributions WHERE id=?",
            (revised["id"],),
        ).fetchone()
        self.assertEqual(old["status"],"changes_requested")
        self.assertEqual(new["status"],"submitted")
        self.assertEqual(new["supersedes_contribution_id"],original["id"])
        self.assertNotEqual(old["payload_sha256"],new["payload_sha256"])

    def test_conflict_and_separation_of_duties_block_admission(self):
        self._qualify()
        contribution=syndication_network.submit_contribution(
            self.c,"INST-SYND-001","review_input","Synthetic review input",
            {"note":"test"},"participant@demo.ru"
        )
        with self.assertRaisesRegex(ValueError,"contribution_conflict_blocks_acceptance"):
            syndication_network.review_contribution(
                self.c,contribution["id"],"editorial","editor@demo.ru",
                "accept","Conflicted.","material"
            )

    def test_withdrawal_creates_sla_obligation_and_late_ack_is_breach(self):
        self._subscription(withdrawal_sla=3600)
        package,delivery=self._package_delivery()
        change_impact.analyze_source_change(
            self.c,"ES01","source_retracted",
            "Synthetic downstream withdrawal test","editor@demo.ru"
        )
        obligation=self.c.execute(
            """SELECT id,status,due_at FROM syndication_delivery_obligations
               WHERE delivery_id=? AND obligation_type='withdrawal'""",
            (delivery["id"],),
        ).fetchone()
        self.assertIsNotNone(obligation)
        self.assertEqual(obligation["status"],"pending")

        self.c.execute(
            "UPDATE syndication_delivery_obligations SET due_at=? WHERE id=?",
            (int(time.time())-1,obligation["id"]),
        )
        result=syndication_network.acknowledge_obligation(
            self.c,obligation["id"],"INST-SYND-001",
            "urn:test:withdrawal-ack",actor="participant@demo.ru"
        )
        self.assertEqual(result["status"],"breached")

    def test_breached_obligation_can_still_record_late_ack_evidence(self):
        self._subscription(withdrawal_sla=3600)
        package,delivery=self._package_delivery()
        change_impact.analyze_source_change(
            self.c,"ES01","source_retracted",
            "Synthetic overdue acknowledgement test","editor@demo.ru"
        )
        obligation=self.c.execute(
            """SELECT id FROM syndication_delivery_obligations
               WHERE delivery_id=? AND obligation_type='withdrawal'""",
            (delivery["id"],),
        ).fetchone()
        self.c.execute(
            "UPDATE syndication_delivery_obligations SET due_at=? WHERE id=?",
            (int(time.time())-1,obligation["id"]),
        )
        syndication_network.mark_overdue_obligations(self.c)
        marked=self.c.execute(
            "SELECT status,acknowledged_at FROM syndication_delivery_obligations WHERE id=?",
            (obligation["id"],),
        ).fetchone()
        self.assertEqual(marked["status"],"breached")
        self.assertIsNone(marked["acknowledged_at"])

        late=syndication_network.acknowledge_obligation(
            self.c,obligation["id"],"INST-SYND-001",
            "urn:test:late-withdrawal-ack",actor="participant@demo.ru"
        )
        self.assertEqual(late["status"],"breached")
        self.assertIsNotNone(late["acknowledged_at"])
        self.assertEqual(late["evidence_ref"],"urn:test:late-withdrawal-ack")

    def test_revocation_does_not_erase_withdrawal_obligation_for_prior_delivery(self):
        self._subscription(withdrawal_sla=3600)
        package,delivery=self._package_delivery()
        syndication_network.revoke_qualification(
            self.c,"INST-SYND-001","Post-delivery revocation test","governance@demo.ru"
        )
        change_impact.analyze_source_change(
            self.c,"ES01","source_retracted",
            "Synthetic retraction after partner revocation","editor@demo.ru"
        )
        obligation=self.c.execute(
            """SELECT status FROM syndication_delivery_obligations
               WHERE delivery_id=? AND obligation_type='withdrawal'""",
            (delivery["id"],),
        ).fetchone()
        self.assertIsNotNone(obligation)
        self.assertEqual(obligation["status"],"pending")

    def test_revocation_stops_subscription_and_new_contributions(self):
        self._subscription()
        revoked=syndication_network.revoke_qualification(
            self.c,"INST-SYND-001","Conformance revoked in test","governance@demo.ru"
        )
        self.assertEqual(revoked["qualification"]["status"],"revoked")
        subscription=self.c.execute(
            "SELECT status FROM syndication_subscriptions WHERE organization_id='INST-SYND-001'"
        ).fetchone()
        self.assertEqual(subscription["status"],"revoked")
        with self.assertRaisesRegex(ValueError,"qualification_revoked_reinstatement_required"):
            syndication_network.start_qualification(
                self.c,"INST-SYND-001","governance@demo.ru",demo_only=True
            )
        with self.assertRaisesRegex(ValueError,"syndication_partner_not_qualified"):
            syndication_network.submit_contribution(
                self.c,"INST-SYND-001","institutional_metadata","Blocked after revoke",
                {"name":"test"},"participant@demo.ru"
            )


if __name__=="__main__":
    unittest.main()
