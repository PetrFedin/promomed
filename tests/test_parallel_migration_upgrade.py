"""P0: upgrade an existing Promomed 001-025 database to BOTH 026 migrations.

Runs in its own SQLite subprocess so other test suites' selected backends,
connection pools, and module globals cannot change this fixture's behavior.
The PostgreSQL pipeline continues to prove a clean PG17 installation/restore;
provider-live upgrade remains separately gated.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SCRIPT = r'''
from unittest.mock import patch
from app import db

c = db.connect()
try:
    all_migrations = list(db._migration_files())
    legacy = [p for p in all_migrations if p.stem[:3].isdigit() and int(p.stem[:3]) <= 25]
    assert len(legacy) == 25, [p.name for p in legacy]
    with patch.object(db, "_migration_files", return_value=legacy):
        old = db.migrate(c)
        assert old["schema_ready"], old
        assert len(old["applied"]) == 25, old
        c.execute(
            "INSERT INTO state(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
            ("upgrade-sentinel", "before-and-after"),
        )
        c.commit()

    pending = db.migration_status(c)
    assert pending["schema_ready"] is False, pending
    assert set(("026_commercial_evidence_ledger",
                "026_partner_collaboration",
                "027_partner_task_execution",
                "028_partner_organization_tenancy",
                "029_auth_session_revocation", "030_personal_workspace_notes",
                "031_public_artifact_admission",
                "032_participant_self_registration")).issubset(set(pending["missing"])), pending

    upgraded = db.migrate(c)
    assert upgraded["schema_ready"] and not upgraded["missing"], upgraded
    assert not upgraded["checksum_drift"], upgraded
    assert len(upgraded["applied"]) == 33, upgraded
    assert c.execute(
        "SELECT v FROM state WHERE k=?", ("upgrade-sentinel",)
    ).fetchone()["v"] == "before-and-after"

    expected = ("commercial_contract_versions", "commercial_evidence_events",
                "commercial_evidence_audit", "partner_collab_projects",
                "partner_collab_task_receipts", "partner_collab_project_scopes",
                "institutional_organizations", "auth_sessions", "personal_notes_v1",
                "public_artifact_admissions", "participant_registration_requests")
    for table in expected:
        row = c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        assert row, table

    version_rows = list(c.execute(
        "SELECT version FROM _schema_migrations WHERE version LIKE '026_%' ORDER BY version"
    ))
    assert [r["version"] for r in version_rows] == [
        "026_commercial_evidence_ledger", "026_partner_collaboration"
    ], version_rows
    repeated = db.migrate(c)
    assert repeated["schema_ready"] and not repeated["checksum_drift"], repeated
    assert len(repeated["applied"]) == 33, repeated
    assert c.execute(
        "SELECT v FROM state WHERE k=?", ("upgrade-sentinel",)
    ).fetchone()["v"] == "before-and-after"
finally:
    c.close()
'''


class ParallelMigrationUpgradeTests(unittest.TestCase):
    def test_existing_25_migrations_upgrade_and_reapply_without_loss(self):
        with tempfile.TemporaryDirectory() as work:
            db_path = str(Path(work) / "promomed-25-to-30.sqlite")
            env = dict(os.environ)
            env.update({
                "DATABASE_URL": "",
                "SQLITE_PATH": db_path,
                "PROMOMED_REQUIRE_POSTGRES": "false",
                "PROMOMED_SEED_DEMO": "false",
            })
            result = subprocess.run(
                [sys.executable, "-c", SCRIPT],
                cwd=str(ROOT), env=env,
                capture_output=True, text=True, timeout=90,
                check=False,
            )
            self.assertEqual(
                result.returncode, 0,
                "Parallel-migration SQLite upgrade failed:\n"
                + result.stdout[-3000:] + "\n" + result.stderr[-5000:],
            )


if __name__ == "__main__":
    unittest.main()
