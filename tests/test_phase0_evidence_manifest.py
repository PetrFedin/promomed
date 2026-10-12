import hashlib
import json
import unittest
from pathlib import Path

from ops.phase0_evidence_manifest import InvalidAdmissionEvidence, build_manifest

ROOT = Path(__file__).resolve().parents[1]
SHA = "3471d05af97fe65e9e08b9da03a4c68bf81a2a78"


def fingerprint():
    counts = {"accounts": 0, "_schema_migrations": 2, "state": 1}
    versions = ["001", "002"]
    canonical = json.dumps(
        {"counts": counts, "migration_versions": versions},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return {
        "backend": "postgres",
        "counts": counts,
        "migration_versions": versions,
        "catalog_sha256": hashlib.sha256(canonical).hexdigest(),
    }


class Phase0EvidenceTruthTests(unittest.TestCase):
    def test_source_restore_pass_does_not_claim_live_production(self):
        output = build_manifest(fingerprint(), fingerprint(), SHA)
        self.assertEqual(output["proof_kind"], "repository_postgres_source_restore_only")
        self.assertEqual(output["backup_restore"], "pass")
        self.assertEqual(output["catalog_equivalence"], "pass")
        self.assertEqual(output["live_health"], "not_verified")
        self.assertEqual(output["live_ready"], "not_verified")
        self.assertEqual(output["live_production_ready"], "not_verified")
        self.assertEqual(output["phase0_end_to_end"], "not_complete")
        self.assertEqual(output["external_participation_acceptance"], "GATED")
        self.assertNotIn("production_ready", output)

    def test_mismatch_fails_closed(self):
        restored = fingerprint()
        restored["counts"] = {**restored["counts"], "accounts": 1}
        with self.assertRaisesRegex(InvalidAdmissionEvidence, "mismatch"):
            build_manifest(fingerprint(), restored, SHA)

    def test_fingerprint_and_sha_are_validated(self):
        bad = fingerprint()
        bad["catalog_sha256"] = "invalid"
        with self.assertRaises(InvalidAdmissionEvidence):
            build_manifest(bad, fingerprint(), SHA)
        with self.assertRaisesRegex(InvalidAdmissionEvidence, "invalid_repository_sha"):
            build_manifest(fingerprint(), fingerprint(), "not-a-sha")

    def test_invalid_database_metadata_rejected(self):
        bad = fingerprint()
        bad["backend"] = "sqlite"
        with self.assertRaisesRegex(InvalidAdmissionEvidence, "must_be_postgres"):
            build_manifest(bad, fingerprint(), SHA)
        bad = fingerprint()
        bad["counts"]["accounts"] = -1
        with self.assertRaisesRegex(InvalidAdmissionEvidence, "invalid_counts"):
            build_manifest(bad, fingerprint(), SHA)

    def test_no_credentials_or_row_contents_in_manifest(self):
        source = fingerprint()
        source["DATABASE_URL"] = "postgresql://private:secret@host/db"
        source["rows"] = ["sensitive patient info"]
        output = build_manifest(source, fingerprint(), SHA)
        serialized = json.dumps(output)
        self.assertNotIn("private", serialized)
        self.assertNotIn("secret", serialized)
        self.assertNotIn("patient", serialized)

    def test_manual_workflow_uses_repository_only_manifest(self):
        workflow = (ROOT / ".github/workflows/phase0-postgres-admission.yml").read_text(encoding="utf-8")
        self.assertIn("python ops/phase0_evidence_manifest.py", workflow)
        self.assertNotIn('"production_ready": True', workflow)
        self.assertIn("Admit restored PostgreSQL", workflow)
        self.assertIn("Compare source and restored catalog fingerprints", workflow)


if __name__ == "__main__":
    unittest.main()
