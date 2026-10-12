"""Execution proof on the existing ephemeral PostgreSQL 17 CI service."""
import secrets
import unittest
from app import db, partner_collaboration as pc

C="/api/partner-collaboration/create"
T="/api/partner-collaboration/task"
P="/api/partner-collaboration/project"
E="/api/partner-collaboration/execute"


class PostgresPartnerTaskContract(unittest.TestCase):
    def test_postgres_workflow_rollback_and_immutable_receipt(self):
        if db.backend_name()!="postgres":
            self.skipTest("PostgreSQL CI job only")
        c=db.connect()
        try:
            db.migrate(c)
            status=db.migration_status(c)
            self.assertIn("027_partner_task_execution",status["applied"])
            owner="ci-"+secrets.token_hex(8)+"@example.test"
            organizer="ci-organizer-"+secrets.token_hex(8)+"@example.test"
            n=iter(range(1,99))
            def send(route,role,email,**data):
                v=pc.handle_command(c,route,role,email,
                    {"operation_id":"proof-"+str(next(n)),**data})
                self.assertLess(v.status,400,v.payload)
                return v.payload
            pid=send(C,"partner",owner,title="Temporary test project",format="studio")["project_id"]
            tid=send(T,"partner",owner,project_id=pid,title="Temporary check",lane="partner")["task_id"]
            send(P,"partner",owner,project_id=pid,action="request_review",expected_version=1)
            send(P,"organizer",organizer,project_id=pid,action="review",expected_version=2)
            send(E,"partner",owner,project_id=pid,task_id=tid,action="start",expected_version=1)
            send(E,"partner",owner,project_id=pid,task_id=tid,action="submit",
                expected_version=2,evidence_ref="demo:ci-postgres",
                evidence_sha256="b"*64)
            accepted=send(E,"organizer",organizer,project_id=pid,task_id=tid,
                action="accept",expected_version=3,decision_note="Internal QA")
            self.assertEqual(accepted["status"],"accepted")
            self.assertFalse(accepted["contractAccepted"])
            receipt=c.execute("SELECT actor_role,next_status,evidence_ref_sha256 FROM partner_collab_task_receipts WHERE id=?",
                              (accepted["receipt_id"],)).fetchone()
            self.assertEqual(receipt["actor_role"],"organizer")
            self.assertEqual(receipt["next_status"],"accepted")
            self.assertEqual(receipt["evidence_ref_sha256"],"b"*64)
            with self.assertRaises(Exception):
                # SAVEPOINT permits transaction recovery after the expected trigger rejection.
                c.execute("SAVEPOINT immutable_receipt_probe")
                c.execute("DELETE FROM partner_collab_task_receipts WHERE id=?",
                          (accepted["receipt_id"],))
            c.execute("ROLLBACK TO SAVEPOINT immutable_receipt_probe")
            c.execute("RELEASE SAVEPOINT immutable_receipt_probe")
        finally:
            c.rollback()
            c.close()


if __name__=="__main__":
    unittest.main()
