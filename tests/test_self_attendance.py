"""SEC-11: participant self-attendance is a self-report, never verified attendance."""
import time
import unittest
import uuid

from app import client365, db, my_workspace, programme_commands, public_state
from app.auth import hash_password


class SelfAttendanceV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.migrate()

    def setUp(self):
        suffix=uuid.uuid4().hex[:10]
        self.item_id="SELF-"+suffix
        self.email="self-"+suffix+"@example.test"
        self.other="other-"+suffix+"@example.test"
        self.now=int(time.time())
        self.c=db.connect()
        for email in (self.email,self.other):
            self.c.execute(
                "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
                "VALUES(?,?,'participant',?,'active',?,?)",
                (email,hash_password("StrongSelfAttendance!42"),email,self.now,self.now),
            )
        self.c.execute(
            'INSERT INTO program_items(id,start,"end",venue,track,format,title,audience,capacity,stream,replay,partner) '
            "VALUES(?,?,?,?,?,?,?,?,5,1,1,'Partner X')",
            (
                self.item_id,"12:00","12:45","Hall S","Science","talk",
                "Self-report session","all",
            ),
        )
        row=self.item()
        digest=public_state.payload_sha256("event",row)
        self.digest=digest
        self.c.execute(
            "INSERT INTO public_artifact_admissions("
            "artifact_kind,artifact_ref,payload_sha256,status,reviewer_ref,source_ref,"
            "admitted_at,demo_only) VALUES('event',?,?,'admitted','review:self','source:self',?,0)",
            (self.item_id,digest,self.now),
        )
        self.c.execute(
            "INSERT INTO activity_bookings(email,item_id,status,ts) VALUES(?,?,'booked',?)",
            (self.email,self.item_id,self.now),
        )
        self.c.commit()

    def tearDown(self):
        try:
            self.c.rollback()
            self.c.execute("DELETE FROM partner_engagement WHERE email IN (?,?)",(self.email,self.other))
            self.c.execute("DELETE FROM session_attendance WHERE email IN (?,?)",(self.email,self.other))
            self.c.execute("DELETE FROM activity_bookings WHERE email IN (?,?)",(self.email,self.other))
            self.c.execute(
                "DELETE FROM public_artifact_admissions "
                "WHERE artifact_kind='event' AND artifact_ref=?",(self.item_id,)
            )
            self.c.execute("DELETE FROM publication_holds WHERE artifact_ref=?",(self.item_id,))
            self.c.execute("DELETE FROM program_items WHERE id=?",(self.item_id,))
            self.c.execute("DELETE FROM auth_sessions WHERE email IN (?,?)",(self.email,self.other))
            self.c.execute("DELETE FROM accounts WHERE email IN (?,?)",(self.email,self.other))
            self.c.commit()
        finally:
            self.c.close()

    def item(self):
        return self.c.execute(
            'SELECT id,start,"end",venue,track,format,title,audience,capacity,stream,replay,partner '
            "FROM program_items WHERE id=?",(self.item_id,)
        ).fetchone()

    def command(self,email,action,extra=None,role="participant"):
        data={"item_id":self.item_id,"action":action}
        if extra:
            data.update(extra)
        out=programme_commands.handle_command(
            self.c,"/api/self-attendance/v1",role,email,data
        )
        self.c.commit()
        return out

    def test_arrive_is_self_report_and_does_not_enter_attendance_kpi(self):
        out=self.command(self.email,"arrive")
        self.assertEqual(out.status,201)
        self.assertFalse(out.payload["verifiedAttendance"])
        self.assertFalse(out.payload["countsAsAttendanceKpi"])
        row=self.c.execute(
            "SELECT status,source FROM session_attendance WHERE email=? AND item_id=?",
            (self.email,self.item_id),
        ).fetchone()
        self.assertEqual(dict(row),{
            "status":"self_reported",
            "source":"participant_self_report",
        })
        kpi=self.c.execute(
            "SELECT COUNT(*) n FROM session_attendance "
            "WHERE item_id=? AND status IN ('present','completed')",
            (self.item_id,),
        ).fetchone()["n"]
        self.assertEqual(int(kpi),0)
        partner=self.c.execute(
            "SELECT COUNT(*) n FROM partner_engagement WHERE email=? AND ref_id=?",
            (self.email,self.item_id),
        ).fetchone()["n"]
        self.assertEqual(int(partner),0)

        c365=client365.snapshot(self.c,self.email,now=self.now+1)
        self.assertEqual(c365["counts"]["selfRecordedAttendance"],0)
        self.assertTrue(c365["truthBoundary"]["selfCheckinIsNotVerifiedAttendance"])

        workspace,status=my_workspace.read(
            self.c,my_workspace.READ_ROUTE,"participant",self.email
        )
        self.assertEqual(status,200)
        own=[x for x in workspace["selfAttendance"] if x["item_id"]==self.item_id]
        self.assertEqual(len(own),1)
        self.assertEqual(own[0]["status"],"self_reported")
        self.assertFalse(workspace["truthBoundary"]["selfAttendanceIsVerifiedAttendance"])
        self.assertFalse(workspace["truthBoundary"]["selfAttendanceCountsAsAttendanceKpi"])

    def test_arrive_requires_exact_admission_and_confirmed_activity_booking(self):
        self.c.execute(
            "UPDATE activity_bookings SET status='waitlist' WHERE email=? AND item_id=?",
            (self.email,self.item_id),
        )
        self.c.commit()
        out=self.command(self.email,"arrive")
        self.assertEqual((out.status,out.payload["error"]),(409,"confirmed_booking_required"))

        self.c.execute(
            "UPDATE activity_bookings SET status='booked' WHERE email=? AND item_id=?",
            (self.email,self.item_id),
        )
        self.c.execute(
            "UPDATE public_artifact_admissions SET status='withdrawn',withdrawn_at=? "
            "WHERE artifact_kind='event' AND artifact_ref=?",
            (self.now+1,self.item_id),
        )
        self.c.commit()
        out=self.command(self.email,"arrive")
        self.assertEqual(out.status,404)
        self.assertEqual(out.payload,{"error":"program_item_not_found"})

    def test_leave_after_withdrawal_is_owner_control_and_idempotent(self):
        first=self.command(self.email,"arrive")
        self.assertEqual(first.status,201)
        self.c.execute(
            "UPDATE public_artifact_admissions SET status='withdrawn',withdrawn_at=? "
            "WHERE artifact_kind='event' AND artifact_ref=?",
            (self.now+1,self.item_id),
        )
        self.c.commit()
        left=self.command(self.email,"leave")
        self.assertEqual(left.status,200)
        self.assertEqual(left.payload["selfAttendance"]["status"],"self_reported_complete")
        self.assertFalse(left.payload["verifiedAttendance"])
        replay=self.command(self.email,"leave")
        self.assertEqual(replay.status,200)
        self.assertTrue(replay.payload["replayed"])

    def test_participant_cannot_overwrite_staff_or_organizer_record(self):
        self.c.execute(
            "INSERT INTO session_attendance("
            "email,item_id,status,checkin_ts,checkout_ts,source"
            ") VALUES(?,?,'present',?,NULL,'staff')",
            (self.email,self.item_id,self.now),
        )
        self.c.commit()
        out=self.command(self.email,"arrive")
        self.assertEqual((out.status,out.payload["error"]),(409,"attendance_record_conflict"))
        row=self.c.execute(
            "SELECT status,source FROM session_attendance WHERE email=? AND item_id=?",
            (self.email,self.item_id),
        ).fetchone()
        self.assertEqual(dict(row),{"status":"present","source":"staff"})

    def test_route_has_no_target_email_selector_and_is_participant_only(self):
        out=self.command(self.email,"arrive",extra={"email":self.other})
        self.assertEqual((out.status,out.payload["error"]),(422,"invalid_request"))
        out=self.command(self.email,"arrive",role="organizer")
        self.assertEqual((out.status,out.payload["error"]),(403,"forbidden"))

    def test_other_account_never_sees_owner_self_report(self):
        self.command(self.email,"arrive")
        workspace,status=my_workspace.read(
            self.c,my_workspace.READ_ROUTE,"participant",self.other
        )
        self.assertEqual(status,200)
        self.assertNotIn(self.email,str(workspace))
        self.assertEqual(workspace["selfAttendance"],[])


if __name__=="__main__":
    unittest.main()
