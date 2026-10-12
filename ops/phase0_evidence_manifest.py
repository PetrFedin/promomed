"""Repository-only Phase 0 proof. Deliberately not a live Render admission verdict."""

import json
import os
import re
import sys
from pathlib import Path

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_GIT_SHA = re.compile(r"^[a-f0-9]{40}$")


class InvalidAdmissionEvidence(ValueError):
    pass


def build_manifest(source, restored, git_sha):
    """Emit metadata only; database credentials and row contents are never included."""
    if not isinstance(git_sha, str) or not _GIT_SHA.fullmatch(git_sha):
        raise InvalidAdmissionEvidence("invalid_repository_sha")
    for name, record in (("source", source), ("restore", restored)):
        if not isinstance(record, dict) or record.get("backend") != "postgres":
            raise InvalidAdmissionEvidence(f"{name}_must_be_postgres")
        if not isinstance(record.get("catalog_sha256"), str) or not _SHA256.fullmatch(record["catalog_sha256"]):
            raise InvalidAdmissionEvidence(f"{name}_invalid_fingerprint")
        counts = record.get("counts")
        versions = record.get("migration_versions")
        if not isinstance(counts, dict) or not counts or any(
            not isinstance(k, str) or not k or type(v) is not int or v < 0
            for k, v in counts.items()
        ):
            raise InvalidAdmissionEvidence(f"{name}_invalid_counts")
        if not isinstance(versions, list) or not versions or any(
            not isinstance(v, str) or not v for v in versions
        ):
            raise InvalidAdmissionEvidence(f"{name}_invalid_migrations")

    for key in ("catalog_sha256", "counts", "migration_versions"):
        if source[key] != restored[key]:
            raise InvalidAdmissionEvidence("source_restore_evidence_mismatch")

    return {
        "proof_kind": "repository_postgres_source_restore_only",
        "repository_sha": git_sha,
        "source_catalog_sha256": source["catalog_sha256"],
        "restore_catalog_sha256": restored["catalog_sha256"],
        "migration_versions": source["migration_versions"],
        "backup_restore": "pass",
        "catalog_equivalence": "pass",
        "source_and_restore_ownership": "requires_independent_operator_verification",
        "render_deployment_sha": "not_verified",
        "live_health": "not_verified",
        "live_ready": "not_verified",
        "live_production_ready": "not_verified",
        "phase0_end_to_end": "not_complete",
        "external_participation_acceptance": "GATED",
    }


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: phase0_evidence_manifest.py SOURCE_JSON RESTORE_JSON")
    try:
        source = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        restored = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        output = build_manifest(source, restored, os.environ.get("GITHUB_SHA", ""))
    except (OSError, ValueError, TypeError):
        # Fail closed without echoing paths, DSNs, exception text, or document contents.
        raise SystemExit("phase0_evidence_manifest_validation_failed")
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
