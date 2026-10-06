import os
import tempfile
import unittest
from pathlib import Path

class Journey365Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"]=str(Path(self.tmp.name)/"journey365.db")
        os.environ["PROMOMED_SEED_DEMO"]="true"
        os.environ.pop("DATABASE_URL",None); os.environ.pop("PROMOMED_REQUIRE_POSTGRES",None)
        import importlib, app.db as db, app.journey365 as journey365, server
        importlib.reload(db); importlib.reload(journey365); importlib.reload(server)
        self.journey=journey365; self.server=server; self.server.init(); self.c=self.server.conn()
        self.email="participant@demo.ru"
    def tearDown(self):
        self.c.close(); self.tmp.cleanup()
    def test_default_journey_is_behavioural_not_medical(self):
        d=self.journey.snapshot(self.c,self.email)
        self.assertEqual(d["journey365_mode"],"derived_lifecycle_v1")
        self.assertEqual(len(d["journey365_stages"]),5)
        self.assertFalse(d["journey365_truth_boundary"]["medical_journey"])
        self.assertFalse(d["journey365_truth_boundary"]["diagnosis_or_treatment"])
    def test_learning_progress_moves_d7_complete(self):
        self.c.execute("INSERT INTO learning_enrollments(email,track_id,status,current_step,started,updated) VALUES(?,?,'active',1,1,1)",(self.email,"LT01"))
        self.c.commit()
        d=self.journey.snapshot(self.c,self.email)
        status={x["id"]:x["status"] for x in d["journey365_stages"]}
        self.assertEqual(status["d7"],"complete")
        self.assertGreaterEqual(d["journey365_progress_pct"],20)
    def test_attendance_moves_event_stage(self):
        self.c.execute("INSERT INTO session_attendance(email,item_id,status,checkin_ts,checkout_ts,source) VALUES(?,?,'attended',1,2,'demo')",(self.email,"P21"))
        self.c.commit()
        d=self.journey.snapshot(self.c,self.email)
        status={x["id"]:x["status"] for x in d["journey365_stages"]}
        self.assertEqual(status["event"],"complete")
    def test_progress_is_monotonic_by_completed_stage_count(self):
        a=self.journey.snapshot(self.c,self.email)["journey365_progress_pct"]
        self.c.execute("INSERT INTO topic_subscriptions(email,topic,status,ts) VALUES(?,?,'active',1)",(self.email,"Метаболическое здоровье"))
        self.c.commit()
        b=self.journey.snapshot(self.c,self.email)["journey365_progress_pct"]
        self.assertGreaterEqual(b,a)

if __name__=="__main__": unittest.main()
