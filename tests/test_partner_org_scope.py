"""Tenant-negative tests for partner collaboration against the same DB authority."""
import importlib
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app import partner_collaboration as pc
from app import partner_org_scope as scopes
from app import partner_execution
from app import db, evidence_interchange, syndication_network
from app.auth import hash_password, seed_demo_accounts

C="/api/partner-collaboration/create"
T="/api/partner-collaboration/task"
P="/api/partner-collaboration/project"
E="/api/partner-collaboration/execute"


class PartnerOrganizationScopeTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "SQLITE_PATH":str(Path(self.t.name)/"scope.db"),
            "DATABASE_URL":"",
            "PROMOMED_SEED_DEMO":"false",
        })
        self.env.start()
        importlib.reload(db)
        self.c=db.connect()
        db.migrate(self.c)
        seed_demo_accounts(self.c)
        ts=int(time.time())
        self.c.execute(
            """INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at)
            VALUES(?,?,?,'Partner second','active',?,?)""",
            ("partner2@demo.ru",hash_password("test-only"),"partner",ts,ts),
        )
        for id in ("ORG-QA-A","ORG-QA-B"):
            evidence_interchange.register_organization(
                self.c,organization_id=id,name="Synthetic "+id,
                organization_type="strategic_partner",
                actor="governance@demo.ru",external_ref="urn:synthetic:"+id,
                credential_source="synthetic-fixture",demo_only=True,
            )
        for org,mail in [("ORG-QA-A","partner@demo.ru"),
                         ("ORG-QA-B","partner2@demo.ru")]:
            syndication_network.bind_member(
                self.c,org,mail,"operator","governance@demo.ru",
                verification_ref="fixture-verified-membership",demo_only=True,
            )
        self.c.commit()
        self.counter=0

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.t.cleanup()

    def go(self,route,role="partner",email="partner@demo.ru",op=None,**data):
        self.counter+=1
        outcome=pc.handle_command(self.c,route,role,email,
                                  {"operation_id":op or f"org-op-{self.counter}",**data})
        if outcome.status<400:self.c.commit()
        else:self.c.rollback()
        return outcome

    def create(self,org="ORG-QA-A",email="partner@demo.ru"):
        result=self.go(C,email=email,organization_id=org,
                       title="Synthetic Studio",format="studio")
        self.assertEqual(result.status,201,result.payload)
        return result.payload["project_id"]

    def test_scoped_create_read_and_separate_organizations(self):
        pid=self.create()
        row=pc.snapshot(self.c,"partner","partner@demo.ru",pid)
        self.assertEqual(row["project"]["organization_id"],"ORG-QA-A")
        self.assertEqual(row["project"]["demo_only"],1)
        self.assertEqual(pc.snapshot(self.c,"partner","partner2@demo.ru")["projects"],[])
        with self.assertRaises(LookupError):
            pc.snapshot(self.c,"partner","partner2@demo.ru",pid)
        self.assertEqual(self.go(T,email="partner2@demo.ru",project_id=pid,
                                 title="foreign",lane="partner").status,404)
        self.assertEqual(self.go(C,email="partner2@demo.ru",
                                 organization_id="ORG-QA-A",
                                 title="foreign",format="studio").status,404)
        self.assertEqual(self.go(T,role="participant",email="participant@demo.ru",
                                 project_id=pid,title="foreign",lane="partner").status,403)
        with self.assertRaises(Exception):
            self.c.execute("DELETE FROM partner_collab_project_scopes WHERE project_id=?",(pid,))
        self.c.rollback()

    def test_same_organization_verified_collaborator_can_operate(self):
        pid=self.create()
        syndication_network.bind_member(
            self.c,"ORG-QA-A","partner2@demo.ru","operator",
            "governance@demo.ru","synthetic-team-access",demo_only=True)
        self.c.commit()
        access=pc.snapshot(self.c,"partner","partner2@demo.ru",pid)
        self.assertEqual(access["project"]["organization_id"],"ORG-QA-A")
        t=self.go(T,email="partner2@demo.ru",project_id=pid,
                  title="Additional task",lane="partner")
        self.assertEqual(t.status,201)
        self.assertEqual(len(pc.snapshot(self.c,"partner","partner@demo.ru",pid)["tasks"]),1)

    def test_suspension_expiry_and_revocation_cancel_all_access_including_replay(self):
        created=self.go(C,op="replayed-create",organization_id="ORG-QA-A",
                        title="Synthetic Studio",format="studio")
        pid=created.payload["project_id"]
        t=self.go(T,project_id=pid,title="One task",lane="partner")
        tid=t.payload["task_id"]
        self.go(P,project_id=pid,action="request_review",expected_version=1)
        self.go(P,role="organizer",email="organizer@demo.ru",
                project_id=pid,action="review",expected_version=2)
        self.c.execute("UPDATE institutional_memberships SET status='revoked' WHERE organization_id=? AND account_email=?",
                      ("ORG-QA-A","partner@demo.ru"))
        self.c.commit()
        self.assertEqual(pc.snapshot(self.c,"partner","partner@demo.ru")["projects"],[])
        with self.assertRaises(LookupError):
            pc.snapshot(self.c,"partner","partner@demo.ru",pid)
        self.assertEqual(self.go(E,project_id=pid,task_id=tid,
                                 action="start",expected_version=1).status,404)
        self.assertEqual(self.go(C,op="replayed-create",organization_id="ORG-QA-A",
                                 title="Synthetic Studio",format="studio").status,404)
        syndication_network.bind_member(
            self.c,"ORG-QA-A","partner@demo.ru","operator",
            "governance@demo.ru","reinstated-fixture",demo_only=True)
        self.c.execute("UPDATE institutional_memberships SET expires_at=? WHERE organization_id=? AND account_email=?",
                      (int(time.time())-1,"ORG-QA-A","partner@demo.ru"))
        self.c.commit()
        self.assertEqual(self.go(E,project_id=pid,task_id=tid,
                                 action="start",expected_version=1).status,404)

    def test_account_role_changes_and_suspended_organizer_block_tenant_reads(self):
        pid=self.create()
        self.assertEqual(pc.snapshot(self.c,"organizer","organizer@demo.ru",pid)["project"]["id"],pid)
        self.c.execute("UPDATE accounts SET role='participant' WHERE email='partner@demo.ru'")
        self.c.commit()
        with self.assertRaises(LookupError):
            pc.snapshot(self.c,"partner","partner@demo.ru",pid)
        self.assertEqual(pc.snapshot(self.c,"partner","partner@demo.ru")["projects"],[])
        self.c.execute("UPDATE accounts SET role='partner' WHERE email='partner@demo.ru'")
        self.c.execute("UPDATE accounts SET status='suspended' WHERE email='organizer@demo.ru'")
        self.c.commit()
        with self.assertRaises(LookupError):
            pc.snapshot(self.c,"organizer","organizer@demo.ru",pid)
        self.assertEqual(self.go(P,role="organizer",email="organizer@demo.ru",
             project_id=pid,action="archive",expected_version=1).status,404)

    def test_unverified_membership_not_sufficient_and_unscoped_production_denied(self):
        self.c.execute("UPDATE institutional_memberships SET verification_ref='' WHERE organization_id='ORG-QA-A'")
        self.c.commit()
        self.assertEqual(self.go(C,organization_id="ORG-QA-A",
                                 title="Attempt",format="studio").status,404)
        self.assertEqual(pc.snapshot(self.c,"partner","partner@demo.ru")["projects"],[])
        with patch.object(db,"backend_name",return_value="postgres"),patch.object(db,"demo_seed_enabled",return_value=False):
            self.assertEqual(self.go(C,title="Unscoped",format="studio").status,422)

    def test_non_demo_candidate_must_not_be_promoted(self):
        self.c.execute(
          """INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at)
             VALUES(?,?,?,'External','active',?,?)""",
          ("external@example.test",hash_password("test-only"),"partner",int(time.time()),int(time.time())),
        )
        evidence_interchange.register_organization(
            self.c,organization_id="ORG-NON-DEMO",name="Synthetic registered",
            organization_type="strategic_partner",actor="governance@demo.ru",
            external_ref="urn:synthetic:real",credential_source="test",
            demo_only=False,
        )
        syndication_network.bind_member(
            self.c,"ORG-NON-DEMO","external@example.test","administrator",
            "governance@demo.ru","verified-in-test",demo_only=False)
        self.c.commit()
        response=self.go(C,email="external@example.test",
                         organization_id="ORG-NON-DEMO",title="External trial",format="event")
        self.assertEqual(response.status,409)
        self.assertEqual(response.payload["error"],"non_demo_partner_pilot_not_admitted")

    def test_membership_discovery_filtered_and_malformed_identifiers(self):
        orgs=scopes.partner_organizations(self.c,"partner@demo.ru")
        self.assertEqual([x["id"] for x in orgs],["ORG-QA-A"])
        self.assertEqual(self.go(C,organization_id=["ORG-QA-A"],
                                 title="Bad",format="studio").status,422)
        self.assertEqual(self.go(C,organization_id="ORG-NOT-FOUND",
                                 title="Bad",format="studio").status,404)
        self.assertEqual(self.go(C,organization_id="ORG-QA-A",
                                 title="Bad",format=["studio"]).status,422)
        self.assertEqual(self.go(P,project_id="dead",action=["review"],
                                 expected_version=1).status,404)


if __name__=="__main__":
    unittest.main()
