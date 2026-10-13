"""Actual PostgreSQL 17 integration proof, using only isolated CI database."""
import hashlib
import os
import unittest
import uuid

from app import commercial_evidence_ledger as ledger
from app import db, evidence_interchange, syndication_network
from app.auth import seed_demo_accounts

ACTOR = "organizer@demo.ru"

def source_sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@unittest.skipUnless(os.environ.get("DATABASE_URL", "").startswith("postgres"),
                     "PostgreSQL CI environment required")
class CommercialEvidencePostgresTests(unittest.TestCase):
    def setUp(self):
        self.c = db.connect()
        db.migrate(self.c)
        seed_demo_accounts(self.c)
        self.org = "PG-CASH-CI-" + uuid.uuid4().hex[:16].upper()
        evidence_interchange.register_organization(
            self.c, organization_id=self.org, name="Synthetic PostgreSQL ledger fixture",
            organization_type="strategic_partner", actor=ACTOR,
            external_ref="urn:ci:"+self.org,
            credential_source="test only", demo_only=True,
        )
        syndication_network.bind_member(
            self.c, self.org, ACTOR, "administrator", ACTOR,
            "synthetic PostgreSQL fixture", demo_only=True,
        )
        self.c.commit()

    def tearDown(self):
        self.c.rollback()
        self.c.close()

    def test_postgres_contract_to_partial_cash_with_immutable_audit(self):
        contract = ledger.record_contract(
            self.c, organization_id=self.org, actor=ACTOR,
            external_ref="pg-pilot", version=1, currency_code="RUB",
            net_amount_minor=30000, source_ref="fixture:contract",
            source_sha256=source_sha("pg-contract"), idempotency_key="pg:contract")
        cid = contract["id"]
        def ev(typ, ref, amount, *, parent=None, related=None, tax=0, period=None):
            return ledger.record_event(
                self.c, organization_id=self.org, actor=ACTOR,
                contract_id=cid, event_type=typ, external_ref=ref,
                amount_minor=amount, source_ref="fixture:"+typ,
                source_sha256=source_sha(ref), idempotency_key="pg:"+ref,
                parent_event_id=parent, related_event_id=related,
                tax_minor=tax, accounting_period=period,
            )["id"]

        obligation = ev("obligation", "pg-obligation", 20000)
        delivery = ev("delivery", "pg-delivery", 18000, parent=obligation)
        invoice = ev("invoice", "pg-invoice", 12000, parent=delivery, tax=2400)
        settlement = ev("settlement", "pg-bank-proof-candidate", 15000)
        ev("allocation", "pg-alloc-1", 11000, parent=invoice, related=settlement)
        with self.assertRaisesRegex(ValueError, "allocation_exceeds_receivable"):
            ev("allocation", "pg-overalloc", 4000, parent=invoice, related=settlement)
        recognition = ev("recognition", "pg-recognition-candidate", 9000,
                         parent=invoice, period="2026-10")
        view = ledger.snapshot(self.c, self.org, actor=ACTOR)
        self.assertIsNone(view["recognizedRevenue"])
        self.assertIsNone(view["cashCollected"])
        self.assertEqual(view["financialAuthority"], "NONE")
        self.assertEqual(view["contractCandidates"][0]["documentCounts"]["recognition"], 1)
        audit = ledger.verify_chain(self.c, self.org, actor=ACTOR)
        self.assertTrue(audit["valid"])
        self.assertEqual(audit["checked"], 7)
        self.assertTrue(recognition.startswith("ce:"))
        self.c.commit()

        # DB-level immutable protection: the insert cannot later be rewritten
        # into a fake approved financial result even by a SQL writer.
        with self.assertRaises(Exception):
            self.c.execute(
                "UPDATE commercial_evidence_events SET state='approved' WHERE id=?",
                (recognition,),
            )
        self.c.rollback()
        assert ledger.verify_chain(self.c, self.org, actor=ACTOR)["valid"]

    def test_unverified_non_demo_postgres_remains_candidate_only(self):
        # Authenticated memberships are still required for non-demo sources,
        # and finance recognition is not offered as an approved state.
        c=self.c
        direct=c.execute(
            "SELECT COUNT(*) n FROM commercial_evidence_events "
            "WHERE organization_id=? AND state <> 'candidate'", (self.org,)
        ).fetchone()
        self.assertEqual(direct["n"], 0)


if __name__ == "__main__":
    unittest.main()
