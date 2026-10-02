import json
import os
import secrets
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db


def fail(code, **extra):
    payload = {"ok": False, "error": code}
    payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False))
    raise SystemExit(1)


def main():
    if db.backend_name() != "postgres":
        fail("postgres_required", backend=db.backend_name())
    if not db.require_postgres():
        fail("require_postgres_flag_required")
    if db.demo_seed_enabled():
        fail("demo_seed_must_be_disabled")

    migration = db.migrate()
    ready = db.readiness()
    if not migration["schema_ready"]:
        fail("schema_not_ready", migration=migration)
    if migration["checksum_drift"]:
        fail("migration_checksum_drift", drift=migration["checksum_drift"])
    if not ready["ready"] or not ready["production_ready"]:
        fail("production_readiness_failed", readiness=ready)

    probe_key = "phase0_admission_" + secrets.token_hex(8)
    probe_value = str(int(time.time()))
    c = db.connect()
    try:
        c.execute(
            "INSERT INTO state(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
            (probe_key, probe_value),
        )
        row = c.execute("SELECT v FROM state WHERE k=?", (probe_key,)).fetchone()
        if not row or str(row["v"]) != probe_value:
            c.rollback()
            fail("write_probe_readback_failed")
        c.execute("DELETE FROM state WHERE k=?", (probe_key,))
        c.commit()
    except Exception as exc:
        c.rollback()
        fail("write_probe_failed", detail=type(exc).__name__)
    finally:
        c.close()

    print(json.dumps({
        "ok": True,
        "backend": ready["backend"],
        "durable": ready["durable"],
        "schema_ready": ready["schema_ready"],
        "production_ready": ready["production_ready"],
        "ready": ready["ready"],
        "migration_count": len(migration["applied"]),
        "write_probe": "pass",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
