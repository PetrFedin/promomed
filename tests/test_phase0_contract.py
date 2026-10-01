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

if __name__ == "__main__":
    unittest.main()
