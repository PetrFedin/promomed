import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db

TABLES = (
    "_schema_migrations",
    "state",
    "auth_sessions",
    "program_items",
    "content_catalog",
    "product_catalog",
    "speakers",
    "partners",
    "registrations",
    "bookings",
    "session_attendance",
    "events",
    "notifications",
    "direct_messages",
)


def main():
    if db.backend_name() != "postgres":
        raise SystemExit("PostgreSQL backend required")
    c = db.connect()
    try:
        counts = {}
        for table in TABLES:
            counts[table] = int(c.execute(f"SELECT COUNT(*) n FROM {table}").fetchone()["n"])
        versions = [r["version"] for r in c.execute(
            "SELECT version FROM _schema_migrations ORDER BY version"
        )]
    finally:
        c.close()

    canonical = json.dumps(
        {"counts": counts, "migration_versions": versions},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    print(json.dumps({
        "backend": "postgres",
        "counts": counts,
        "migration_versions": versions,
        "catalog_sha256": hashlib.sha256(canonical).hexdigest(),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
