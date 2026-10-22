"""P0 regression: governance metadata requests cannot revoke commercial bindings.

This is an authenticated-route and canonical-state test, not proof of a
separately authorized commercial partner reassignment workflow.
"""
import importlib
import io
import json
import os
import tempfile
import time
import unittest
import uuid
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import evidence_interchange, institutional_commands, partner_appointments
from app import partner_commercial, participant_agenda, partner_org_scope
from app.auth import hash_password
from server import H


ROUTE="/api/institution/register"


class InstitutionRegistrationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "SQLITE_PATH":str(Path(self.tmp.name)/"institutional-boundary.db"),
            "DATABASE_URL":"",
            "PROMOMED_SEED_DEMO":"false",
            "PROMOMED_REQUIRE_POSTGRES":"false",
        })
        self.env.start()
        from app import db
        importlib.reload(db)
        self.db=db
        self.c=db.connect()
        db.migrate(self.c)
        self.now=int(time.time())
        tag=uuid.uuid4().hex[:9]
        self.org="BOUND-ORG-"+tag
        self.partner_id="BOUND-PARTNER-"+tag
        self.partner="bound-partner-"+tag+"@example.test"
        self.participant="bound-participant-"+tag+"@example.test"
        self.governance="bound-governance-"+tag+"@example.test"
        self.base={
            "organization_id":self.org,
            "name":"Synthetic Institution",
            "organization_type":"strategic_partner",
        }
        for email,role in (
            (self.partner,"partner"),
            (self.participant,"participant"),
            (self.governance,"governance"),
        ):
            self.c.execute(
                "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at)"
                " VALUES(?,?,?,?, 'active',?,?)",
                (email,hash_password("TemporaryCIOnly!42"),role,email,self.now,self.now),
            )
        self.c.execute(
            "INSERT INTO partners(id,name,category,description,status)"
            " VALUES(?,'Synthetic Partner','test','Synthetic CI only','active')",
            (self.partner_id,),
        )
        registered=evidence_interchange.register_organization(
            self.c,**self.base,actor=self.governance,
            external_ref="urn:original:institution",
            credential_source="evidence:original",
            partner_id=self.partner_id,demo_only=False,
        )
        self.assertEqual(registered["partner_id"],self.partner_id)
        self.c.execute(
            "INSERT INTO institutional_memberships("
            "id,organization_id,account_email,member_role,status,effective_at,expires_at,"
            "verified_by,verification_ref,demo_only)"
            " VALUES(?,?,?,'administrator','active',?,NULL,?,?,0)",
            ("MEM-"+tag,self.org,self.partner,self.now-10,self.governance,
             "synthetic-verified-member"),
        )
        self.c.commit()
        placement=partner_commercial.handle_command(
            self.c,partner_commercial.ROUTE,"partner",self.partner,{
                "action":"placement_update","organization_id":self.org,
                "status":"enabled","expected_version":0,
            },
        )
        self.assertEqual(placement.status,201,placement.payload)
        self.c.commit()
        slot=partner_appointments.handle_command(
            self.c,partner_appointments.ROUTE,"partner",self.partner,{
                "action":"slot_create","organization_id":self.org,
                "starts_at":self.now+7200,"ends_at":self.now+9000,"capacity":2,
            },
        )
        self.assertEqual(slot.status,201,slot.payload)
        self.slot=slot.payload["slot"]["id"]
        booked=partner_appointments.handle_command(
            self.c,partner_appointments.ROUTE,"participant",self.participant,{
                "action":"book","slot_id":self.slot,"contact_consent":True,
            },
        )
        self.assertEqual(booked.status,201,booked.payload)
        self.c.commit()

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.tmp.cleanup()

    def command(self,data,role="governance"):
        output=institutional_commands.handle_command(
            self.c,ROUTE,role,self.governance,data,
        )
        if output.status>=400:self.c.rollback()
        else:self.c.commit()
        return output

    def institution(self):
        return evidence_interchange.organization(self.c,self.org)

    def test_metadata_only_refresh_preserves_binding_provenance_and_demo_boundary(self):
        outcome=self.command({**self.base,"name":"Synthetic Institution Renamed"})
        self.assertEqual(outcome.status,201,outcome.payload)
        organization=self.institution()
        self.assertEqual(organization["name"],"Synthetic Institution Renamed")
        self.assertEqual(organization["partner_id"],self.partner_id)
        self.assertEqual(organization["external_ref"],"urn:original:institution")
        self.assertEqual(organization["credential_source"],"evidence:original")
        self.assertEqual(organization["demo_only"],0)
        self.assertIsNotNone(partner_org_scope.commercial_member(
            self.c,self.org,self.partner,
        ))
        partner_view,status=partner_appointments.read(
            self.c,partner_appointments.ROUTE,"partner",self.partner,
        )
        self.assertEqual(status,200)
        self.assertEqual(len(partner_view["organizations"]),1)
        self.assertEqual(
            partner_view["organizations"][0]["slots"][0]["bookings"][0]["email"],
            self.participant,
        )
        agenda,status=participant_agenda.read(
            self.c,participant_agenda.ROUTE,"participant",self.participant,
        )
        self.assertEqual(status,200)
        self.assertTrue(any(x["id"]=="appointment:"+self.slot
                            and x["calendarEligible"] for x in agenda["items"]))
        self.assertIn("Synthetic Institution Renamed",agenda["calendarIcs"])

    def test_explicit_partner_remove_change_or_blank_is_denied(self):
        for partner_id,expected_code,expected_status in (
            (None,"partner_binding_change_requires_review",409),
            ("different-partner","partner_binding_change_requires_review",409),
            ("","partner_id_invalid",422),
            ("   ","partner_id_invalid",422),
            (123,"partner_id_invalid",422),
        ):
            with self.subTest(partner_id=partner_id):
                result=self.command({**self.base,"partner_id":partner_id})
                self.assertEqual(
                    (result.status,result.payload["error"]),
                    (expected_status,expected_code),
                )
                self.assertEqual(self.institution()["partner_id"],self.partner_id)
                self.assertIsNotNone(partner_org_scope.commercial_member(
                    self.c,self.org,self.partner,
                ))

    def test_readonly_equal_binding_does_not_clear_on_metadata_update(self):
        result=self.command({
            **self.base,"partner_id":self.partner_id,
            "credential_source":"new-attested-source",
        })
        self.assertEqual(result.status,201)
        org=self.institution()
        self.assertEqual(org["partner_id"],self.partner_id)
        self.assertEqual(org["credential_source"],"new-attested-source")
        self.assertEqual(org["external_ref"],"urn:original:institution")
        result=self.command({**self.base,"external_ref":None})
        self.assertEqual(result.status,201)
        self.assertEqual(self.institution()["external_ref"],"")

    def test_new_org_requires_separately_governed_initial_binding(self):
        fresh={**self.base,"organization_id":self.org+"-NEW"}
        refused=self.command({**fresh,"partner_id":self.partner_id})
        self.assertEqual((refused.status,refused.payload["error"]),
                         (409,"partner_binding_change_requires_review"))
        self.assertIsNone(self.c.execute(
            "SELECT 1 FROM institutional_organizations WHERE id=?",
            (fresh["organization_id"],),
        ).fetchone())
        created=self.command(fresh)
        self.assertEqual(created.status,201)
        self.assertIsNone(created.payload["data"]["partner_id"])
        self.assertEqual(created.payload["data"]["demo_only"],0)

    def test_invalid_or_conflicting_demo_authority_cannot_mutate(self):
        for flag,expected_code,expected_status in (
            (True,"organization_demo_boundary_mismatch",409),
            (1,"organization_demo_boundary_invalid",422),
            ("false","organization_demo_boundary_invalid",422),
            (None,"organization_demo_boundary_invalid",422),
        ):
            with self.subTest(flag=flag):
                outcome=self.command({**self.base,"demo_only":flag})
                self.assertEqual((outcome.status,outcome.payload["error"]),
                                 (expected_status,expected_code))
                self.assertEqual(self.institution()["demo_only"],0)
                self.assertEqual(self.institution()["partner_id"],self.partner_id)

    def test_mutation_permissions_and_non_object_payload(self):
        other=self.command(self.base,role="partner")
        self.assertEqual((other.status,other.payload["error"]),(403,"forbidden"))
        invalid=self.command(None)
        self.assertEqual((invalid.status,invalid.payload["error"]),
                         (422,"invalid_request"))
        self.assertEqual(self.institution()["partner_id"],self.partner_id)

    def test_governed_update_audit_only_for_accepted_changes(self):
        before=int(self.c.execute(
            "SELECT COUNT(*) n FROM events WHERE actor=? AND kind='institution_metadata_updated'",
            (self.governance,),
        ).fetchone()["n"])
        accepted=self.command({**self.base,"name":"Audited Refresh"})
        self.assertEqual(accepted.status,201)
        after=int(self.c.execute(
            "SELECT COUNT(*) n FROM events WHERE actor=? AND kind='institution_metadata_updated'",
            (self.governance,),
        ).fetchone()["n"])
        self.assertEqual(after,before+1)
        audit_event=self.c.execute(
            "SELECT payload FROM events WHERE actor=? AND kind='institution_metadata_updated'"
            " ORDER BY id DESC LIMIT 1",
            (self.governance,),
        ).fetchone()
        self.assertEqual(json.loads(audit_event["payload"]),{
            "organization_id":self.org,"binding_changed":False,"demo_only":0,
        })
        denied=self.command({**self.base,"partner_id":None})
        self.assertEqual(denied.status,409)
        unchanged=int(self.c.execute(
            "SELECT COUNT(*) n FROM events WHERE actor=? AND kind='institution_metadata_updated'",
            (self.governance,),
        ).fetchone()["n"])
        self.assertEqual(unchanged,after)

    def test_real_http_post_path_preserves_partner_binding(self):
        data={**self.base,"name":"From authenticated HTTP"}
        encoded=json.dumps(data).encode("utf-8")
        headers=Message()
        headers["Content-Length"]=str(len(encoded))
        request=SimpleNamespace(
            path=ROUTE,headers=headers,rfile=io.BytesIO(encoded),
            out=lambda value,status=200:(value,status),
        )
        with patch("server.auth",return_value=("governance","Synthetic",self.governance)):
            with patch("server.conn",side_effect=self.db.connect):
                result,status=H.do_POST(request)
        self.assertEqual(status,201,result)
        self.assertEqual(result["data"]["partner_id"],self.partner_id)
        self.c.rollback()
        self.assertEqual(self.institution()["name"],"From authenticated HTTP")
        self.assertEqual(self.institution()["partner_id"],self.partner_id)


if __name__=="__main__":
    unittest.main()
