"""PostgreSQL 17 concurrency/isolation proof for partner appointments."""
import os
import threading
import time
import unittest
import uuid

from app import db, partner_appointments, partner_commercial
from app.auth import hash_password


@unittest.skipUnless(
    os.environ.get("PROMOMED_PARTNER_APPOINTMENTS_PG_TEST")=="1",
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
        suffix=uuid.uuid4().hex[:8]
        self.org="APPT-ORG-"+suffix
        self.partner="appt-partner-"+suffix+"@example.test"
        self.users=(
            "appt-a-"+suffix+"@example.test",
            "appt-b-"+suffix+"@example.test",
        )
        self.now=int(time.time())
        c=db.connect()
        try:
            for email,role in ((self.partner,"partner"),(self.users[0],"participant"),(self.users[1],"participant")):
                c.execute(
                    "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
                    "VALUES(?,?,?,?, 'active',?,?)",
                    (email,hash_password("StrongAppointmentPg!42"),role,email,self.now,self.now),
                )
            c.execute(
                "INSERT INTO institutional_organizations("
                "id,name,organization_type,status,external_ref,credential_source,partner_id,"
                "created_at,created_by,demo_only) VALUES(?,?,?,'active','ext','registry',?,?,?,0)",
                (self.org,"Appointment Org","commercial_partner","partner-appt",self.now,"governance"),
            )
            c.execute(
                "INSERT INTO institutional_memberships("
                "id,organization_id,account_email,member_role,status,effective_at,expires_at,"
                "verified_by,verification_ref,demo_only) "
                "VALUES(?,?,?,'administrator','active',?,NULL,'governance','verification:appt',0)",
                (uuid.uuid4().hex,self.org,self.partner,self.now-10),
            )
            c.commit()
            out=partner_commercial.handle_command(
                c,partner_commercial.ROUTE,"partner",self.partner,{
                    "action":"placement_update","organization_id":self.org,
                    "status":"enabled","expected_version":0,
                }
            )
            self.assertEqual(out.status,201)
            c.commit()
            slot=partner_appointments.handle_command(
                c,partner_appointments.ROUTE,"partner",self.partner,{
                    "action":"slot_create","organization_id":self.org,
                    "starts_at":self.now+3600,"ends_at":self.now+5400,"capacity":1,
                }
            )
            self.assertEqual(slot.status,201)
            self.slot_id=slot.payload["slot"]["id"]
            c.commit()
        finally:
            c.close()

    def tearDown(self):
        c=db.connect()
        try:
            c.execute(
                "DELETE FROM participant_partner_appointments_v1 WHERE slot_id=?",
                (self.slot_id,),
            )
            c.execute(
                "DELETE FROM partner_appointment_slots_v1 WHERE id=?",(self.slot_id,)
            )
            c.execute(
                "DELETE FROM partner_commercial_placements_v1 WHERE organization_id=?",
                (self.org,),
            )
            c.execute(
                "DELETE FROM institutional_memberships WHERE organization_id=?",
                (self.org,),
            )
            c.execute("DELETE FROM institutional_organizations WHERE id=?",(self.org,))
            for email in (self.partner,*self.users):
                c.execute("DELETE FROM auth_sessions WHERE email=?",(email,))
                c.execute("DELETE FROM accounts WHERE email=?",(email,))
            c.commit()
        finally:
            c.close()

    def test_two_concurrent_bookings_serialize_last_place(self):
        barrier=threading.Barrier(2)
        outcomes={}
        errors=[]

        def book(email):
            c=db.connect()
            try:
                barrier.wait(timeout=5)
                out=partner_appointments.handle_command(
                    c,partner_appointments.ROUTE,"participant",email,{
                        "action":"book","slot_id":self.slot_id,
                        "contact_consent":True,
                    }
                )
                c.commit()
                outcomes[email]=out.payload["appointment"]["status"]
            except Exception as exc:
                try:c.rollback()
                except Exception:pass
                errors.append(repr(exc))
            finally:
                c.close()

        threads=[threading.Thread(target=book,args=(email,)) for email in self.users]
        for thread in threads:thread.start()
        for thread in threads:thread.join(timeout=15)
        self.assertFalse(errors,errors)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(sorted(outcomes.values()),["booked","waitlist"])

    def test_membership_revocation_hides_partner_but_owner_cancel_remains(self):
        c=db.connect()
        try:
            booked=partner_appointments.handle_command(
                c,partner_appointments.ROUTE,"participant",self.users[0],{
                    "action":"book","slot_id":self.slot_id,"contact_consent":True,
                }
            )
            self.assertEqual(booked.status,201)
            c.commit()

            c.execute(
                "UPDATE institutional_memberships SET status='revoked' "
                "WHERE organization_id=? AND account_email=?",
                (self.org,self.partner),
            )
            c.commit()
            snap,status=partner_appointments.read(
                c,partner_appointments.ROUTE,"partner",self.partner
            )
            self.assertEqual(status,200)
            self.assertEqual(snap["organizations"],[])

            denied=partner_appointments.handle_command(
                c,partner_appointments.ROUTE,"partner",self.partner,{
                    "action":"slot_update","slot_id":self.slot_id,
                    "expected_version":1,"starts_at":self.now+3600,
                    "ends_at":self.now+5400,"capacity":1,"status":"closed",
                }
            )
            self.assertEqual((denied.status,denied.payload["error"]),(404,"slot_not_found"))
            c.rollback()

            cancelled=partner_appointments.handle_command(
                c,partner_appointments.ROUTE,"participant",self.users[0],{
                    "action":"cancel","slot_id":self.slot_id,
                }
            )
            self.assertEqual(cancelled.status,200)
            c.commit()
        finally:
            c.close()


if __name__=="__main__":
    unittest.main()
