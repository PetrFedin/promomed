import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import client365


class Client365EvidenceTests(unittest.TestCase):
    NOW=1900000000
    EMAIL="account@test.invalid"
    OTHER="other@test.invalid"

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "SQLITE_PATH":str(Path(self.temp.name)/"client365.db"),
            "DATABASE_URL":"",
            "PROMOMED_SEED_DEMO":"false",
        })
        self.env.start()
        from app import db
        importlib.reload(db)
        self.db=db
        self.c=db.connect()
        db.migrate(self.c)
        for email in (self.EMAIL,self.OTHER):
            self.c.execute(
                "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
                "VALUES(?,?,'participant','Fixture','active',?,?)",
                (email,"fixture-only",self.NOW-40*86400,self.NOW-40*86400),
            )
        self.c.commit()

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.temp.cleanup()

    def register(self,days_ago=35,email=None):
        email=email or self.EMAIL
        self.c.execute(
            "INSERT INTO registrations(email,status,ts) VALUES(?,'confirmed',?)",
            (email,self.NOW-days_ago*86400),
        )

    def action(self,when,kind="replay_opened",email=None):
        self.c.execute(
            "INSERT INTO events(kind,actor,payload,ts) VALUES(?,?,?,?)",
            (kind,email or self.EMAIL,'{"secret":"NOT FOR PUBLIC PROJECTION"}',when),
        )

    def snapshot(self,email=None):
        self.c.commit()
        return client365.snapshot(self.c,email or self.EMAIL,now=self.NOW)

    def test_no_baseline_means_no_retention_inference(self):
        self.c.execute(
            "INSERT INTO followups(email,day,track,status,ts) VALUES(?,30,'sleep','active',?)",
            (self.EMAIL,self.NOW),
        )
        self.c.execute(
            "INSERT INTO learning_enrollments(email,track_id,status,current_step,started,updated) "
            "VALUES(?,'LT-MISSING','completed',1,?,?)",
            (self.EMAIL,self.NOW-40*86400,self.NOW-35*86400),
        )
        d=self.snapshot()
        self.assertIsNone(d["registeredAt"])
        self.assertTrue(all(x["state"]=="no_registration_baseline" for x in d["milestones"]))
        self.assertTrue(all(x["isEvidenceOfReturn"] is False for x in d["followups"]))
        self.assertIsNone(d["truthBoundary"]["cohortRetentionRate"])
        self.assertIsNone(d["truthBoundary"]["recognizedRevenue"])

    def test_d7_d30_are_observed_actions_after_true_elapsed_time(self):
        self.register(days_ago=35)
        base=self.NOW-35*86400
        self.action(base+3*86400)
        d=self.snapshot()
        self.assertEqual([m["state"] for m in d["milestones"]],
                         ["observed_account_activity","no_observed_account_activity",
                          "no_observed_account_activity"])
        self.action(base+8*86400,kind="learning_advanced")
        d=self.snapshot()
        self.assertEqual([m["state"] for m in d["milestones"]],
                         ["observed_account_activity","observed_account_activity",
                          "no_observed_account_activity"])
        self.action(base+31*86400,kind="discovery_saved")
        d=self.snapshot()
        self.assertEqual([m["state"] for m in d["milestones"]],
                         ["observed_account_activity","observed_account_activity",
                          "observed_account_activity"])
        self.assertEqual(d["milestones"][2]["recordedActionCount"],1)
        self.assertFalse(d["milestones"][2]["externallyVerifiedRetention"])
        self.assertFalse(d["truthBoundary"]["externalAcceptance"])
        self.assertNotIn("NOT FOR PUBLIC PROJECTION",str(d))

    def test_not_due_is_not_mistaken_for_no_return(self):
        self.register(days_ago=3)
        self.action(self.NOW-86400)
        d=self.snapshot()
        self.assertEqual([m["state"] for m in d["milestones"]],
                         ["observed_account_activity","not_due","not_due"])
        self.assertEqual(d["milestones"][2]["recordedActionCount"],0)

    def test_personal_history_scoped_and_provenance_separated(self):
        self.register()
        self.register(email=self.OTHER)
        when=self.NOW-86400
        self.action(when,email=self.EMAIL)
        self.action(when,email=self.OTHER)
        self.c.execute(
            "INSERT INTO takeaways(email,session_id,note,source,ts) VALUES(?,?,?,?,?)",
            (self.EMAIL,"P01","private participant note","session",when),
        )
        self.c.execute(
            "INSERT INTO takeaways(email,session_id,note,source,ts) VALUES(?,?,?,?,?)",
            (self.OTHER,"P02","OTHER PRIVATE NOTE","session",when),
        )
        self.c.execute(
            "INSERT INTO session_attendance(email,item_id,status,checkin_ts,checkout_ts,source) "
            "VALUES(?,'P01','present',?,NULL,'participant')",
            (self.EMAIL,when),
        )
        self.c.execute(
            "INSERT INTO session_attendance(email,item_id,status,checkin_ts,checkout_ts,source) "
            "VALUES(?,'P02','completed',?,?,'staff')",
            (self.EMAIL,when,when+15),
        )
        d=self.snapshot()
        self.assertEqual(d["counts"]["selfRecordedAttendance"],1)
        self.assertEqual(d["counts"]["staffRecordedAttendance"],1)
        self.assertEqual(d["counts"]["savedTakeaways"],1)
        self.assertEqual(d["counts"]["recordedAccountActions"],1)
        self.assertNotIn("OTHER PRIVATE NOTE",str(d))
        self.assertNotIn("private participant note",str(d))
        event_types={x["assurance"] for x in d["events"]}
        self.assertIn("self_recorded_not_verified",event_types)
        self.assertIn("staff_recorded_not_independently_verified",event_types)
        self.assertFalse(d["truthBoundary"]["selfCheckinIsNotVerifiedAttendance"] is False)

    def test_no_future_or_missing_timestamps_counted(self):
        self.register(days_ago=35)
        self.action(self.NOW+1000)
        self.action(0)
        d=self.snapshot()
        self.assertEqual(d["counts"]["recordedAccountActions"],0)
        self.assertEqual(d["milestones"][2]["state"],"no_observed_account_activity")

    def test_http_role_identity_and_account_revocation(self):
        self.register()
        self.c.commit()
        user=("participant","Fixture",self.EMAIL)
        _,status=client365.read(self.c,None,"/api/client-365")
        self.assertEqual(status,401)
        _,status=client365.read(self.c,("organizer","Fixture",self.EMAIL),"/api/client-365")
        self.assertEqual(status,403)
        _,status=client365.read(self.c,user,"/api/client-365?email="+self.OTHER)
        self.assertEqual(status,422)
        d,status=client365.read(self.c,user,"/api/client-365")
        self.assertEqual(status,200)
        self.assertFalse(d["demoOnly"])
        self.c.execute("UPDATE accounts SET status='suspended' WHERE email=?",(self.EMAIL,))
        _,status=client365.read(self.c,user,"/api/client-365")
        self.assertEqual(status,403)
        self.c.execute("UPDATE accounts SET status='active',role='partner' WHERE email=?",(self.EMAIL,))
        _,status=client365.read(self.c,user,"/api/client-365")
        self.assertEqual(status,403)


if __name__=="__main__":
    unittest.main()
