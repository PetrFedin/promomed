import os
import tempfile
import unittest
from pathlib import Path

class ReallocationApprovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"]=str(Path(self.tmp.name)/"realloc.db")
        os.environ["PROMOMED_SEED_DEMO"]="true"
        os.environ.pop("DATABASE_URL",None)
        os.environ.pop("PROMOMED_REQUIRE_POSTGRES",None)
        import importlib, app.db as db, app.reallocation_authority as ra, server
        importlib.reload(db);importlib.reload(ra);importlib.reload(server)
        self.ra=ra;self.server=server;self.server.init();self.c=self.server.conn()
    def tearDown(self):
        self.c.close();self.tmp.cleanup()
    def test_proposal_uses_4_5m_uncommitted_capacity(self):
        self.ra.create_demo_proposal(self.c,"sales@demo.ru");self.c.commit()
        d=self.ra.snapshot(self.c);p=d["proposal"]
        self.assertEqual(p["source_capacity_rub"],4_500_000)
        self.assertEqual(p["finance_target_rub"]+p["governance_target_rub"],4_500_000)
        self.assertFalse(d["capital_moved"])
    def test_all_three_roles_required_for_demo_preview(self):
        self.ra.create_demo_proposal(self.c,"sales@demo.ru")
        for role in ("Finance","Business Owner"):
            self.ra.accept_demo(self.c,role,"sales@demo.ru")
        self.c.commit();d=self.ra.snapshot(self.c)
        self.assertFalse(d["all_demo_approved"])
        self.ra.accept_demo(self.c,"Investment Committee","sales@demo.ru");self.c.commit()
        d=self.ra.snapshot(self.c)
        self.assertTrue(d["all_demo_approved"])
        self.assertEqual(d["proposal"]["status"],"approved_demo_preview")
        self.assertFalse(d["capital_moved"])
        self.assertFalse(d["truth_boundary"]["approved_reallocation"])
        self.assertFalse(d["truth_boundary"]["automatic_money_movement"])
if __name__=="__main__":unittest.main()
