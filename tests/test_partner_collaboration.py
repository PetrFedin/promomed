import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import importlib
from app import partner_collaboration as pc

class PartnerCollaborationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.patcher=patch.dict(os.environ,{"SQLITE_PATH":str(Path(self.temp.name)/"collab.db"),"PROMOMED_SEED_DEMO":"false"},clear=False)
        self.patcher.start()
        from app import db
        importlib.reload(db)
        self.db=db
        self.c=db.connect()
        db.migrate(self.c)
    def tearDown(self):
        self.c.close();self.patcher.stop();self.temp.cleanup()
    def cmd(self,path,role,email,**kwargs):
        data={"operation_id":"op"+str(self.c.execute("SELECT COUNT(*) n FROM partner_collab_operations").fetchone()["n"]+1),**kwargs}
        out=pc.handle_command(self.c,path,role,email,data)
        if out.status<400:self.c.commit()
        else:self.c.rollback()
        return out
    def test_isolation_and_review(self):
        a=self.cmd("/api/partner-collaboration/create","partner","one@test.invalid",title="Studio partner experience",format="studio")
        self.assertEqual(a.status,201)
        pid=a.payload["project_id"]
        self.assertEqual(pc.snapshot(self.c,"partner","one@test.invalid")["projects"][0]["id"],pid)
        self.assertEqual(pc.snapshot(self.c,"partner","other@test.invalid")["projects"],[])
        with self.assertRaises(LookupError):pc.snapshot(self.c,"partner","other@test.invalid",pid)
        self.assertEqual(self.cmd("/api/partner-collaboration/task","partner","other@test.invalid",project_id=pid,title="steal",lane="partner").status,404)
        t=self.cmd("/api/partner-collaboration/task","partner","one@test.invalid",project_id=pid,title="Prepare schedule",lane="partner")
        self.assertEqual(t.status,201)
        self.assertEqual(len(pc.snapshot(self.c,"partner","one@test.invalid",pid)["tasks"]),1)
        self.assertEqual(self.cmd("/api/partner-collaboration/project","organizer","owner@test.invalid",project_id=pid,action="review",expected_version=1).status,409)
        self.assertEqual(self.cmd("/api/partner-collaboration/project","partner","one@test.invalid",project_id=pid,action="request_review",expected_version=1).status,200)
        self.assertEqual(self.cmd("/api/partner-collaboration/project","organizer","owner@test.invalid",project_id=pid,action="review",expected_version=1).status,409)
        self.assertEqual(self.cmd("/api/partner-collaboration/project","organizer","owner@test.invalid",project_id=pid,action="review",expected_version=2).status,200)
        self.assertEqual(pc.snapshot(self.c,"organizer","owner@test.invalid",pid)["project"]["status"],"internally_reviewed")
        self.assertFalse(pc.snapshot(self.c,"organizer","owner@test.invalid",pid)["contractAccepted"])
    def test_idempotent_replay_and_conflict(self):
        data={"operation_id":"my-unique-op","title":"Field experience","format":"event"}
        first=pc.handle_command(self.c,"/api/partner-collaboration/create","partner","one@test.invalid",data);self.c.commit()
        second=pc.handle_command(self.c,"/api/partner-collaboration/create","partner","one@test.invalid",data);self.c.commit()
        self.assertEqual(first.payload,second.payload)
        bad=pc.handle_command(self.c,"/api/partner-collaboration/create","partner","one@test.invalid",{**data,"title":"changed"})
        self.assertEqual(bad.status,409)
        self.assertEqual(self.c.execute("SELECT COUNT(*) n FROM partner_collab_projects").fetchone()["n"],1)
        with self.assertRaises(Exception):
            self.c.execute("DELETE FROM partner_collab_events WHERE project_id=?",(first.payload["project_id"],))
        self.c.rollback()
    def test_roles_and_validation(self):
        self.assertEqual(self.cmd("/api/partner-collaboration/create","participant","p@test.invalid",title="x",format="event").status,403)
        self.assertEqual(self.cmd("/api/partner-collaboration/create","organizer","o@test.invalid",title="x",format="event").status,403)
        self.assertEqual(self.cmd("/api/partner-collaboration/create","partner","p@test.invalid",title="",format="event").status,422)
        self.assertEqual(self.cmd("/api/partner-collaboration/create","partner","p@test.invalid",title="x",format="medicine").status,422)
        self.assertFalse(pc.snapshot(self.c,"organizer","o@test.invalid")["contractAccepted"])

if __name__=="__main__":unittest.main()
