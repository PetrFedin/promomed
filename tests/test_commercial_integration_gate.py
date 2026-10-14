"""Verify the combined DB parser and candidate commercial migration gate.

This runs without account access or actual payment documents. Existing
PostgreSQL integration jobs separately apply migration 026 to PostgreSQL 17.
"""
import unittest
from pathlib import Path

from app import db, commercial_evidence_ledger

ROOT = Path(__file__).resolve().parents[1]


class CommercialIntegrationGateTests(unittest.TestCase):
    def test_postgres_026_survives_comment_semicolon_and_function_bodies(self):
        source = (ROOT / "migrations" / "postgres" /
                  "026_commercial_evidence_ledger.sql").read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS commercial_contract_versions", source)
        self.assertIn("CREATE TABLE IF NOT EXISTS commercial_evidence_events", source)
        self.assertIn("CREATE TABLE IF NOT EXISTS commercial_evidence_audit", source)
        parsed = db._split_postgres_script(source)
        qualified = db._split_postgres_script(
            "-- Qualifier; do not interpret as executable SQL; migration 026\n" + source
        )
        self.assertEqual(qualified, parsed)
        self.assertGreaterEqual(len(parsed), 9)
        self.assertTrue(all("Qualifier;" not in statement for statement in qualified))
        functions = [part for part in parsed if
                     "CREATE OR REPLACE FUNCTION promomed_block_commercial" in part]
        self.assertEqual(len(functions), 1)
        self.assertIn("RAISE EXCEPTION 'immutable_commercial_evidence';", functions[0])
        self.assertIn("END;", functions[0])
        self.assertIn("$$ LANGUAGE plpgsql", functions[0])

    def test_migration_026_is_mirrored_and_operations_stay_candidate_only(self):
        for backend in ("sqlite", "postgres"):
            path = (ROOT / "migrations" / backend /
                    "026_commercial_evidence_ledger.sql")
            self.assertTrue(path.is_file(), path)
            source = path.read_text(encoding="utf-8")
            self.assertIn("state TEXT NOT NULL DEFAULT 'candidate'", source)
            self.assertIn("CHECK(state='candidate')", source)
            self.assertIn("CREATE TABLE IF NOT EXISTS commercial_evidence_audit", source)
        self.assertEqual(commercial_evidence_ledger.VERSION,
                         "promomed-contract-cash-candidate-ledger-v1")
        self.assertIn("finance_review", commercial_evidence_ledger.ALLOWED_TYPES)
        self.assertNotIn("finance_approved", commercial_evidence_ledger.ALLOWED_TYPES)
        self.assertNotIn("capital_release", commercial_evidence_ledger.ALLOWED_TYPES)


if __name__ == "__main__":
    unittest.main()
