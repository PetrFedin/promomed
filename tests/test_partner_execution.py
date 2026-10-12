"""Zero-network, zero-paid verification of partner task execution authority."""
import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import partner_collaboration as collaboration


CREATE="/api/partner-collaboration/create"
TASK="/api/partner-collaboration/task"
PROJECT="/api/partner-collaboration/project"
EXEC="/api/partner-collaboration/execute"
DIGEST="a"*64


class PartnerExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.patcher=patch.dict(os.environ,{
            "SQLITE_PATH":str(Path(self.temp.name)/"task-execution.sqlite"),
            "DATABASE_URL":"",
            "PROMOMED_SEED_DEMO":"false",
            "PROMOMED_REQUIRE_POSTGRES":"false",
        })
        self.patcher.start()
        from app import db
        importlib.reload(db)
        self.c=db.connect()
        db.migrate(self.c)
        self.counter=0

    def tearDown(self):
        self.c.close()
        self.patcher.stop()
        self.temp.cleanup()

    def command(self,route,role="partner",email="partner@test.invalid",
                op=None,commit=True,**payload):
        if not op:
            self.counter+=1
            op="task-op-"+str(self.counter)
        out=collaboration.handle_command(self.c,route,role,email,{
            "operation_id":op,**payload})
        if commit:
            if out.status<400:self.c.commit()
            else:self.c.rollback()
        return out

    def project_and_task(self,lane="partner"):
        created=self.command(CREATE,title="Studio governance plan",format="studio")
        self.assertEqual(created.status,201)
        pid=created.payload["project_id"]
        task=self.command(TASK,project_id=pid,title="Produce training card",
                          lane=lane)
        self.assertEqual(task.status,201)
        tid=task.payload["task_id"]
        return pid,tid

    def approve_project(self,pid):
        self.assertEqual(self.command(PROJECT,project_id=pid,
            action="request_review",expected_version=1).status,200)
        self.assertEqual(self.command(PROJECT,role="organizer",
            email="organizer@test.invalid",project_id=pid,
            action="review",expected_version=2).status,200)

    def do_task(self,pid,tid,action,version,role="partner",
                email="partner@test.invalid",**extra):
        return self.command(EXEC,role=role,email=email,project_id=pid,
            task_id=tid,action=action,expected_version=version,**extra)

    def test_two_party_task_delivery_and_immutable_receipts(self):
        pid,tid=self.project_and_task()
        first=self.do_task(pid,tid,"start",1)
        self.assertEqual(first.status,409)  # project not internally reviewed
        self.approve_project(pid)
        first=self.do_task(pid,tid,"start",1)
        self.assertEqual(first.status,200)
        self.assertEqual(first.payload["version"],2)
        self.assertFalse(first.payload["contractAccepted"])
        self.assertEqual(self.do_task(pid,tid,"submit",2).status,422)
        sub=self.do_task(pid,tid,"submit",2,
            evidence_ref="demo:studio-brief-v1",evidence_sha256=DIGEST)
        self.assertEqual(sub.payload["status"],"submitted")
        self.assertEqual(self.do_task(pid,tid,"accept",3).status,403)
        ok=self.do_task(pid,tid,"accept",3,role="organizer",
            email="organizer@test.invalid",decision_note="Reviewed demo content")
        self.assertEqual(ok.status,200)
        self.assertEqual(ok.payload["version"],4)
        self.assertFalse(ok.payload["artifactIntegrityIndependentlyVerified"])
        project=collaboration.snapshot(self.c,"partner","partner@test.invalid",pid)
        self.assertEqual(project["tasks"][0]["status"],"accepted")
        self.assertEqual(project["tasks"][0]["version"],4)
        self.assertEqual([x["action"] for x in project["receipts"]],
                         ["start","submit","accept"])
        self.assertEqual(project["receipts"][-1]["evidence_ref_sha256"],DIGEST)
        self.assertFalse(project["contractAccepted"])
        self.assertFalse(project["revenueClaimed"])
        for table in ("partner_collab_task_receipts",):
            with self.assertRaises(Exception):
                self.c.execute("DELETE FROM "+table)
            self.c.rollback()
            with self.assertRaises(Exception):
                self.c.execute("UPDATE "+table+" SET action='start'")
            self.c.rollback()
        self.assertEqual(self.do_task(pid,tid,"start",4).status,409)

    def test_rejection_and_resubmission_needs_new_digest(self):
        pid,tid=self.project_and_task()
        self.approve_project(pid)
        self.do_task(pid,tid,"start",1)
        self.do_task(pid,tid,"submit",2,
                     evidence_ref="demo:brief-v1",evidence_sha256=DIGEST)
        bad=self.do_task(pid,tid,"request_changes",3,role="organizer",
                         email="organizer@test.invalid")
        self.assertEqual(bad.status,422)
        change=self.do_task(pid,tid,"request_changes",3,
             role="organizer",email="organizer@test.invalid",
             decision_note="Revise scientific attribution")
        self.assertEqual(change.status,200)
        restarted=self.do_task(pid,tid,"start",4)
        self.assertEqual(restarted.payload["status"],"in_progress")
        state=collaboration.snapshot(self.c,"partner","partner@test.invalid",pid)
        self.assertIsNone(state["tasks"][0]["evidence_ref"])
        self.assertEqual(self.do_task(pid,tid,"submit",5).status,422)
        self.assertEqual(self.do_task(pid,tid,"submit",5,
             evidence_ref="demo:brief-v2",evidence_sha256="B"*64).status,200)

    def test_platform_lane_executed_by_organizer_reviewed_by_partner(self):
        pid,tid=self.project_and_task(lane="platform")
        self.approve_project(pid)
        self.assertEqual(self.do_task(pid,tid,"start",1).status,403)
        self.assertEqual(self.do_task(pid,tid,"start",1,
            role="organizer",email="organizer@test.invalid").status,200)
        self.assertEqual(self.do_task(pid,tid,"submit",2,
            role="organizer",email="organizer@test.invalid",
            evidence_ref="demo:platform-plan",evidence_sha256=DIGEST).status,200)
        self.assertEqual(self.do_task(pid,tid,"accept",3,
            role="organizer",email="organizer@test.invalid").status,403)
        self.assertEqual(self.do_task(pid,tid,"accept",3,
            role="partner",email="partner@test.invalid").status,200)

    def test_foreign_owner_and_untrusted_role_denied(self):
        pid,tid=self.project_and_task()
        self.approve_project(pid)
        before=self.c.execute("SELECT COUNT(*) n FROM partner_collab_task_receipts").fetchone()["n"]
        self.assertEqual(self.do_task(pid,tid,"start",1,
                         email="stranger@test.invalid").status,404)
        self.assertEqual(self.do_task(pid,tid,"start",1,
                         role="participant",email="p@test.invalid").status,403)
        self.assertEqual(self.do_task(pid,"unknown","start",1).status,404)
        self.assertEqual(self.c.execute(
             "SELECT COUNT(*) n FROM partner_collab_task_receipts").fetchone()["n"],before)

    def test_idempotent_no_duplicate_receipts_and_version_cas(self):
        pid,tid=self.project_and_task()
        self.approve_project(pid)
        payload={"project_id":pid,"task_id":tid,"action":"start","expected_version":1}
        a=self.command(EXEC,op="fixed-key",**payload)
        b=self.command(EXEC,op="fixed-key",**payload)
        self.assertEqual(a.payload,b.payload)
        self.assertEqual(a.status,b.status)
        self.assertEqual(self.command(EXEC,op="fixed-key",
             **{**payload,"expected_version":2}).status,409)
        self.assertEqual(self.command(EXEC,op="fresh-key",
             **payload).status,409)
        self.assertEqual(self.c.execute("SELECT COUNT(*) n FROM partner_collab_task_receipts").fetchone()["n"],1)

if __name__=="__main__":
    unittest.main()
