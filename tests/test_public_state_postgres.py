"""PostgreSQL 17 proof for hash-bound public-state admission."""
import os
import time
import unittest
import uuid

from app import db, public_state


@unittest.skipUnless(
    os.environ.get("PROMOMED_PUBLIC_STATE_PG_TEST") == "1",
    "dedicated PostgreSQL public-state qualification only",
)
class PublicStatePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if db.backend_name() != "postgres":
            raise RuntimeError("postgres_required")
        cls.c = db.connect()
        db.migrate(cls.c)

    @classmethod
    def tearDownClass(cls):
        cls.c.rollback()
        cls.c.close()

    def setUp(self):
        self.suffix = uuid.uuid4().hex[:10]
        self.content_id = "PUBC-" + self.suffix
        self.event_id = "PUBE-" + self.suffix
        self.now = int(time.time())
        self.c.execute(
            "INSERT INTO content_catalog"
            "(id,kind,theme,title,dek,duration,author,reviewer,partner,status) "
            "VALUES(?,?,?,?,?,?,?,?,?,'published')",
            (self.content_id, "guide", "science", "PG public title",
             "PG public summary", "5 min", "Editorial", "reviewed", ""),
        )
        self.c.execute(
            'INSERT INTO program_items(id,start,"end",venue,track,format,title,audience,'
            "capacity,stream,replay,partner) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (self.event_id, "10:00", "10:40", "Hall A", "Science", "talk",
             "PG public event", "all", 100, 1, 1, ""),
        )
        self.c.commit()

    def tearDown(self):
        self.c.rollback()
        self.c.execute(
            "DELETE FROM public_artifact_admissions WHERE artifact_ref IN (?,?)",
            (self.content_id, self.event_id),
        )
        self.c.execute("DELETE FROM publication_holds WHERE artifact_ref IN (?,?)",
                       (self.content_id, self.event_id))
        self.c.execute("DELETE FROM content_catalog WHERE id=?", (self.content_id,))
        self.c.execute("DELETE FROM program_items WHERE id=?", (self.event_id,))
        self.c.commit()

    def _row(self, kind):
        if kind == "content":
            return self.c.execute(
                "SELECT id,kind,theme,title,dek,duration,author,partner "
                "FROM content_catalog WHERE id=?", (self.content_id,)
            ).fetchone()
        return self.c.execute(
            'SELECT id,start,"end",venue,track,format,title,audience,capacity,'
            "stream,replay,partner FROM program_items WHERE id=?", (self.event_id,)
        ).fetchone()

    def _admit(self, kind, ref):
        digest = public_state.payload_sha256(kind, self._row(kind))
        self.c.execute(
            "INSERT INTO public_artifact_admissions("
            "artifact_kind,artifact_ref,payload_sha256,status,reviewer_ref,source_ref,"
            "admitted_at,demo_only) VALUES(?,?,?,'admitted','review:pg','source:pg',?,0)",
            (kind, ref, digest, self.now),
        )
        self.c.commit()
        return digest

    def test_exact_version_only_and_withdrawal(self):
        before = public_state.snapshot(self.c)
        self.assertNotIn(self.content_id, str(before))
        self.assertNotIn(self.event_id, str(before))

        self._admit("content", self.content_id)
        event_hash = self._admit("event", self.event_id)
        admitted = public_state.snapshot(self.c)
        self.assertEqual(
            [x["id"] for x in admitted["content"] if x["id"] == self.content_id],
            [self.content_id],
        )
        self.assertEqual(
            [x["id"] for x in admitted["agenda"] if x["id"] == self.event_id],
            [self.event_id],
        )

        self.c.execute("UPDATE content_catalog SET title=? WHERE id=?",
                       ("Changed after admission", self.content_id))
        self.c.execute(
            "UPDATE public_artifact_admissions SET status='withdrawn',withdrawn_at=? "
            "WHERE artifact_kind='event' AND artifact_ref=? AND payload_sha256=?",
            (self.now + 1, self.event_id, event_hash),
        )
        self.c.commit()
        after = public_state.snapshot(self.c)
        self.assertNotIn(self.content_id, str(after))
        self.assertNotIn(self.event_id, str(after))


if __name__ == "__main__":
    unittest.main()
