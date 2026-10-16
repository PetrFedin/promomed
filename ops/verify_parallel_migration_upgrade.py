"""Isolated CI-only PostgreSQL 17 legacy-to-parallel-migration upgrade proof.

Do not point this at a production DB. Requires a *separate, empty, local*
GitHub Actions service-container database named promomed_upgrade_ci.
The workflow creates that database; this script never creates or drops it.
"""
import os
from unittest.mock import patch
from urllib.parse import urlparse

from app import db

SENTINEL = "ci-upgrade-25-to-30-preserve"
NEXT = {
    "026_commercial_evidence_ledger",
    "026_partner_collaboration",
    "027_partner_task_execution",
    "028_partner_organization_tenancy",
    "029_auth_session_revocation",
    "030_personal_workspace_notes",
    "031_public_artifact_admission",
    "032_participant_self_registration",
    "033_event_registration_authority",
    "034_partner_commercial_authority",
    "035_partner_appointment_authority",
}
TABLES = {
    "commercial_contract_versions",
    "commercial_evidence_events",
    "commercial_evidence_audit",
    "partner_collab_projects",
    "partner_collab_tasks",
    "partner_collab_task_execution",
    "partner_collab_task_receipts",
    "partner_collab_project_scopes",
    "institutional_memberships",
    "auth_sessions",
    "personal_notes_v1",
    "public_artifact_admissions",
    "participant_registration_requests",
    "event_editions_v1",
    "participant_event_registrations_v1",
    "partner_commercial_placements_v1",
    "participant_partner_leads_v1",
    "partner_appointment_slots_v1",
    "participant_partner_appointments_v1",
}


def fail_closed():
    url = urlparse(os.environ.get("DATABASE_URL", ""))
    if not (
        os.environ.get("PROMOMED_CONFIRM_ISOLATED_UPGRADE_TEST") == "true"
        and url.scheme in ("postgres", "postgresql")
        and url.hostname in ("127.0.0.1", "localhost")
        and url.path == "/promomed_upgrade_ci"
        and db.backend_name() == "postgres"
        and db.require_postgres()
        and not db.demo_seed_enabled()
    ):
        raise SystemExit("isolated_ci_postgres_upgrade_only")


def run():
    fail_closed()
    conn = db.connect()
    try:
        original = list(db._migration_files())
        legacy = [p for p in original if p.stem[:3].isdigit()
                  and int(p.stem[:3]) <= 25]
        if len(legacy) != 25:
            raise RuntimeError("unexpected_legacy_migration_set")
        # For this isolated empty database, only the historical migrations
        # are visible during initial admission.
        with patch.object(db, "_migration_files", return_value=legacy):
            status = db.migrate(conn)
            assert status["schema_ready"] and len(status["applied"]) == 25, status

        conn.execute(
            "INSERT INTO state(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=EXCLUDED.v",
            (SENTINEL, "preserve-me"),
        )
        conn.commit()
        pending = db.migration_status(conn)
        assert NEXT.issubset(set(pending["missing"])), pending
        assert not pending["checksum_drift"], pending

        upgraded = db.migrate(conn)
        assert upgraded["schema_ready"] and not upgraded["checksum_drift"], upgraded
        assert len(upgraded["applied"]) == len(original) == 36, upgraded
        assert conn.execute(
            "SELECT v FROM state WHERE k=?", (SENTINEL,)
        ).fetchone()["v"] == "preserve-me"

        rows = conn.execute(
            "SELECT version FROM _schema_migrations "
            "WHERE version LIKE ? ORDER BY version",
            ("026_%",),
        )
        assert [r["version"] for r in rows] == [
            "026_commercial_evidence_ledger", "026_partner_collaboration"
        ]
        schema = {
            row["table_name"] for row in conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema=current_schema()"
            )
        }
        assert TABLES.issubset(schema), TABLES - schema
        rerun = db.migrate(conn)
        assert rerun["schema_ready"] and not rerun["checksum_drift"], rerun
        assert len(rerun["applied"]) == 36, rerun
        assert conn.execute(
            "SELECT v FROM state WHERE k=?", (SENTINEL,)
        ).fetchone()["v"] == "preserve-me"
        print("ISOLATED POSTGRES LEGACY 001-025 TO PARALLEL 026-029 PASS")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
