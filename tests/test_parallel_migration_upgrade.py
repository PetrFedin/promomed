"""P0: upgrade an existing 001-025 database to every current migration.

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
    expected_versions = {p.stem for p in all_migrations}
    assert '036_event_registration_transition_history' in expected_versions
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
                "032_participant_self_registration",
                "033_event_registration_authority", "034_partner_commercial_authority", "035_partner_appointment_authority")).issubset(set(pending["missing"])), pending

    upgraded = db.migrate(c)
    assert upgraded["schema_ready"] and not upgraded["missing"], upgraded
    assert not upgraded["checksum_drift"], upgraded
    assert set(upgraded["applied"]) == expected_versions, upgraded
    assert set(upgraded["available"]) == expected_versions, upgraded
    assert c.execute(
        "SELECT v FROM state WHERE k=?", ("upgrade-sentinel",)
    ).fetchone()["v"] == "before-and-after"

    expected = ("commercial_contract_versions", "commercial_evidence_events",
                "commercial_evidence_audit", "partner_collab_projects",
                "partner_collab_task_receipts", "partner_collab_project_scopes",
                "institutional_organizations", "auth_sessions", "personal_notes_v1",
                "public_artifact_admissions", "participant_registration_requests", "event_editions_v1",
                "participant_event_registrations_v1", "partner_commercial_placements_v1",
                "participant_partner_leads_v1", "partner_appointment_slots_v1",
                "participant_partner_appointments_v1",
                "event_registration_transitions_v1")
    for table in expected:
        row = c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        assert row, table

    # The newly installed transition triggers must work on an upgraded
    # database, rather than only on a fresh empty schema.
    event_id = "UPGRADE-EVENT-01"
    email = "migration-participant@example.test"
    c.execute(
        "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
        "VALUES(?,?,'participant',?,'active',?,?)",
        (email, "migration-fixture", "Migration Participant", 1700000000, 1700000000),
    )
    c.execute(
        "INSERT INTO event_editions_v1("
        "id,title,starts_at,registration_status,capacity,demo_only,created_at,updated_at"
        ") VALUES(?,?,?,'open',1,0,?,?)",
        (event_id, "Upgrade event", 2000000000, 1700000000, 1700000000),
    )
    c.execute(
        "INSERT INTO participant_event_registrations_v1("
        "event_id,email,status,requested_at,updated_at,source"
        ") VALUES(?,?, 'waitlist', ?,?,'participant')",
        (event_id,email,1700000000,1700000000),
    )
    c.execute(
        "UPDATE participant_event_registrations_v1 "
        "SET status='confirmed',updated_at=? WHERE event_id=? AND email=?",
        (1700001000,event_id,email),
    )
    c.commit()
    transitions = list(c.execute(
        "SELECT transition_no,previous_status,next_status "
        "FROM event_registration_transitions_v1 "
        "WHERE event_id=? AND email=? ORDER BY transition_no",
        (event_id,email),
    ))
    assert [(r["transition_no"],r["previous_status"],r["next_status"])
            for r in transitions] == [
        (1,None,"waitlist"),(2,"waitlist","confirmed")
    ], transitions

    version_rows = list(c.execute(
        "SELECT version FROM _schema_migrations WHERE version LIKE '026_%' ORDER BY version"
    ))
    assert [r["version"] for r in version_rows] == [
        "026_commercial_evidence_ledger", "026_partner_collaboration"
    ], version_rows
    repeated = db.migrate(c)
    assert repeated["schema_ready"] and not repeated["checksum_drift"], repeated
    assert set(repeated["applied"]) == expected_versions, repeated
    assert set(repeated["available"]) == expected_versions, repeated
    assert c.execute(
        "SELECT status FROM participant_event_registrations_v1 WHERE event_id=? AND email=?",
        (event_id,email),
    ).fetchone()["status"] == "confirmed"
    assert c.execute(
        "SELECT COUNT(*) n FROM event_registration_transitions_v1 "
        "WHERE event_id=? AND email=?",
        (event_id,email),
    ).fetchone()["n"] == 2
    assert c.execute(
        "SELECT v FROM state WHERE k=?", ("upgrade-sentinel",)
    ).fetchone()["v"] == "before-and-after"
finally:
    c.close()
'''


class ParallelMigrationUpgradeTests(unittest.TestCase):
    def test_existing_25_migrations_upgrade_and_reapply_without_loss(self):
        with tempfile.TemporaryDirectory() as work:
            db_path = str(Path(work) / "promomed-25-to-current.sqlite")
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
