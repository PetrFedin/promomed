"""PostgreSQL 17 concurrency proof for partner appointment authority v1."""
import os
import threading
import time
import unittest
import uuid

from app import db, partner_appointment, public_state
from app.auth import hash_password


@unittest.skipUnless(
    os.environ.get("PROMOMED_PARTNER_APPOINTMENT_PG_TEST")=="1",
    "dedicated PostgreSQL partner appointment qualification only",
)
class PartnerAppointmentPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if db.backend_name()!="postgres":
            raise RuntimeError("postgres_required")
        c=db.connect()
        try: db.migrate(c)
        finally: c.close()

    def setUp(self):
        self.suffix=uuid.uuid4().hex[:10]
        self.org="ORG-APPT-"+self.suffix
        self.item="ITEM-APPT-"+self.suffix
        self.partner="partner-"+self.suffix+"@example.test"
        self.users=(
            "p1-"+self.suffix+"@example.test",
            "p2-"+self.suffix+"@example.test",
        )
        self.now=int(time.time())
        c=db.connect()
        try:
            for email,role in [(self.partner,"partner"),(self.users[0],"participant"),(self.users[1],"participant")]:
                c.execute(
                    "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
                    "VALUES(?,?,?,?,'active',?,?)",
                    (email,hash_password("StrongPartnerAppointment!42"),role,email,self.now,self.now),
                )
            c.execute(
                "INSERT INTO institutional_organizations("
                "id,name,organization_type,status,external_ref,credential_source,partner_id,"
                "created_at,created_by,demo_only"
                ") VALUES(?,?,'strategic_partner','active',NULL,'test',NULL,?,'governance',0)",
                (self.org,self.org,self.now),
            )
            c.execute(
                "INSERT INTO institutional_memberships("
                "id,organization_id,account_email,member_role,status,effective_at,expires_at,"
                "verified_by,verification_ref,demo_only"
                ") VALUES(?,?,?,'operator','active',?,NULL,'governance','verified',0)",
                ("M-"+self.suffix,self.org,self.partner,self.now-10),
            )
            c.execute(
                'INSERT INTO program_items(id,start,"end",venue,track,format,title,audience,capacity,stream,replay,partner) '
                "VALUES(?,?,?,?,?,?,?,?,20,1,1,'')",
                (self.item,"10:00","11:00","Hall A","Science","talk","PG appointment event","all"),
            )
            row=c.execute(
                'SELECT id,start,"end",venue,track,format,title,audience,capacity,stream,replay,partner '
                "FROM program_items WHERE id=?",(self.item,)
            ).fetchone()
            digest=public_state.payload_sha256("event",row)
            c.execute(
                "INSERT INTO public_artifact_admissions("
                "artifact_kind,artifact_ref,payload_sha256,status,reviewer_ref,source_ref,"
                "admitted_at,demo_only) VALUES('event',?,?,'admitted','review:pg','source:pg',?,0)",
                (self.item,digest,self.now),
            )
            c.commit()
        finally:
            c.close()

    def tearDown(self):
        c=db.connect()
        try:
            c.execute(
                "DELETE FROM partner_appointment_bookings_v1 "
                "WHERE slot_id IN (SELECT id FROM partner_appointment_slots_v1 WHERE organization_id=?)",
                (self.org,),
            )
            c.execute("DELETE FROM partner_appointment_operations_v1 WHERE actor_email=?",(self.partner,))
            c.execute("DELETE FROM partner_appointment_slots_v1 WHERE organization_id=?",(self.org,))
            c.execute("DELETE FROM public_artifact_admissions WHERE artifact_kind='event' AND artifact_ref=?",(self.item,))
            c.execute("DELETE FROM publication_holds WHERE artifact_ref=?",(self.item,))
            c.execute("DELETE FROM program_items WHERE id=?",(self.item,))
            c.execute("DELETE FROM institutional_memberships WHERE organization_id=?",(self.org,))
            c.execute("DELETE FROM institutional_organizations WHERE id=?",(self.org,))
            for email in (self.partner,*self.users):
                c.execute("DELETE FROM auth_sessions WHERE email=?",(email,))
                c.execute("DELETE FROM accounts WHERE email=?",(email,))
            c.commit()
        finally:
            c.close()

    def create_slot(self,capacity=1,request_id=None):
        c=db.connect()
        try:
            out=partner_appointment.handle_command(
                c,partner_appointment.SLOT_ROUTE,"partner",self.partner,{
                    "action":"create","organization_id":self.org,"item_id":self.item,
                    "start":"10:10","end":"10:30","capacity":capacity,
                    "request_id":request_id or uuid.uuid4().hex,
                },
            )
            c.commit()
            self.assertEqual(out.status,201,out.payload)
            return out.payload["slot"]["slotId"]
        finally:
            c.close()

    def test_two_concurrent_bookings_serialize_last_place(self):
        slot=self.create_slot(capacity=1)
        barrier=threading.Barrier(2)
        outcomes={}
        errors=[]
        def book(email):
            c=db.connect()
            try:
                barrier.wait(timeout=5)
                out=partner_appointment.handle_command(
                    c,partner_appointment.BOOKING_ROUTE,"participant",email,
                    {"slot_id":slot,"action":"book"},
                )
                c.commit()
                outcomes[email]=(out.status,out.payload["booking"]["status"])
            except Exception as exc:
                try:c.rollback()
                except Exception:pass
                errors.append(repr(exc))
            finally:c.close()

        threads=[threading.Thread(target=book,args=(email,)) for email in self.users]
        for t in threads:t.start()
        for t in threads:t.join(timeout=15)
        self.assertFalse(errors,errors)
        self.assertFalse(any(t.is_alive() for t in threads))
        self.assertEqual(sorted(status for _,status in outcomes.values()),["confirmed","waitlist"])

        c=db.connect()
        try:
            rows=list(c.execute(
                "SELECT status FROM partner_appointment_bookings_v1 WHERE slot_id=?",
                (slot,),
            ))
            self.assertEqual(sorted(x["status"] for x in rows),["confirmed","waitlist"])
        finally:c.close()

    def test_same_partner_request_id_creates_exactly_one_slot(self):
        request_id=uuid.uuid4().hex
        barrier=threading.Barrier(2)
        results=[]
        errors=[]
        def create():
            c=db.connect()
            try:
                barrier.wait(timeout=5)
                out=partner_appointment.handle_command(
                    c,partner_appointment.SLOT_ROUTE,"partner",self.partner,{
                        "action":"create","organization_id":self.org,"item_id":self.item,
                        "start":"10:10","end":"10:30","capacity":2,"request_id":request_id,
                    },
                )
                c.commit()
                results.append((out.status,out.payload["slot"]["slotId"]))
            except Exception as exc:
                try:c.rollback()
                except Exception:pass
                errors.append(repr(exc))
            finally:c.close()

        threads=[threading.Thread(target=create) for _ in range(2)]
        for t in threads:t.start()
        for t in threads:t.join(timeout=15)
        self.assertFalse(errors,errors)
        self.assertFalse(any(t.is_alive() for t in threads))
        self.assertEqual(sorted(x[0] for x in results),[200,201])
        self.assertEqual(len({x[1] for x in results}),1)

        c=db.connect()
        try:
            slots=c.execute(
                "SELECT COUNT(*) n FROM partner_appointment_slots_v1 WHERE organization_id=?",
                (self.org,),
            ).fetchone()["n"]
            ops=c.execute(
                "SELECT COUNT(*) n FROM partner_appointment_operations_v1 "
                "WHERE actor_email=? AND request_id=?",(self.partner,request_id)
            ).fetchone()["n"]
            self.assertEqual((int(slots),int(ops)),(1,1))
        finally:c.close()

    def test_withdrawal_cancel_does_not_promote_waitlist(self):
        slot=self.create_slot(capacity=1)
        c=db.connect()
        try:
            for email in self.users:
                out=partner_appointment.handle_command(
                    c,partner_appointment.BOOKING_ROUTE,"participant",email,
                    {"slot_id":slot,"action":"book"},
                )
                self.assertEqual(out.status,201)
                c.commit()
            c.execute(
                "UPDATE public_artifact_admissions SET status='withdrawn',withdrawn_at=? "
                "WHERE artifact_kind='event' AND artifact_ref=?",
                (self.now+1,self.item),
            )
            c.commit()
            out=partner_appointment.handle_command(
                c,partner_appointment.BOOKING_ROUTE,"participant",self.users[0],
                {"slot_id":slot,"action":"cancel"},
            )
            c.commit()
            self.assertEqual(out.status,200)
            self.assertFalse(out.payload["queuePromotionOccurred"])
            row=c.execute(
                "SELECT status FROM partner_appointment_bookings_v1 "
                "WHERE slot_id=? AND email=?",(slot,self.users[1])
            ).fetchone()
            self.assertEqual(row["status"],"waitlist")
        finally:c.close()


if __name__=="__main__":
    unittest.main()
