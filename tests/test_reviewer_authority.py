import os
import tempfile
import unittest
from pathlib import Path


class MedicalReviewerAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"]=str(Path(self.tmp.name)/"review-authority.db")
        os.environ["PROMOMED_SEED_DEMO"]="true"
        os.environ.pop("DATABASE_URL",None);os.environ.pop("PROMOMED_REQUIRE_POSTGRES",None)
        import importlib
        import app.db as db
        import app.evidence_monitor as monitor
        import app.reviewer_authority as authority
        import server
        importlib.reload(db);importlib.reload(monitor);importlib.reload(authority);importlib.reload(server)
        self.db=db;self.monitor=monitor;self.authority=authority;self.server=server
        self.server.init();self.c=self.server.conn()

    def tearDown(self):
        self.c.close();self.tmp.cleanup()

    def _production_candidate(self,suffix="authority"):
        doi="10.1000/"+suffix
        payload={"message":{"DOI":doi,"title":["Authority test"],"publisher":"Test Journal","issued":{"date-parts":[[2026,10,6]]},"update-to":[]}}
        r=self.monitor.ingest_payload(self.c,"crossref",doi,payload,"editor@demo.ru",0)
        self.monitor.review_candidate(self.c,r["candidate_id"],"editorial","editor@demo.ru","accept","Editorial acceptance.")
        return r["candidate_id"]

    def _promote_demo_reviewer_to_verified(self):
        self.c.execute(
            "UPDATE reviewer_profiles SET credential_state='verified',independent_attested=1,demo_only=0 WHERE account_email='reviewer@demo.ru'"
        )
        self.c.execute(
            "UPDATE reviewer_scopes SET demo_only=0 WHERE reviewer_id='REV-DEMO-MEDICAL'"
        )

    def test_assignment_requires_editorial_acceptance_first(self):
        doi="10.1000/editorial-first"
        payload={"message":{"DOI":doi,"title":["Editorial first"],"publisher":"Test Journal","issued":{"date-parts":[[2026,10,6]]},"update-to":[]}}
        r=self.monitor.ingest_payload(self.c,"crossref",doi,payload,"editor@demo.ru",0)
        self._promote_demo_reviewer_to_verified()
        with self.assertRaisesRegex(ValueError,"editorial_review_required_before_assignment"):
            self.authority.assign_candidate(self.c,r["candidate_id"],"reviewer@demo.ru","editor@demo.ru")

    def test_production_scientific_review_cannot_use_editor_shortcut(self):
        cid=self._production_candidate("no-shortcut")
        with self.assertRaisesRegex(ValueError,"scientific_review_authority_required"):
            self.monitor.review_candidate(self.c,cid,"scientific","editor@demo.ru","accept","")

    def test_verified_reviewer_conflict_decision_and_governance_admission(self):
        cid=self._production_candidate("governed")
        self._promote_demo_reviewer_to_verified()
        assignment=self.authority.assign_candidate(self.c,cid,"reviewer@demo.ru","editor@demo.ru")
        self.authority.declare_conflict(self.c,assignment,"reviewer@demo.ru","none","No conflict identified.")
        decision=self.authority.submit_decision(self.c,assignment,"reviewer@demo.ru","accept","Evidence metadata reviewed.")
        self.assertEqual(len(decision["decision_digest"]),64)
        with self.assertRaisesRegex(ValueError,"governance_admission_required"):
            self.monitor.admit_candidate(self.c,cid,"editor@demo.ru")
        admitted=self.monitor.admit_candidate(self.c,cid,"governance@demo.ru")
        self.assertTrue(admitted["source_id"])
        row=self.c.execute("SELECT status,admitted_by FROM evidence_admission_candidates WHERE id=?",(cid,)).fetchone()
        self.assertEqual(row["status"],"admitted")
        self.assertEqual(row["admitted_by"],"governance@demo.ru")
        monitor=self.monitor.snapshot(self.c)
        self.assertGreaterEqual(monitor["summary"]["admitted_candidates"],1)
        self.assertTrue(monitor["truth_boundary"]["reviewer_authority_present"])
        self.assertFalse(monitor["truth_boundary"]["independent_scientific_reviewer"])
        self.assertTrue(self.authority.verify_event_chain(self.c))

    def test_material_conflict_blocks_scientific_decision(self):
        cid=self._production_candidate("conflict")
        self._promote_demo_reviewer_to_verified()
        assignment=self.authority.assign_candidate(self.c,cid,"reviewer@demo.ru","editor@demo.ru")
        self.authority.declare_conflict(self.c,assignment,"reviewer@demo.ru","material","Prior direct involvement.")
        with self.assertRaisesRegex(ValueError,"assignment_not_active"):
            self.authority.submit_decision(self.c,assignment,"reviewer@demo.ru","accept","Should not pass.")

    def test_potential_conflict_blocks_scientific_decision(self):
        cid=self._production_candidate("potential-conflict")
        self._promote_demo_reviewer_to_verified()
        assignment=self.authority.assign_candidate(self.c,cid,"reviewer@demo.ru","editor@demo.ru")
        self.authority.declare_conflict(self.c,assignment,"reviewer@demo.ru","potential","Potential institutional overlap.")
        row=self.c.execute("SELECT status FROM review_assignments WHERE id=?",(assignment,)).fetchone()
        self.assertEqual(row["status"],"conflict_hold")
        with self.assertRaisesRegex(ValueError,"assignment_not_active"):
            self.authority.submit_decision(self.c,assignment,"reviewer@demo.ru","accept","Should not pass.")
        with self.assertRaisesRegex(ValueError,"reviewer_conflict_history_blocks_reassignment"):
            self.authority.assign_candidate(self.c,cid,"reviewer@demo.ru","editor@demo.ru")

    def test_editor_cannot_be_assigned_as_scientific_reviewer(self):
        cid=self._production_candidate("editor-blocked")
        with self.assertRaisesRegex(ValueError,"reviewer_identity_not_authorized"):
            self.authority.assign_candidate(self.c,cid,"editor@demo.ru","governance@demo.ru")

    def test_decision_and_event_tables_are_db_immutable(self):
        cid=self._production_candidate("immutable")
        self._promote_demo_reviewer_to_verified()
        assignment=self.authority.assign_candidate(self.c,cid,"reviewer@demo.ru","editor@demo.ru")
        self.authority.declare_conflict(self.c,assignment,"reviewer@demo.ru","none","No conflict.")
        decision=self.authority.submit_decision(self.c,assignment,"reviewer@demo.ru","accept","Accepted.")
        self.c.commit()
        with self.assertRaises(Exception):
            self.c.execute("UPDATE review_decisions SET rationale='mutated' WHERE id=?",(decision["decision_id"],))
        self.c.rollback()
        self.assertTrue(self.authority.verify_event_chain(self.c))

    def test_schema_rejects_invalid_review_decision_state(self):
        with self.assertRaises(self.db.INTEGRITY_ERRORS):
            self.c.execute(
                "INSERT INTO review_decisions(id,assignment_id,candidate_id,reviewer_id,decision,rationale,evidence_snapshot_hash,attestation_method,decision_digest,signed_at,demo_only) "
                "VALUES('bad','missing','missing','missing','override','x','h','x','d',1,1)"
            )
        self.c.rollback()

    def test_demo_profile_is_explicitly_not_independent_verified(self):
        d=self.authority.snapshot(self.c)
        p=next(x for x in d["profiles"] if x["account_email"]=="reviewer@demo.ru")
        self.assertEqual(p["credential_state"],"demo_attested")
        self.assertEqual(p["independent_attested"],0)
        self.assertFalse(d["truth_boundary"]["credential_registry_integration"])
        self.assertFalse(d["truth_boundary"]["legal_e_signature"])


if __name__=="__main__":unittest.main()
