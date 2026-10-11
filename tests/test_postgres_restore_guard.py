import unittest
from unittest.mock import patch

from ops import postgres_restore_guard as guard


class Cursor:
    def __init__(self, name, objects):
        self.responses = [(name,), (objects,)]
        self.sql = []

    def execute(self, sql):
        self.sql.append(sql)

    def fetchone(self):
        return self.responses.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class Connection:
    def __init__(self, name, objects):
        self.cur = Cursor(name, objects)

    def cursor(self):
        return self.cur

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class RestoreGuardTests(unittest.TestCase):
    SOURCE = "postgresql://user:password@db.example.test:5432/promomed"

    def connector(self, actual, objects):
        def connect(url, **kwargs):
            self.assertEqual(kwargs["connect_timeout"], 10)
            return Connection(actual, objects)
        return connect

    def test_source_and_destination_same_database_refused(self):
        with self.assertRaisesRegex(guard.UnsafeRestoreTarget, "same endpoint"):
            guard.require_empty_isolated_restore_target(
                self.SOURCE, self.SOURCE, connector=self.connector("promomed", 0)
            )

    def test_missing_or_ambiguous_address_refused(self):
        for target in (
            "postgresql:///promomed_restore",
            "postgresql://db.example.test",
            "postgresql://db.example.test/promomed_restore?dbname=other",
            "postgresql://db.example.test/promomed_restore?host=elsewhere",
        ):
            with self.subTest(target=target), self.assertRaises(guard.UnsafeRestoreTarget):
                guard.require_empty_isolated_restore_target(self.SOURCE, target, connector=self.connector("promomed_restore", 0))

    def test_unrelated_database_name_refused(self):
        with self.assertRaisesRegex(guard.UnsafeRestoreTarget, "must start"):
            guard.require_empty_isolated_restore_target(
                self.SOURCE, "postgresql://db.example.test/mfw_postgres",
                connector=self.connector("mfw_postgres", 0)
            )

    def test_actual_database_name_is_verified(self):
        with self.assertRaisesRegex(guard.UnsafeRestoreTarget, "differs"):
            guard.require_empty_isolated_restore_target(
                self.SOURCE, "postgresql://db.example.test/promomed_restore",
                connector=self.connector("different_restore", 0)
            )

    def test_non_empty_target_refused_before_restore(self):
        with self.assertRaisesRegex(guard.UnsafeRestoreTarget, "contains user objects"):
            guard.require_empty_isolated_restore_target(
                self.SOURCE, "postgresql://db.example.test/promomed_restore",
                connector=self.connector("promomed_restore", 3)
            )

    def test_connection_error_fails_closed_without_leaking_credentials(self):
        def bad_connection(url, **kwargs):
            raise RuntimeError("password-do-not-print")
        with self.assertRaises(guard.UnsafeRestoreTarget) as ctx:
            guard.require_empty_isolated_restore_target(
                self.SOURCE, "postgresql://db.example.test/promomed_restore",
                connector=bad_connection
            )
        self.assertNotIn("password-do-not-print", str(ctx.exception))

    def test_empty_explicit_restore_target_admitted(self):
        outcome = guard.require_empty_isolated_restore_target(
            self.SOURCE, "postgresql://db.example.test/promomed_admission_restore",
            connector=self.connector("promomed_admission_restore", 0)
        )
        self.assertTrue(outcome["target_empty"])
        self.assertEqual(outcome["target_database"], "promomed_admission_restore")

    def test_pg_restore_command_is_atomic_and_non_destructive(self):
        from ops import db_backup_restore
        captured = []
        with patch.object(db_backup_restore, "require_binary", return_value="pg_restore"), patch.object(
            db_backup_restore.subprocess, "run", side_effect=lambda *a, **k: captured.append((a, k))
        ):
            db_backup_restore.restore_postgres("/tmp/example.dump", "postgresql://db.example.test/promomed_restore")
        cmd = captured[0][0][0]
        self.assertIn("--single-transaction", cmd)
        self.assertIn("--exit-on-error", cmd)
        self.assertNotIn("--clean", cmd)
        self.assertNotIn("--if-exists", cmd)


if __name__ == "__main__":
    unittest.main()
