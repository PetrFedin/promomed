"""APPT-01 qualification for organization-scoped partner appointments."""
import importlib
import os
import tempfile
import time
import unittest
import uuid
from pathlib import Path

from app import db, my_workspace, partner_appointment, partner_org_scope, public_state
from app.auth import hash_password


class PartnerAppointmentV1Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old_env=dict(os.environ)
        os.environ.update({
            "SQLITE_PATH":str(Path(self.temp.name)/"appointments.db"),
            "DATABASE_URL":"",
            "PROMOMED_SEED_DEMO":"false",
            "PROMOMED_REQUIRE_POSTGRES":"false",
        })
        importlib.reload(db)
        importlib.reload(public_state)
        importlib.reload(partner_org_scope)
        importlib.reload(partner_appointment)
        importlib.reload(my_workspace)
        self.c=db.connect()
        db.migrate(self.c)
        self.now=int(time.time())
        self.partner_a="partner-a@example.test"
        self.partner_b="partner-b@example.test"
        self.users=("p1@example.test","p2@example.test","p3@example.test")
        for email,role in [
            (self.partner_a,"partner"),(self.partner_b,"partner"),
            *[(x,"participant") for x in self.users],
        ]:
            self.c.execute(
                "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
                "VALUES(?,?,?,?,'active',?,?)",
                (email,hash_password("StrongAppointment!42"),role,email,self.now,self.now),
            )
        for org,kind in (("ORG-A","strategic_partner"),("ORG-B","strategic_partner"),("ORG-X","hospital")):
            self.c.execute(
                "INSERT INTO institutional_organizations("
                "id,name,organization_type,status,external_ref,credential_source,partner_id,"
                "created_at,created_by,demo_only"
                ") VALUES(?,?,?,'active',NULL,'test',NULL,?,'governance',0)",
                (org,org,kind,self.now),
            )
        for idx,(org,email) in enumerate((("ORG-A",self.partner_a),("ORG-B",self.partner_b),("ORG-X",self.partner_a))):
            self.c.execute(
                "INSERT INTO institutional_memberships("
                "id,organization_id,account_email,member_role,status,effective_at,expires_at,"
                "verified_by,verification_ref,demo_only"
                ") VALUES(?,?,?,'operator','active',?,NULL,'governance','verified',0)",
                ("M"+str(idx),org,email,self.now-10),
            )
        self.item_id="P-APPT"
        self.c.execute(
            'INSERT INTO program_items(id,start,"end",venue,track,format,title,audience,capacity,stream,replay,partner) '
            "VALUES(?,?,?,?,?,?,?,?,20,1,1,'')",
            (self.item_id,"10:00","11:00","Hall A","Science","talk","Appointment event","all"),
        )
        self.admit()
        self.c.commit()

    def tearDown(self):
        self.c.close()
        os.environ.clear()
        os.environ.update(self.old_env)
        self.temp.cleanup()

    def item(self):
        return self.c.execute(
            'SELECT id,start,"end",venue,track,format,title,audience,capacity,stream,replay,partner '
            "FROM program_items WHERE id=?",(self.item_id,)
        ).fetchone()

    def admit(self):
        digest=public_state.payload_sha256("event",self.item())
        self.digest=digest
        self.c.execute(
            "INSERT INTO public_artifact_admissions("
            "artifact_kind,artifact_ref,payload_sha256,status,reviewer_ref,source_ref,"
            "admitted_at,demo_only) VALUES('event',?,?,'admitted','review:test','source:test',?,0)",
            (self.item_id,digest,self.now),
        )

    def partner(self,email,data):
        out=partner_appointment.handle_command(
            self.c,partner_appointment.SLOT_ROUTE,"partner",email,data
        )
        if out.status<400:self.c.commit()
        else:self.c.rollback()
        return out

    def participant(self,email,slot_id,action):
        out=partner_appointment.handle_command(
            self.c,partner_appointment.BOOKING_ROUTE,"participant",email,
            {"slot_id":slot_id,"action":action},
        )
        if out.status<400:self.c.commit()
        else:self.c.rollback()
        return out

    def create_slot(self,email=None,org="ORG-A",request_id=None,capacity=1):
        request_id=request_id or uuid.uuid4().hex
        out=self.partner(email or self.partner_a,{
            "action":"create","organization_id":org,"item_id":self.item_id,
            "start":"10:10","end":"10:30","capacity":capacity,"request_id":request_id,
        })
        self.assertEqual(out.status,201,out.payload)
        return out.payload["slot"]["slotId"],request_id

    def status(self,slot_id,email):
        row=self.c.execute(
            "SELECT status FROM partner_appointment_bookings_v1 WHERE slot_id=? AND email=?",
            (slot_id,email),
        ).fetchone()
        return row["status"] if row else None

    def test_create_replay_is_idempotent_and_scope_is_immutable(self):
        rid=uuid.uuid4().hex
        slot,_=self.create_slot(request_id=rid)
        replay=self.partner(self.partner_a,{
            "action":"create","organization_id":"ORG-A","item_id":self.item_id,
            "start":"10:10","end":"10:30","capacity":1,"request_id":rid,
        })
        self.assertEqual(replay.status,200)
        self.assertEqual(replay.payload["slot"]["slotId"],slot)
        n=self.c.execute("SELECT COUNT(*) n FROM partner_appointment_slots_v1").fetchone()["n"]
        self.assertEqual(int(n),1)
        with self.assertRaises(Exception):
            self.c.execute(
                "UPDATE partner_appointment_slots_v1 SET organization_id='ORG-B' WHERE id=?",
                (slot,),
            )
        self.c.rollback()

    def test_foreign_org_and_revoked_membership_cannot_manage_slot(self):
        slot,_=self.create_slot()
        out=self.partner(self.partner_b,{
            "action":"close","slot_id":slot,"expected_version":1,
            "request_id":uuid.uuid4().hex,
        })
        self.assertEqual((out.status,out.payload["error"]),(404,"slot_not_found"))

        self.c.execute(
            "UPDATE institutional_memberships SET status='revoked' "
            "WHERE organization_id='ORG-A' AND account_email=?",(self.partner_a,)
        )
        self.c.commit()
        out=self.partner(self.partner_a,{
            "action":"close","slot_id":slot,"expected_version":1,
            "request_id":uuid.uuid4().hex,
        })
        self.assertEqual((out.status,out.payload["error"]),(404,"slot_not_found"))

    def test_revoked_membership_blocks_idempotent_replay(self):
        rid=uuid.uuid4().hex
        slot,_=self.create_slot(request_id=rid)
        self.c.execute(
            "UPDATE institutional_memberships SET status='revoked' "
            "WHERE organization_id='ORG-A' AND account_email=?",(self.partner_a,)
        )
        self.c.commit()
        replay=self.partner(self.partner_a,{
            "action":"create","organization_id":"ORG-A","item_id":self.item_id,
            "start":"10:10","end":"10:30","capacity":1,"request_id":rid,
        })
        self.assertEqual((replay.status,replay.payload["error"]),(404,"organization_not_found"))
        self.assertEqual(
            int(self.c.execute(
                "SELECT COUNT(*) n FROM partner_appointment_slots_v1 WHERE id=?",(slot,)
            ).fetchone()["n"]),1
        )

    def test_non_strategic_partner_org_is_not_admitted(self):
        out=self.partner(self.partner_a,{
            "action":"create","organization_id":"ORG-X","item_id":self.item_id,
            "start":"10:10","end":"10:30","capacity":1,"request_id":uuid.uuid4().hex,
        })
        self.assertEqual((out.status,out.payload["error"]),(404,"organization_not_found"))

    def test_event_withdrawal_blocks_create_and_update_but_close_stays_owner_control(self):
        slot,_=self.create_slot()
        self.c.execute(
            "UPDATE public_artifact_admissions SET status='withdrawn',withdrawn_at=? "
            "WHERE artifact_kind='event' AND artifact_ref=?",(self.now+1,self.item_id)
        )
        self.c.commit()
        create=self.partner(self.partner_a,{
            "action":"create","organization_id":"ORG-A","item_id":self.item_id,
            "start":"10:30","end":"10:45","capacity":1,"request_id":uuid.uuid4().hex,
        })
        self.assertEqual((create.status,create.payload["error"]),(404,"program_item_not_found"))
        update=self.partner(self.partner_a,{
            "action":"update","slot_id":slot,"expected_version":1,
            "start":"10:15","end":"10:35","capacity":1,"request_id":uuid.uuid4().hex,
        })
        self.assertEqual((update.status,update.payload["error"]),(404,"program_item_not_found"))
        close=self.partner(self.partner_a,{
            "action":"close","slot_id":slot,"expected_version":1,
            "request_id":uuid.uuid4().hex,
        })
        self.assertEqual(close.status,200)
        self.assertEqual(close.payload["slot"]["status"],"closed")

    def test_capacity_waitlist_cancel_and_promotion(self):
        slot,_=self.create_slot(capacity=1)
        a=self.participant(self.users[0],slot,"book")
        b=self.participant(self.users[1],slot,"book")
        self.assertEqual((a.status,b.status),(201,201))
        self.assertEqual(self.status(slot,self.users[0]),"confirmed")
        self.assertEqual(self.status(slot,self.users[1]),"waitlist")
        self.assertFalse(a.payload["booking"]["marketingConsent"])
        self.assertFalse(a.payload["booking"]["partnerLead"])
        self.assertEqual(
            int(self.c.execute("SELECT COUNT(*) n FROM partner_engagement").fetchone()["n"]),0
        )
        cancelled=self.participant(self.users[0],slot,"cancel")
        self.assertTrue(cancelled.payload["queuePromotionOccurred"])
        self.assertEqual(self.status(slot,self.users[1]),"confirmed")

    def test_withdrawal_allows_owner_cancel_but_suppresses_promotion(self):
        slot,_=self.create_slot(capacity=1)
        self.participant(self.users[0],slot,"book")
        self.participant(self.users[1],slot,"book")
        self.c.execute(
            "UPDATE public_artifact_admissions SET status='withdrawn',withdrawn_at=? "
            "WHERE artifact_kind='event' AND artifact_ref=?",(self.now+1,self.item_id)
        )
        self.c.commit()
        cancelled=self.participant(self.users[0],slot,"cancel")
        self.assertFalse(cancelled.payload["queuePromotionOccurred"])
        self.assertEqual(self.status(slot,self.users[1]),"waitlist")
        blocked=self.participant(self.users[2],slot,"book")
        self.assertEqual((blocked.status,blocked.payload["error"]),(404,"slot_not_found"))

    def test_participant_cannot_supply_organization_selector(self):
        slot,_=self.create_slot()
        out=partner_appointment.handle_command(
            self.c,partner_appointment.BOOKING_ROUTE,"participant",self.users[0],
            {"slot_id":slot,"action":"book","organization_id":"ORG-B"},
        )
        self.assertEqual((out.status,out.payload["error"]),(422,"invalid_request"))
        self.c.rollback()

    def test_capacity_cannot_drop_below_confirmed(self):
        slot,_=self.create_slot(capacity=2)
        self.participant(self.users[0],slot,"book")
        self.participant(self.users[1],slot,"book")
        out=self.partner(self.partner_a,{
            "action":"update","slot_id":slot,"expected_version":1,
            "start":"10:10","end":"10:30","capacity":1,"request_id":uuid.uuid4().hex,
        })
        self.assertEqual((out.status,out.payload["error"]),(409,"capacity_below_confirmed"))

    def test_my_state_is_owner_scoped(self):
        slot,_=self.create_slot()
        self.participant(self.users[0],slot,"book")
        mine,status=my_workspace.read(
            self.c,my_workspace.READ_ROUTE,"participant",self.users[0]
        )
        self.assertEqual(status,200)
        self.assertEqual(len(mine["partnerAppointments"]),1)
        self.assertEqual(mine["partnerAppointments"][0]["slot_id"],slot)
        self.assertFalse(mine["truthBoundary"]["partnerAppointmentIsAttendance"])
        other,status=my_workspace.read(
            self.c,my_workspace.READ_ROUTE,"participant",self.users[1]
        )
        self.assertEqual(status,200)
        self.assertEqual(other["partnerAppointments"],[])
        self.assertNotIn(self.users[0],str(other))


if __name__=="__main__":
    unittest.main()
