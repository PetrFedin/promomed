"""PostgreSQL 17 cross-tenant proof for Partner Commercial v1."""
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import time
import unittest
import uuid

from app import db, partner_commercial
from app.auth import hash_password


@unittest.skipUnless(
    os.environ.get("PROMOMED_PARTNER_COMMERCIAL_PG_TEST")=="1",
    "dedicated PostgreSQL partner commercial qualification only",
)
class PartnerCommercialPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if db.backend_name()!="postgres":
            raise RuntimeError("postgres_required")
        c=db.connect()
        try: db.migrate(c)
        finally: c.close()

    def setUp(self):
        suffix=uuid.uuid4().hex[:8]
        self.org_a="ORG-A-"+suffix
        self.org_b="ORG-B-"+suffix
        self.partner_a="partner-a-"+suffix+"@example.test"
        self.partner_b="partner-b-"+suffix+"@example.test"
        self.participant="participant-"+suffix+"@example.test"
        self.now=int(time.time())
        c=db.connect()
        try:
            for email,role in (
                (self.partner_a,"partner"),
                (self.partner_b,"partner"),
                (self.participant,"participant"),
            ):
                c.execute(
                    "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
                    "VALUES(?,?,?,?, 'active',?,?)",
                    (email,hash_password("StrongPartnerPg!42"),role,email,self.now,self.now),
                )
            for org,name,partner_id in (
                (self.org_a,"Org A","partner-a"),
                (self.org_b,"Org B","partner-b"),
            ):
                c.execute(
                    "INSERT INTO institutional_organizations("
                    "id,name,organization_type,status,external_ref,credential_source,partner_id,"
                    "created_at,created_by,demo_only) VALUES(?,?,?,'active','ext','registry',?,?,?,0)",
                    (org,name,"commercial_partner",partner_id,self.now,"governance"),
                )
            for idx,(org,email) in enumerate(((self.org_a,self.partner_a),(self.org_b,self.partner_b)),1):
                c.execute(
                    "INSERT INTO institutional_memberships("
                    "id,organization_id,account_email,member_role,status,effective_at,expires_at,"
                    "verified_by,verification_ref,demo_only) "
                    "VALUES(?,?,?,'administrator','active',?,NULL,'governance',?,0)",
                    (uuid.uuid4().hex,org,email,self.now-10,"verification:"+str(idx)),
                )
            c.commit()
        finally:
            c.close()

    def tearDown(self):
        c=db.connect()
        try:
            c.execute(
                "DELETE FROM participant_partner_leads_v1 "
                "WHERE email=?",(self.participant,)
            )
            c.execute(
                "DELETE FROM partner_commercial_placements_v1 "
                "WHERE organization_id IN (?,?)",(self.org_a,self.org_b)
            )
            c.execute(
                "DELETE FROM institutional_memberships "
                "WHERE organization_id IN (?,?)",(self.org_a,self.org_b)
            )
            c.execute(
                "DELETE FROM institutional_organizations "
                "WHERE id IN (?,?)",(self.org_a,self.org_b)
            )
            for email in (self.partner_a,self.partner_b,self.participant):
                c.execute("DELETE FROM auth_sessions WHERE email=?",(email,))
                c.execute("DELETE FROM accounts WHERE email=?",(email,))
            c.commit()
        finally:
            c.close()

    def command(self,c,role,email,**data):
        out=partner_commercial.handle_command(
            c,partner_commercial.ROUTE,role,email,data
        )
        if out.status<400:c.commit()
        else:c.rollback()
        return out

    def test_cross_tenant_placement_and_lead_isolation(self):
        c=db.connect()
        try:
            created=self.command(
                c,"partner",self.partner_a,
                action="placement_update",organization_id=self.org_a,
                status="enabled",expected_version=0,
            )
            self.assertEqual(created.status,201)

            denied=self.command(
                c,"partner",self.partner_b,
                action="placement_update",organization_id=self.org_a,
                status="paused",expected_version=1,
            )
            self.assertEqual((denied.status,denied.payload["error"]),(404,"organization_not_found"))

            lead=self.command(
                c,"participant",self.participant,
                action="lead_submit",organization_id=self.org_a,
                request_id="d"*32,kind="materials",consent=True,
            )
            self.assertEqual(lead.status,201)
            lead_id=lead.payload["lead"]["id"]

            a,status=partner_commercial.read(
                c,partner_commercial.ROUTE,"partner",self.partner_a
            )
            self.assertEqual(status,200)
            self.assertIn(self.participant,str(a))

            b,status=partner_commercial.read(
                c,partner_commercial.ROUTE,"partner",self.partner_b
            )
            self.assertEqual(status,200)
            self.assertNotIn(self.participant,str(b))
            self.assertNotIn(self.org_a,str(b))

            withdrawn=self.command(
                c,"participant",self.participant,
                action="lead_withdraw",lead_id=lead_id,
            )
            self.assertEqual(withdrawn.status,200)
            a,_=partner_commercial.read(
                c,partner_commercial.ROUTE,"partner",self.partner_a
            )
            self.assertNotIn(self.participant,str(a))
        finally:
            c.close()

    def test_membership_revocation_immediately_removes_partner_visibility(self):
        c=db.connect()
        try:
            self.command(
                c,"partner",self.partner_a,
                action="placement_update",organization_id=self.org_a,
                status="enabled",expected_version=0,
            )
            self.command(
                c,"participant",self.participant,
                action="lead_submit",organization_id=self.org_a,
                request_id="e"*32,kind="follow_up",consent=True,
            )
            c.execute(
                "UPDATE institutional_memberships SET status='revoked' "
                "WHERE organization_id=? AND account_email=?",
                (self.org_a,self.partner_a),
            )
            c.commit()
            snap,status=partner_commercial.read(
                c,partner_commercial.ROUTE,"partner",self.partner_a
            )
            self.assertEqual(status,200)
            self.assertEqual(snap["organizations"],[])
            denied=self.command(
                c,"partner",self.partner_a,
                action="placement_update",organization_id=self.org_a,
                status="paused",expected_version=1,
            )
            self.assertEqual((denied.status,denied.payload["error"]),(404,"organization_not_found"))
        finally:
            c.close()

    def test_partner_unbinding_revokes_existing_lead_and_placement_access(self):
        c=db.connect()
        try:
            enabled=self.command(
                c,"partner",self.partner_a,action="placement_update",
                organization_id=self.org_a,status="enabled",expected_version=0,
            )
            self.assertEqual(enabled.status,201)
            lead=self.command(
                c,"participant",self.participant,action="lead_submit",
                organization_id=self.org_a,request_id="d"*32,
                kind="materials",consent=True,
            )
            self.assertEqual(lead.status,201)
            lead_id=lead.payload["lead"]["id"]
            c.execute(
                "UPDATE institutional_organizations SET partner_id=NULL WHERE id=?",
                (self.org_a,),
            )
            c.commit()
            hidden,status=partner_commercial.read(
                c,partner_commercial.ROUTE,"partner",self.partner_a
            )
            self.assertEqual(status,200)
            self.assertEqual(hidden["organizations"],[])
            denied=self.command(
                c,"partner",self.partner_a,action="placement_update",
                organization_id=self.org_a,status="paused",expected_version=1,
            )
            self.assertEqual(
                (denied.status,denied.payload["error"]),
                (404,"organization_not_found"),
            )
            new_lead=self.command(
                c,"participant",self.participant,action="lead_submit",
                organization_id=self.org_a,request_id="a"*32,
                kind="follow_up",consent=True,
            )
            self.assertEqual(
                (new_lead.status,new_lead.payload["error"]),
                (404,"organization_not_found"),
            )
            withdrawn=self.command(
                c,"participant",self.participant,action="lead_withdraw",
                lead_id=lead_id,
            )
            self.assertEqual(withdrawn.status,200)
        finally:
            c.close()

    def _race_two_commands(self, actor, payload, synchronize):
        """Two distinct PostgreSQL transactions; no global HTTP mutex."""
        barrier=threading.Barrier(2)
        original=synchronize["original"]
        target=synchronize["target"]
        lock=threading.Lock()
        hits=[0]

        def gated(*args,**kwargs):
            value=original(*args,**kwargs)
            if target(value):
                with lock:
                    hits[0]+=1
                barrier.wait(timeout=12)
            return value

        def worker():
            connection=db.connect()
            try:
                outcome=partner_commercial.handle_command(
                    connection,partner_commercial.ROUTE,actor[0],actor[1],
                    dict(payload),
                )
                if outcome.status<400:
                    connection.commit()
                else:
                    connection.rollback()
                return outcome.status,outcome.payload
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

        with patch.object(partner_commercial,synchronize["name"],side_effect=gated):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first=pool.submit(worker)
                second=pool.submit(worker)
                responses=[first.result(timeout=30),second.result(timeout=30)]
        self.assertEqual(hits[0],2,"race fixture did not synchronize both reads")
        return responses

    def test_concurrent_first_placement_create_has_one_winner(self):
        original=partner_commercial._placement
        results=self._race_two_commands(
            ("partner",self.partner_a),
            {"action":"placement_update","organization_id":self.org_a,
             "status":"enabled","expected_version":0},
            {"name":"_placement","original":original,
             "target":lambda row: row is None},
        )
        self.assertEqual(sorted(status for status,_ in results),[201,409])
        loser=[payload for status,payload in results if status==409][0]
        self.assertEqual(loser["error"],"version_conflict")
        c=db.connect()
        try:
            row=c.execute(
                "SELECT version,status FROM partner_commercial_placements_v1 "
                "WHERE organization_id=?",(self.org_a,),
            ).fetchone()
            self.assertEqual((row["version"],row["status"]),(1,"enabled"))
        finally:
            c.close()

    def test_concurrent_placement_compare_and_swap_rejects_stale_writer(self):
        c=db.connect()
        try:
            initial=self.command(
                c,"partner",self.partner_a,
                action="placement_update",organization_id=self.org_a,
                status="enabled",expected_version=0,
            )
            self.assertEqual(initial.status,201)
        finally:
            c.close()
        original=partner_commercial._placement
        results=self._race_two_commands(
            ("partner",self.partner_a),
            {"action":"placement_update","organization_id":self.org_a,
             "status":"paused","expected_version":1},
            {"name":"_placement","original":original,
             "target":lambda row: row is not None and int(row["version"])==1},
        )
        self.assertEqual(sorted(status for status,_ in results),[200,409])
        self.assertEqual(
            [payload for status,payload in results if status==409][0]["error"],
            "version_conflict",
        )
        c=db.connect()
        try:
            row=c.execute(
                "SELECT version,status FROM partner_commercial_placements_v1 "
                "WHERE organization_id=?",(self.org_a,),
            ).fetchone()
            self.assertEqual((row["version"],row["status"]),(2,"paused"))
        finally:
            c.close()

    def test_concurrent_lead_idempotency_returns_one_original_record(self):
        c=db.connect()
        try:
            created=self.command(
                c,"partner",self.partner_a,
                action="placement_update",organization_id=self.org_a,
                status="enabled",expected_version=0,
            )
            self.assertEqual(created.status,201)
        finally:
            c.close()

        barrier=threading.Barrier(2)
        original=partner_commercial.secrets.token_hex
        hit_lock=threading.Lock()
        hits=[0]

        def gated_token_hex(n):
            with hit_lock:
                hits[0]+=1
            barrier.wait(timeout=12)
            return original(n)

        def worker():
            connection=db.connect()
            try:
                outcome=partner_commercial.handle_command(
                    connection,partner_commercial.ROUTE,
                    "participant",self.participant,
                    {"action":"lead_submit","organization_id":self.org_a,
                     "request_id":"9"*32,"kind":"materials","consent":True},
                )
                if outcome.status<400:
                    connection.commit()
                else:
                    connection.rollback()
                return outcome.status,outcome.payload
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

        with patch.object(partner_commercial.secrets,"token_hex",side_effect=gated_token_hex):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first=pool.submit(worker)
                second=pool.submit(worker)
                responses=[first.result(timeout=30),second.result(timeout=30)]
        self.assertEqual(hits[0],2,"both actors must pass the prior-key read")
        self.assertEqual(sorted(status for status,_ in responses),[200,201])
        self.assertEqual(
            [payload["replayed"] for _,payload in responses].count(True),1
        )
        self.assertEqual(
            len({payload["lead"]["id"] for _,payload in responses}),1
        )
        c=db.connect()
        try:
            row=c.execute(
                "SELECT COUNT(*) n FROM participant_partner_leads_v1 "
                "WHERE email=? AND request_key=?",(self.participant,"9"*32),
            ).fetchone()
            self.assertEqual(int(row["n"]),1)
        finally:
            c.close()


if __name__=="__main__":
    unittest.main()
