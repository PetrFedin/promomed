"""Isolated candidate contract-to-cash integrity tests; no production access."""
import hashlib
import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import commercial_evidence_ledger as ledger, evidence_interchange, syndication_network
from app.auth import seed_demo_accounts

ACTOR = "organizer@demo.ru"
A = "LEDGER-DEMO-A"
B = "LEDGER-DEMO-B"


def source_hash(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class CommercialEvidenceLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "SQLITE_PATH": str(Path(self.tmp.name) / "ledger-test.db"),
            "DATABASE_URL": "",
            "PROMOMED_SEED_DEMO": "true",
        })
        self.env.start()
        import app.db as db
        importlib.reload(db)
        self.db = db
        self.c = db.connect()
        self.c.execute("PRAGMA foreign_keys = ON")
        db.migrate(self.c)
        seed_demo_accounts(self.c)
        for org in (A, B):
            evidence_interchange.register_organization(
                self.c, organization_id=org, name="Synthetic "+org,
                organization_type="strategic_partner",
                actor=ACTOR, external_ref="urn:synthetic:"+org,
                credential_source="synthetic fixture", demo_only=True,
            )
            syndication_network.bind_member(
                self.c, org, ACTOR, "administrator", ACTOR,
                "synthetic-fixture-membership", demo_only=True,
            )
        self.c.commit()

    def tearDown(self):
        self.c.rollback()
        self.c.close()
        self.env.stop()
        self.tmp.cleanup()

    def contract(self, *, org=A, external="pilot-1", version=1,
                 previous=None, amount=20000, currency="RUB", key=None):
        return ledger.record_contract(
            self.c, organization_id=org, actor=ACTOR,
            external_ref=external, version=version, currency_code=currency,
            net_amount_minor=amount, source_ref="fixture:contract",
            source_sha256=source_hash("contract-"+external+"-"+str(version)),
            idempotency_key=key or ("contract:"+external+":"+str(version)),
            previous_contract_id=previous,
        )

    def event(self, typ, contract, *, amount=1000, ext=None, version=1,
              parent=None, related=None, replace=None, tax=0, period=None,
              decision=None, org=A, key=None):
        ext = ext or typ+"-01"
        return ledger.record_event(
            self.c, organization_id=org, actor=ACTOR, contract_id=contract,
            event_type=typ, external_ref=ext, version=version,
            amount_minor=amount, tax_minor=tax,
            source_ref="fixture:"+typ, source_sha256=source_hash(typ+ext+str(version)),
            idempotency_key=key or "event:"+ext+":"+str(version),
            accounting_period=period, parent_event_id=parent,
            related_event_id=related, replaces_event_id=replace,
            decision=decision,
        )

    def pipeline(self):
        c = self.contract()["id"]
        o = self.event("obligation",c,amount=15000)["id"]
        d = self.event("delivery",c,amount=12000,parent=o)["id"]
        i = self.event("invoice",c,amount=7000,tax=1400,parent=d)["id"]
        return c,o,d,i

    def test_migrations_are_both_present_and_idempotent(self):
        status = self.db.migration_status(self.c)
        self.assertIn("026_commercial_evidence_ledger", status["applied"])
        self.assertTrue(status["schema_ready"], status)
        self.db.migrate(self.c)
        self.assertEqual(self.db.migration_status(self.c)["checksum_drift"], [])

    def test_contract_idempotency_and_revision(self):
        one = self.contract()
        self.assertTrue(one["created"])
        self.c.commit()
        same = self.contract()
        self.assertFalse(same["created"])
        self.assertEqual(same["id"], one["id"])
        with self.assertRaisesRegex(ValueError, "idempotency_conflict"):
            self.contract(amount=21000)
        with self.assertRaisesRegex(ValueError, "contract_revision_parent_required"):
            self.contract(version=2)
        two = self.contract(version=2,previous=one["id"])
        self.assertNotEqual(one["id"],two["id"])
        self.assertEqual(ledger.snapshot(self.c,A,actor=ACTOR)["auditLength"],2)

    def test_partial_invoice_credit_and_partial_payments(self):
        cid,_,_,invoice = self.pipeline()
        credit = self.event("credit_note",cid,amount=1000,tax=200,parent=invoice)
        self.assertEqual(credit["state"],"candidate")
        s1=self.event("settlement",cid,amount=5000,ext="deposit-1")["id"]
        s2=self.event("settlement",cid,amount=4000,ext="deposit-2")["id"]
        a1=self.event("allocation",cid,amount=4500,ext="allocation-1",parent=invoice,related=s1)
        a2=self.event("allocation",cid,amount=2700,ext="allocation-2",parent=invoice,related=s2)
        self.assertNotEqual(a1["id"],a2["id"])
        with self.assertRaisesRegex(ValueError, "allocation_exceeds_receivable"):
            self.event("allocation",cid,amount=1,ext="allocation-3",parent=invoice,related=s2)
        with self.assertRaisesRegex(ValueError, "credit_requires_cash_reallocation"):
            self.event("credit_note",cid,amount=1,ext="credit-extra",parent=invoice)
        refund=self.event("refund",cid,amount=1000,parent=s2)
        self.assertTrue(refund["created"])
        with self.assertRaisesRegex(ValueError, "refund_exceeds_unallocated_cash"):
            self.event("refund",cid,amount=1000,ext="refund-other",parent=s2)
        self.c.commit()
        out=ledger.snapshot(self.c,A,actor=ACTOR)
        self.assertEqual(out["contractCandidates"][0]["documentCounts"]["allocation"],2)
        self.assertIsNone(out["cashCollected"])
        self.assertEqual(out["financialAuthority"],"NONE")
        self.assertTrue(ledger.verify_chain(self.c,A,actor=ACTOR)["valid"])

    def test_recognition_is_only_candidate_and_finance_accept_is_forbidden(self):
        cid,_,_,invoice=self.pipeline()
        recognition=self.event("recognition",cid,amount=4000,
                               period="2026-10",parent=invoice)
        self.assertEqual(recognition["state"],"candidate")
        with self.assertRaisesRegex(ValueError,"finance_review_not_authority"):
            self.event("finance_review",cid,amount=0,parent=recognition["id"],
                       decision="approved")
        accepted=self.event("finance_review",cid,amount=0,parent=recognition["id"],
                            decision="hold")
        self.assertTrue(accepted["created"])
        with self.assertRaisesRegex(ValueError, "credit_requires_recognition_reversal"):
            self.event("credit_note",cid,amount=1,parent=invoice)
        view=ledger.snapshot(self.c,A,actor=ACTOR)
        self.assertIsNone(view["recognizedRevenue"])
        self.assertEqual(view["capitalAuthority"],"NONE")
        self.c.commit()

    def test_overbooking_and_false_parent_rejected(self):
        cid,ob,delivery,invoice=self.pipeline()
        with self.assertRaisesRegex(ValueError,"obligation_exceeds_contract"):
            self.event("obligation",cid,amount=6000,ext="overob")
        with self.assertRaisesRegex(ValueError,"delivery_exceeds_obligation"):
            self.event("delivery",cid,amount=4000,ext="overdelivery",parent=ob)
        with self.assertRaisesRegex(ValueError,"invoice_exceeds_delivery"):
            self.event("invoice",cid,amount=5001,ext="overinvoice",parent=delivery)
        with self.assertRaisesRegex(ValueError,"event_parent_type_invalid"):
            self.event("invoice",cid,amount=500,ext="wrongparent",parent=ob)
        with self.assertRaisesRegex(ValueError,"recognition_period_required"):
            self.event("recognition",cid,amount=100,parent=invoice)
        self.assertIsNone(ledger.snapshot(self.c,A,actor=ACTOR)["invoiced"])

    def test_revisions_only_before_downstream_and_no_duplicate_count(self):
        cid=self.contract()["id"]
        ob=self.event("obligation",cid,amount=1000)
        revised=self.event("obligation",cid,amount=1500,version=2,
                           ext="obligation-01",replace=ob["id"])
        self.assertNotEqual(ob["id"],revised["id"])
        d=self.event("delivery",cid,amount=1100,parent=revised["id"])
        self.assertEqual(
            ledger.snapshot(self.c,A,actor=ACTOR)["contractCandidates"][0]["documentCounts"]["obligation"],1
        )
        with self.assertRaisesRegex(ValueError,"revision_has_downstream_evidence"):
            self.event("obligation",cid,amount=1600,version=3,
                       ext="obligation-01",replace=revised["id"])
        with self.assertRaisesRegex(ValueError,"superseded_parent_invalid"):
            self.event("delivery",cid,amount=100,ext="old-delivery",parent=ob["id"])
        self.assertTrue(d["created"])

    def test_renewal_candidate_requires_prior_contract_and_recognition(self):
        old,_,_,invoice=self.pipeline()
        recognition=self.event("recognition",old,amount=1000,parent=invoice,period="2026-10")
        fresh=self.contract(external="renewal-period-2",previous=old)
        renewal=self.event("renewal",fresh["id"],amount=0,
                           related=recognition["id"])
        self.assertTrue(renewal["created"])
        self.assertIsNone(ledger.snapshot(self.c,A,actor=ACTOR)["renewals"])
        with self.assertRaisesRegex(ValueError,"renewal_previous_contract_required"):
            self.event("renewal",old,amount=0,related=recognition["id"],
                       ext="wrong-renewal")

    def test_candidate_allocation_correction_releases_capacity_without_mutation(self):
        cid,_,_,invoice=self.pipeline()
        settlement=self.event("settlement",cid,amount=8000,ext="correct-deposit")["id"]
        allocation=self.event("allocation",cid,amount=7000,ext="correct-alloc",parent=invoice,related=settlement)
        corrected=self.event("allocation",cid,amount=0,ext="correct-alloc",version=2,
                             parent=invoice,related=settlement,replace=allocation["id"])
        self.assertNotEqual(corrected["id"],allocation["id"])
        another=self.event("allocation",cid,amount=7000,ext="new-alloc",parent=invoice,related=settlement)
        self.assertTrue(another["created"])
        self.assertEqual(ledger.snapshot(self.c,A,actor=ACTOR)["contractCandidates"][0]["documentCounts"]["allocation"],2)
        self.assertTrue(ledger.verify_chain(self.c,A,actor=ACTOR)["valid"])

    def test_candidate_recognition_correction_releases_net_ceiling(self):
        cid,_,_,invoice=self.pipeline()
        old=self.event("recognition",cid,amount=7000,ext="rec-correction",parent=invoice,period="2026-10")
        self.event("recognition",cid,amount=0,ext="rec-correction",version=2,
                   parent=invoice,period="2026-10",replace=old["id"])
        new=self.event("recognition",cid,amount=7000,ext="new-rec",parent=invoice,period="2026-10")
        self.assertTrue(new["created"])
        self.assertIsNone(ledger.snapshot(self.c,A,actor=ACTOR)["recognizedRevenue"])

    def test_revisions_cannot_reassign_parent_or_recognition_period(self):
        cid,_,_,invoice=self.pipeline()
        settlement=self.event("settlement",cid,amount=8000,ext="lineage-settlement")["id"]
        orig=self.event("allocation",cid,amount=1000,ext="lineage-allocation",parent=invoice,related=settlement)
        another=self.event("settlement",cid,amount=2000,ext="another-settlement")["id"]
        with self.assertRaisesRegex(ValueError,"event_revision_lineage_mismatch"):
            self.event("allocation",cid,amount=0,ext="lineage-allocation",version=2,
                       parent=invoice,related=another,replace=orig["id"])
        recognition=self.event("recognition",cid,amount=1000,ext="lineage-rec",parent=invoice,period="2026-10")
        with self.assertRaisesRegex(ValueError,"event_revision_lineage_mismatch"):
            self.event("recognition",cid,amount=0,ext="lineage-rec",version=2,
                       parent=invoice,period="2026-11",replace=recognition["id"])

    def test_cross_tenant_cannot_read_or_reuse_parent(self):
        a=self.contract()
        b=self.contract(org=B,external="other-pilot")
        ob=self.event("obligation",a["id"])
        with self.assertRaisesRegex(ValueError,"contract_not_found"):
            self.event("obligation",a["id"],org=B,ext="foreign",amount=10)
        with self.assertRaisesRegex(ValueError,"event_not_found"):
            self.event("delivery",b["id"],org=B,parent=ob["id"],amount=10)
        self.assertEqual(ledger.snapshot(self.c,B,actor=ACTOR)["auditLength"],1)
        with self.assertRaisesRegex(ValueError,"organization_not_found"):
            ledger.snapshot(self.c,A,actor="unbound@example.test")

    def test_append_only_and_chain_verification(self):
        cid,_,_,_=self.pipeline()
        self.c.commit()
        valid=ledger.verify_chain(self.c,A,actor=ACTOR)
        self.assertTrue(valid["valid"])
        self.assertEqual(valid["checked"],4)
        with self.assertRaises(self.db.INTEGRITY_ERRORS):
            self.c.execute("UPDATE commercial_contract_versions SET net_amount_minor=999 WHERE id=?",(cid,))
        self.c.rollback()
        with self.assertRaises(self.db.INTEGRITY_ERRORS):
            self.c.execute("DELETE FROM commercial_evidence_events WHERE organization_id=?",(A,))
        self.c.rollback()
        with self.assertRaises(self.db.INTEGRITY_ERRORS):
            self.c.execute("DELETE FROM commercial_evidence_audit WHERE organization_id=?",(A,))
        self.c.rollback()
        self.assertTrue(ledger.verify_chain(self.c,A,actor=ACTOR)["valid"])

    def test_audit_detects_privileged_contract_amount_tampering(self):
        cid,_,_,_=self.pipeline()
        self.c.commit()
        self.assertTrue(ledger.verify_chain(self.c,A,actor=ACTOR)["valid"])
        self.c.execute("DROP TRIGGER commercial_contract_update_denied")
        self.c.execute(
            "UPDATE commercial_contract_versions SET net_amount_minor=? WHERE id=?",
            (999999,cid),
        )
        invalid=ledger.verify_chain(self.c,A,actor=ACTOR)
        self.assertFalse(invalid["valid"])
        self.assertEqual(invalid["reason"],"DOCUMENT_PAYLOAD_MISMATCH")
        self.c.rollback()
        self.assertTrue(ledger.verify_chain(self.c,A,actor=ACTOR)["valid"])

    def test_audit_detects_privileged_event_amount_tampering(self):
        cid,_,_,invoice=self.pipeline()
        self.c.commit()
        self.c.execute("DROP TRIGGER commercial_event_update_denied")
        self.c.execute(
            "UPDATE commercial_evidence_events SET amount_minor=1 WHERE id=?",
            (invoice,),
        )
        invalid=ledger.verify_chain(self.c,A,actor=ACTOR)
        self.assertFalse(invalid["valid"])
        self.assertEqual(invalid["reason"],"DOCUMENT_PAYLOAD_MISMATCH")
        self.c.rollback()
        self.assertTrue(ledger.verify_chain(self.c,A,actor=ACTOR)["valid"])

    def test_audit_detects_privileged_missing_suffix(self):
        self.pipeline()
        self.c.commit()
        self.c.execute("DROP TRIGGER commercial_audit_delete_denied")
        self.c.execute(
            "DELETE FROM commercial_evidence_audit WHERE organization_id=? AND entry_no=4",
            (A,),
        )
        invalid=ledger.verify_chain(self.c,A,actor=ACTOR)
        self.assertFalse(invalid["valid"])
        self.assertEqual(invalid["reason"],"AUDIT_COVERAGE_GAP")
        self.c.rollback()
        self.assertTrue(ledger.verify_chain(self.c,A,actor=ACTOR)["valid"])

    def test_audit_detects_idempotency_key_tampering(self):
        cid,_,_,_=self.pipeline()
        self.c.commit()
        self.c.execute("DROP TRIGGER commercial_contract_update_denied")
        self.c.execute(
            "UPDATE commercial_contract_versions SET idempotency_key=? WHERE id=?",
            ("altered-request-key",cid),
        )
        invalid=ledger.verify_chain(self.c,A,actor=ACTOR)
        self.assertEqual(invalid["reason"],"DOCUMENT_PAYLOAD_MISMATCH")
        self.c.rollback()
        self.assertTrue(ledger.verify_chain(self.c,A,actor=ACTOR)["valid"])

    def test_audit_detects_record_time_tampering(self):
        cid,_,_,_=self.pipeline()
        self.c.commit()
        self.c.execute("DROP TRIGGER commercial_event_update_denied")
        self.c.execute(
            "UPDATE commercial_evidence_events SET recorded_at=recorded_at+60 "
            "WHERE organization_id=? AND event_type='invoice'",
            (A,),
        )
        invalid=ledger.verify_chain(self.c,A,actor=ACTOR)
        self.assertEqual(invalid["reason"],"DOCUMENT_AUDIT_TIMESTAMP_MISMATCH")
        self.c.rollback()
        self.assertTrue(ledger.verify_chain(self.c,A,actor=ACTOR)["valid"])

    def test_non_demo_candidate_write_is_denied_in_sqlite(self):
        evidence_interchange.register_organization(
            self.c,organization_id="REAL-BOUNDARY",name="Non-demo fixture",
            organization_type="strategic_partner",actor=ACTOR,
            external_ref="urn:fixture:real",credential_source="test",demo_only=False)
        self.c.execute(
            """INSERT INTO institutional_memberships
            (id,organization_id,account_email,member_role,status,effective_at,
             expires_at,verified_by,verification_ref,demo_only)
            VALUES(?,?,?,'administrator','active',1,NULL,?,'fixture',0)""",
            ("test:member:real","REAL-BOUNDARY","trusted@example.test","fixture"),
        )
        with self.assertRaisesRegex(ValueError,"non_demo_candidate_requires_admitted_postgres"):
            ledger.record_contract(
                self.c, organization_id="REAL-BOUNDARY",actor="trusted@example.test",
                external_ref="real",version=1,currency_code="RUB",
                net_amount_minor=100,source_ref="fixture:doc",
                source_sha256=source_hash("non-demo"),idempotency_key="real-1")


if __name__ == "__main__":
    unittest.main()
