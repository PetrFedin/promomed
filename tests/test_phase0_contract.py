import importlib
import os
import unittest

class Phase0ContractTest(unittest.TestCase):
    def test_postgres_is_selected_by_database_url(self):
        os.environ["DATABASE_URL"] = "postgresql://example.invalid/promomed"
        import app.db.core as core
        importlib.reload(core)
        self.assertEqual(core.backend_name(), "postgres")

    def test_sqlite_is_explicit_fallback(self):
        os.environ.pop("DATABASE_URL", None)
        import app.db.core as core
        importlib.reload(core)
        self.assertEqual(core.backend_name(), "sqlite")

    def test_legacy_end_is_quoted_for_postgres(self):
        os.environ["DATABASE_URL"] = "postgresql://example.invalid/promomed"
        import app.db.core as core
        importlib.reload(core)
        sql = core.adapt_sql(
            "INSERT OR IGNORE INTO program_items(id,start,end,venue) VALUES(?,?,?,?)"
        )
        self.assertIn('start,"end",venue', sql)
        self.assertNotIn("start,end,venue", sql)

    def test_qualified_end_is_quoted_for_postgres(self):
        os.environ["DATABASE_URL"] = "postgresql://example.invalid/promomed"
        import app.db.core as core
        importlib.reload(core)
        sql = core.adapt_sql("SELECT p.start,p.end FROM program_items p")
        self.assertIn('p."end"', sql)

if __name__ == "__main__":
    unittest.main()
