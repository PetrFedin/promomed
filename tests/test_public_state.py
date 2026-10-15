"""PUB-01: only exact, explicitly admitted public artifact versions are exposed."""
import importlib
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import public_state


class PublicStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "SQLITE_PATH": str(Path(self.temp.name) / "public-state.db"),
            "DATABASE_URL": "",
            "PROMOMED_SEED_DEMO": "false",
            "PROMOMED_REQUIRE_POSTGRES": "false",
        })
        self.env.start()
        from app import db
        importlib.reload(db)
        importlib.reload(public_state)
        self.db = db
        self.c = db.connect()
        db.migrate(self.c)
        self.now = int(time.time())
        self.c.execute(
            "INSERT INTO content_catalog"
            "(id,kind,theme,title,dek,duration,author,reviewer,partner,status) "
            "VALUES('C1','guide','science','Public title','Public summary','5 min',"
            "'Editorial','reviewed','', 'published')"
        )
        self.c.execute(
            'INSERT INTO program_items(id,start,"end",venue,track,format,title,audience,'
            "capacity,stream,replay,partner) "
            "VALUES('E1','10:00','10:40','Hall A','Science','talk','Public event',"
            "'all',100,1,1,'')"
        )
        self.c.commit()

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.temp.cleanup()

    def row(self, kind):
        if kind == "content":
            return self.c.execute(
                "SELECT id,kind,theme,title,dek,duration,author,partner "
                "FROM content_catalog WHERE id='C1'"
            ).fetchone()
        return self.c.execute(
            'SELECT id,start,"end",venue,track,format,title,audience,capacity,stream,replay,partner '
            "FROM program_items WHERE id='E1'"
        ).fetchone()

    def admit(self, kind, ref, *, demo_only=0):
        digest = public_state.payload_sha256(kind, self.row(kind))
        self.c.execute(
            "INSERT INTO public_artifact_admissions("
            "artifact_kind,artifact_ref,payload_sha256,status,reviewer_ref,source_ref,"
            "admitted_at,demo_only) VALUES(?,?,?,'admitted','review:test','source:test',?,?)",
            (kind, ref, digest, self.now, demo_only),
        )
        self.c.commit()
        return digest

    def test_existing_rows_are_private_by_default(self):
        d = public_state.snapshot(self.c)
        self.assertEqual(d["content"], [])
        self.assertEqual(d["agenda"], [])
        self.assertEqual(d["counts"], {"content": 0, "agenda": 0})

    def test_exact_admissions_expose_only_bounded_public_fields(self):
        ch = self.admit("content", "C1")
        eh = self.admit("event", "E1")
        d = public_state.snapshot(self.c)
        self.assertEqual([x["id"] for x in d["content"]], ["C1"])
        self.assertEqual([x["id"] for x in d["agenda"]], ["E1"])
        self.assertEqual(d["content"][0]["publication"]["payloadSha256"], ch)
        self.assertEqual(d["agenda"][0]["publication"]["payloadSha256"], eh)
        self.assertNotIn("reviewer", d["content"][0])
        self.assertNotIn("status", d["content"][0])
        self.assertNotIn("email", str(d).lower())
        self.assertNotIn("revenue", str(d).lower())

    def test_any_payload_change_invalidates_old_admission(self):
        self.admit("content", "C1")
        self.c.execute("UPDATE content_catalog SET title='Changed after approval' WHERE id='C1'")
        self.c.commit()
        self.assertEqual(public_state.snapshot(self.c)["content"], [])

    def test_active_hold_blocks_even_exact_admission(self):
        self.admit("content", "C1")
        self.c.execute(
            "INSERT INTO publication_holds("
            "id,event_id,artifact_kind,artifact_ref,reason,status,placed_at,placed_by,demo_only"
            ") VALUES('H1','EV1','content','C1','source changed','active',?,'governance',0)",
            (self.now,),
        )
        self.c.commit()
        self.assertEqual(public_state.snapshot(self.c)["content"], [])

    def test_non_published_content_cannot_be_admitted_by_hash_alone(self):
        self.c.execute("UPDATE content_catalog SET status='review' WHERE id='C1'")
        self.c.commit()
        self.admit("content", "C1")
        self.assertEqual(public_state.snapshot(self.c)["content"], [])

    def test_withdrawal_removes_public_artifact(self):
        digest = self.admit("event", "E1")
        self.c.execute(
            "UPDATE public_artifact_admissions SET status='withdrawn',withdrawn_at=? "
            "WHERE artifact_kind='event' AND artifact_ref='E1' AND payload_sha256=?",
            (self.now + 1, digest),
        )
        self.c.commit()
        self.assertEqual(public_state.snapshot(self.c)["agenda"], [])

    def test_demo_only_admission_is_not_valid_in_non_demo_runtime(self):
        self.admit("event", "E1", demo_only=1)
        self.assertEqual(public_state.snapshot(self.c)["agenda"], [])

    def test_query_is_rejected_before_database_open(self):
        with patch("app.public_state.db.connect", side_effect=AssertionError("DB opened")):
            self.assertEqual(
                public_state.serve("/api/public-state/v1?kind=hidden"),
                ({"error": "unsupported_query"}, 422),
            )

    def test_http_public_state_runs_before_authentication(self):
        import server
        h = SimpleNamespace(
            path="/api/public-state/v1",
            out=lambda value, status=200: (value, status),
        )
        expected = {"version": "public-state-v1"}
        with patch("server.auth", side_effect=AssertionError("auth queried")):
            with patch("server.serve_public_state", return_value=(expected, 200)):
                self.assertEqual(server.H.do_GET(h), (expected, 200))


if __name__ == "__main__":
    unittest.main()
