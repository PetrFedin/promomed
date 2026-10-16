"""PostgreSQL 17 concurrency proof for admitted activity booking."""
import os
import threading
import time
import unittest
import uuid

from app import db, programme_commands, public_state
from app.auth import hash_password


@unittest.skipUnless(
    os.environ.get("PROMOMED_ACTIVITY_BOOKING_PG_TEST") == "1",
    "dedicated PostgreSQL activity-booking qualification only",
)
class ActivityBookingPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if db.backend_name() != "postgres":
            raise RuntimeError("postgres_required")
        c=db.connect()
        try:
            db.migrate(c)
        finally:
            c.close()

    def setUp(self):
        suffix=uuid.uuid4().hex[:10]
        self.item_id="ACT-"+suffix
        self.users=(
            "act-a-"+suffix+"@example.test",
            "act-b-"+suffix+"@example.test",
        )
        now=int(time.time())
        c=db.connect()
        try:
            for email in self.users:
                c.execute(
                    "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
                    "VALUES(?,?,'participant',?,'active',?,?)",
                    (email,hash_password("StrongActivityPg!42"),email,now,now),
                )
            c.execute(
                'INSERT INTO program_items(id,start,"end",venue,track,format,title,audience,capacity,stream,replay,partner) '
                "VALUES(?,?,?,?,?,?,?,?,1,1,1,'')",
                (
                    self.item_id,"10:00","11:00","Hall A","Science","talk",
                    "Concurrent admitted session","all",
                ),
            )
            row=c.execute(
                'SELECT id,start,"end",venue,track,format,title,audience,capacity,stream,replay,partner '
                "FROM program_items WHERE id=?",(self.item_id,)
            ).fetchone()
            digest=public_state.payload_sha256("event",row)
            c.execute(
                "INSERT INTO public_artifact_admissions("
                "artifact_kind,artifact_ref,payload_sha256,status,reviewer_ref,source_ref,"
                "admitted_at,demo_only) VALUES('event',?,?,'admitted','review:pg','source:pg',?,0)",
                (self.item_id,digest,now),
            )
            c.commit()
        finally:
            c.close()

    def tearDown(self):
        c=db.connect()
        try:
            c.execute(
                "DELETE FROM activity_bookings WHERE item_id=?",(self.item_id,)
            )
            c.execute(
                "DELETE FROM public_artifact_admissions "
                "WHERE artifact_kind='event' AND artifact_ref=?",(self.item_id,)
            )
            c.execute("DELETE FROM publication_holds WHERE artifact_ref=?",(self.item_id,))
            c.execute("DELETE FROM program_items WHERE id=?",(self.item_id,))
            for email in self.users:
                c.execute("DELETE FROM auth_sessions WHERE email=?",(email,))
                c.execute("DELETE FROM accounts WHERE email=?",(email,))
            c.commit()
        finally:
            c.close()

    def test_two_concurrent_requests_cannot_both_take_last_place(self):
        barrier=threading.Barrier(2)
        outcomes={}
        errors=[]

        def book(email):
            c=db.connect()
            try:
                barrier.wait(timeout=5)
                out=programme_commands.handle_command(
                    c,"/api/activity-booking","participant",email,
                    {"item_id":self.item_id,"action":"book"},
                )
                c.commit()
                outcomes[email]=out.status
            except Exception as exc:
                try:
                    c.rollback()
                except Exception:
                    pass
                errors.append(repr(exc))
            finally:
                c.close()

        threads=[threading.Thread(target=book,args=(email,)) for email in self.users]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)

        self.assertFalse(errors,errors)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(sorted(outcomes.values()),[200,200])

        c=db.connect()
        try:
            rows=list(c.execute(
                "SELECT status FROM activity_bookings WHERE item_id=? ORDER BY status",
                (self.item_id,),
            ))
            self.assertEqual(
                sorted(row["status"] for row in rows),
                ["booked","waitlist"],
            )
        finally:
            c.close()

    def test_withdrawal_blocks_new_booking_and_cancel_does_not_promote(self):
        c=db.connect()
        try:
            first=programme_commands.handle_command(
                c,"/api/activity-booking","participant",self.users[0],
                {"item_id":self.item_id,"action":"book"},
            )
            second=programme_commands.handle_command(
                c,"/api/activity-booking","participant",self.users[1],
                {"item_id":self.item_id,"action":"book"},
            )
            self.assertEqual((first.status,second.status),(200,200))
            c.commit()

            c.execute(
                "UPDATE public_artifact_admissions "
                "SET status='withdrawn',withdrawn_at=? "
                "WHERE artifact_kind='event' AND artifact_ref=?",
                (int(time.time())+1,self.item_id),
            )
            c.commit()

            cancelled=programme_commands.handle_command(
                c,"/api/activity-booking","participant",self.users[0],
                {"item_id":self.item_id,"action":"cancel"},
            )
            c.commit()
            self.assertEqual(cancelled.status,200)
            remaining=c.execute(
                "SELECT status FROM activity_bookings WHERE email=? AND item_id=?",
                (self.users[1],self.item_id),
            ).fetchone()
            self.assertEqual(remaining["status"],"waitlist")

            blocked=programme_commands.handle_command(
                c,"/api/activity-booking","participant",self.users[0],
                {"item_id":self.item_id,"action":"book"},
            )
            self.assertEqual(blocked.status,404)
            self.assertEqual(blocked.payload,{"error":"program_item_not_found"})
            c.rollback()
        finally:
            c.close()


if __name__=="__main__":
    unittest.main()
