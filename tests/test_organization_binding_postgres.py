"""PostgreSQL 17 qualification for safe organization metadata refresh."""
import os
import unittest
import uuid

from app import db, evidence_interchange


@unittest.skipUnless(
    os.environ.get("PROMOMED_ORG_UPSERT_PG_TEST")=="1",
    "isolated PostgreSQL 17 organization-binding qualification only",
)
class OrganizationBindingPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if db.backend_name()!="postgres":
            raise RuntimeError("postgres_required")
        c=db.connect()
        try:
            db.migrate(c)
        finally:
            c.close()

    def setUp(self):
        self.org="CI-BIND-"+uuid.uuid4().hex[:16]
        self.args={
            "organization_id":self.org,
            "name":"Synthetic governance organization",
            "organization_type":"strategic_partner",
            "actor":"governance-ci",
            "external_ref":"urn:test:org-binding",
            "credential_source":"synthetic-fixture",
            "demo_only":False,
        }
        c=db.connect()
        try:
            created=evidence_interchange.register_organization(c,**self.args)
            self.assertIsNone(created["partner_id"])
            c.execute(
                "UPDATE institutional_organizations SET partner_id=? WHERE id=?",
                ("existing-synthetic-binding",self.org),
            )
            c.commit()
        finally:
            c.close()

    def tearDown(self):
        c=db.connect()
        try:
            c.execute("DELETE FROM institutional_organizations WHERE id=?",(self.org,))
            c.commit()
        finally:
            c.close()

    def test_omitted_binding_survives_metadata_refresh(self):
        c=db.connect()
        try:
            updated=evidence_interchange.register_organization(
                c,**{**self.args,"name":"Synthetic renamed organization"},
            )
            self.assertEqual(updated["partner_id"],"existing-synthetic-binding")
            self.assertEqual(updated["name"],"Synthetic renamed organization")
            c.commit()
            row=c.execute(
                "SELECT partner_id,name FROM institutional_organizations WHERE id=?",
                (self.org,),
            ).fetchone()
            self.assertEqual(row["partner_id"],"existing-synthetic-binding")
        finally:
            c.close()

    def test_explicit_null_is_distinct_from_unspecified_binding(self):
        c=db.connect()
        try:
            with self.assertRaisesRegex(ValueError,"partner_id_invalid"):
                evidence_interchange.register_organization(
                    c,**{**self.args,"partner_id":" "},
                )
            self.assertEqual(
                c.execute(
                    "SELECT partner_id FROM institutional_organizations WHERE id=?",
                    (self.org,),
                ).fetchone()["partner_id"],
                "existing-synthetic-binding",
            )
            updated=evidence_interchange.register_organization(
                c,**{**self.args,"partner_id":None},
            )
            self.assertIsNone(updated["partner_id"])
            c.commit()
            self.assertIsNone(
                c.execute(
                    "SELECT partner_id FROM institutional_organizations WHERE id=?",
                    (self.org,),
                ).fetchone()["partner_id"]
            )
        finally:
            c.close()


if __name__=="__main__":
    unittest.main()
