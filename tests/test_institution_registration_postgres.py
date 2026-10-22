"""Real PostgreSQL 17 end-to-end governance registration/binding qualification."""
import os
import threading
import time
import unittest
import uuid

from app import db, evidence_interchange, institutional_commands, partner_appointments
from app import partner_org_scope, participant_agenda
from app.auth import hash_password

ROUTE="/api/institution/register"


@unittest.skipUnless(
    os.environ.get("PROMOMED_ORG_ROUTE_PG_TEST")=="1",
    "dedicated PostgreSQL 17 governance registration qualification only",
)
class InstitutionRegistrationPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if db.backend_name()!="postgres":
            raise RuntimeError("postgres_required")
        c=db.connect()
        try: db.migrate(c)
        finally: c.close()

    def setUp(self):
        tag=uuid.uuid4().hex[:12]
        self.org="PG-ORG-"+tag
        self.partner_id="PG-LEGACY-"+tag
        self.partner="pg-member-"+tag+"@example.test"
        self.participant="pg-owner-"+tag+"@example.test"
        self.governance="pg-gov-"+tag+"@example.test"
        self.slot=uuid.uuid4().hex
        self.now=int(time.time())
        self.base={
            "organization_id":self.org,
            "name":"PG synthetic institution",
            "organization_type":"strategic_partner",
        }
        c=db.connect()
        try:
            for email,role in (
                (self.partner,"partner"),
                (self.participant,"participant"),
                (self.governance,"governance"),
            ):
                c.execute(
                    "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at)"
                    " VALUES(?,?,?,?, 'active',?,?)",
                    (email,hash_password("PgBoundaryOnly!42"),role,email,self.now,self.now),
                )
            c.execute(
                "INSERT INTO partners(id,name,category,description,status)"
                " VALUES(?,'PG Synthetic','test','CI only','active')",
                (self.partner_id,),
            )
            evidence_interchange.register_organization(
                c,**self.base,actor=self.governance,
                external_ref="urn:pg:provenance",credential_source="pg:original",
                partner_id=self.partner_id,demo_only=False,
            )
            c.execute(
                "INSERT INTO institutional_memberships("
                "id,organization_id,account_email,member_role,status,effective_at,expires_at,"
                "verified_by,verification_ref,demo_only)"
                " VALUES(?,?,?,'administrator','active',?,NULL,?,?,0)",
                (uuid.uuid4().hex,self.org,self.partner,self.now-5,
                 self.governance,"pg-proof"),
            )
            c.execute(
                "INSERT INTO partner_commercial_placements_v1("
                "organization_id,status,version,updated_at,updated_by,demo_only"
                ") VALUES(?,'enabled',1,?,?,0)",
                (self.org,self.now,self.partner),
            )
            c.execute(
                "INSERT INTO partner_appointment_slots_v1("
                "id,organization_id,starts_at,ends_at,capacity,status,version,"
                "created_at,updated_at,created_by,demo_only)"
                " VALUES(?,?,?, ?,2,'open',1,?,?,?,0)",
                (self.slot,self.org,self.now+7200,self.now+9000,
                 self.now,self.now,self.partner),
            )
            c.execute(
                "INSERT INTO participant_partner_appointments_v1("
                "slot_id,email,status,contact_consent_at,requested_at,updated_at)"
                " VALUES(?,?,'booked',?,?,?)",
                (self.slot,self.participant,self.now,self.now,self.now),
            )
            c.commit()
        finally:
            c.close()

    def tearDown(self):
        c=db.connect()
        try:
            c.execute("DELETE FROM participant_partner_appointments_v1 WHERE slot_id=?",(self.slot,))
            c.execute("DELETE FROM partner_appointment_slots_v1 WHERE id=?",(self.slot,))
            c.execute("DELETE FROM partner_commercial_placements_v1 WHERE organization_id=?",(self.org,))
            c.execute("DELETE FROM institutional_memberships WHERE organization_id=?",(self.org,))
            c.execute("DELETE FROM institutional_organizations WHERE id=?",(self.org,))
            for email in (self.partner,self.participant,self.governance):
                c.execute("DELETE FROM auth_sessions WHERE email=?",(email,))
                c.execute("DELETE FROM accounts WHERE email=?",(email,))
            c.execute("DELETE FROM events WHERE actor=?",(self.governance,))
            c.execute("DELETE FROM partners WHERE id=?",(self.partner_id,))
            c.commit()
        finally:
            c.close()

    def test_governance_metadata_refresh_preserves_commercial_and_calendar(self):
        c=db.connect()
        try:
            result=institutional_commands.handle_command(
                c,ROUTE,"governance",self.governance,
                {**self.base,"name":"PG renamed institution"},
            )
            self.assertEqual(result.status,201,result.payload)
            c.commit()
            org=evidence_interchange.organization(c,self.org)
            self.assertEqual(org["partner_id"],self.partner_id)
            self.assertEqual(org["external_ref"],"urn:pg:provenance")
            self.assertEqual(org["credential_source"],"pg:original")
            self.assertEqual(org["demo_only"],0)
            self.assertIsNotNone(partner_org_scope.commercial_member(c,self.org,self.partner))
            view,status=partner_appointments.read(
                c,partner_appointments.ROUTE,"partner",self.partner,
            )
            self.assertEqual(status,200)
            self.assertEqual(view["organizations"][0]["organizationName"],"PG renamed institution")
            agenda,status=participant_agenda.read(
                c,participant_agenda.ROUTE,"participant",self.participant,
            )
            self.assertEqual(status,200)
            self.assertEqual(len(agenda["items"]),1)
            self.assertEqual(agenda["items"][0]["state"],"booked")
            self.assertEqual(agenda["calendarIcs"].count("BEGIN:VEVENT"),1)
        finally:
            c.close()

    def test_http_bound_change_fail_closed_pg(self):
        c=db.connect()
        try:
            for attempt in (None,"different-binding"):
                result=institutional_commands.handle_command(
                    c,ROUTE,"governance",self.governance,
                    {**self.base,"partner_id":attempt},
                )
                self.assertEqual(
                    (result.status,result.payload["error"]),
                    (409,"partner_binding_change_requires_review"),
                )
                c.rollback()
            org=evidence_interchange.organization(c,self.org)
            self.assertEqual(org["partner_id"],self.partner_id)
        finally:
            c.close()

    def test_concurrent_metadata_refreshes_do_not_clear_binding(self):
        barrier=threading.Barrier(2)
        failures=[]
        outcomes=[]
        def refresh(label):
            c=db.connect()
            try:
                barrier.wait(timeout=6)
                result=institutional_commands.handle_command(
                    c,ROUTE,"governance",self.governance,
                    {**self.base,"name":"Rename "+label},
                )
                self.assertEqual(result.status,201,result.payload)
                c.commit()
                outcomes.append(result.status)
            except Exception as exc:
                try:c.rollback()
                except Exception:pass
                failures.append(repr(exc))
            finally:c.close()
        jobs=[threading.Thread(target=refresh,args=(name,)) for name in ("A","B")]
        for job in jobs:job.start()
        for job in jobs:job.join(timeout=20)
        self.assertFalse(any(job.is_alive() for job in jobs))
        self.assertEqual(failures,[])
        self.assertEqual(outcomes,[201,201])
        c=db.connect()
        try:
            org=evidence_interchange.organization(c,self.org)
            self.assertEqual(org["partner_id"],self.partner_id)
            self.assertEqual(org["external_ref"],"urn:pg:provenance")
            self.assertEqual(org["credential_source"],"pg:original")
            self.assertIsNotNone(partner_org_scope.commercial_member(
                c,self.org,self.partner,
            ))
        finally:c.close()


if __name__=="__main__":
    unittest.main()
