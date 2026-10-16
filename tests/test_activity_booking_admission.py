"""SEC-11: activity booking requires exact admitted event version."""
import importlib
import os
import tempfile
import time
import unittest
from pathlib import Path

from app import programme_commands, public_state
from app.auth import hash_password


class ActivityBookingAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=__import__("unittest").mock.patch.dict(os.environ,{
            "SQLITE_PATH":str(Path(self.temp.name)/"activity.db"),
            "DATABASE_URL":"",
            "PROMOMED_SEED_DEMO":"false",
            "PROMOMED_REQUIRE_POSTGRES":"false",
        })
        self.env.start()
        from app import db
        importlib.reload(db)
        importlib.reload(public_state)
        importlib.reload(programme_commands)
        self.db=db
        self.c=db.connect()
        db.migrate(self.c)
        self.now=int(time.time())
        self.users=("a@example.test","b@example.test")
        for email in self.users:
            self.c.execute(
                "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
                "VALUES(?,?,'participant',?,'active',?,?)",
                (email,hash_password("StrongActivity!42"),email,self.now,self.now),
            )
        self.c.execute(
            'INSERT INTO program_items(id,start,"end",venue,track,format,title,audience,capacity,stream,replay,partner) '
            "VALUES('P1','10:00','11:00','Hall A','Science','talk','Admitted session','all',1,1,1,'')"
        )
        self.c.commit()

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.temp.cleanup()

    def row(self):
        return self.c.execute(
            'SELECT id,start,"end",venue,track,format,title,audience,capacity,stream,replay,partner '
            "FROM program_items WHERE id='P1'"
        ).fetchone()

    def admit(self):
        digest=public_state.payload_sha256("event",self.row())
        self.c.execute(
            "INSERT INTO public_artifact_admissions("
            "artifact_kind,artifact_ref,payload_sha256,status,reviewer_ref,source_ref,admitted_at,demo_only"
            ") VALUES('event','P1',?,'admitted','review:test','source:test',?,0)",
            (digest,self.now),
        )
        self.c.commit()
        return digest

    def command(self,email,action):
        out=programme_commands.handle_command(
            self.c,"/api/activity-booking","participant",email,
            {"item_id":"P1","action":action},
        )
        self.c.commit()
        return out

    def status(self,email):
        row=self.c.execute(
            "SELECT status FROM activity_bookings WHERE email=? AND item_id='P1'",
            (email,),
        ).fetchone()
        return row["status"] if row else None

    def test_missing_unadmitted_held_and_hash_stale_share_same_404(self):
        for stage in ("unadmitted","held","hash_stale"):
            if stage=="held":
                self.admit()
                self.c.execute(
                    "INSERT INTO publication_holds("
                    "id,event_id,artifact_kind,artifact_ref,reason,status,placed_at,placed_by,demo_only"
                    ") VALUES('H1','EV','event','P1','hold','active',?,'gov',0)",
                    (self.now,),
                )
                self.c.commit()
            elif stage=="hash_stale":
                self.c.execute("DELETE FROM publication_holds")
                self.c.execute("DELETE FROM public_artifact_admissions")
                self.c.commit()
                self.admit()
                self.c.execute("UPDATE program_items SET title='Changed' WHERE id='P1'")
                self.c.commit()
            out=self.command(self.users[0],"book")
            self.assertEqual(out.status,404,stage)
            self.assertEqual(out.payload,{"error":"program_item_not_found"},stage)
            self.assertIsNone(self.status(self.users[0]))
            self.c.execute("DELETE FROM publication_holds")
            self.c.execute("DELETE FROM public_artifact_admissions")
            self.c.execute("UPDATE program_items SET title='Admitted session' WHERE id='P1'")
            self.c.commit()

    def test_exact_admission_allows_book_then_waitlist(self):
        self.admit()
        first=self.command(self.users[0],"book")
        second=self.command(self.users[1],"book")
        self.assertEqual(first.status,200)
        self.assertEqual(second.status,200)
        self.assertEqual(self.status(self.users[0]),"booked")
        self.assertEqual(self.status(self.users[1]),"waitlist")

    def test_owner_can_cancel_after_withdrawal_without_waitlist_promotion(self):
        digest=self.admit()
        self.command(self.users[0],"book")
        self.command(self.users[1],"book")
        self.c.execute(
            "UPDATE public_artifact_admissions SET status='withdrawn',withdrawn_at=? "
            "WHERE artifact_kind='event' AND artifact_ref='P1' AND payload_sha256=?",
            (self.now+1,digest),
        )
        self.c.commit()
        cancelled=self.command(self.users[0],"cancel")
        self.assertEqual(cancelled.status,200)
        self.assertIsNone(self.status(self.users[0]))
        self.assertEqual(self.status(self.users[1]),"waitlist")

    def test_admitted_cancel_promotes_oldest_waitlist(self):
        self.admit()
        self.command(self.users[0],"book")
        self.command(self.users[1],"book")
        cancelled=self.command(self.users[0],"cancel")
        self.assertEqual(cancelled.status,200)
        self.assertEqual(self.status(self.users[1]),"booked")

    def test_repeated_active_booking_is_idempotent(self):
        self.admit()
        self.command(self.users[0],"book")
        ts=self.c.execute(
            "SELECT ts FROM activity_bookings WHERE email=? AND item_id='P1'",
            (self.users[0],),
        ).fetchone()["ts"]
        self.command(self.users[0],"book")
        after=self.c.execute(
            "SELECT ts FROM activity_bookings WHERE email=? AND item_id='P1'",
            (self.users[0],),
        ).fetchone()["ts"]
        self.assertEqual(ts,after)

    def test_bad_action_is_rejected(self):
        self.admit()
        out=programme_commands.handle_command(
            self.c,"/api/activity-booking","participant",self.users[0],
            {"item_id":"P1","action":"promote"},
        )
        self.assertEqual((out.status,out.payload["error"]),(400,"bad_action"))


if __name__=="__main__":
    unittest.main()
