"""Provision one non-demo event edition on an admitted PostgreSQL authority."""
import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db

EVENT_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def fail(code, **extra):
    payload = {"ok": False, "error": code}
    payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False))
    raise SystemExit(1)


def parse_start(value):
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        fail("invalid_starts_at")
    if dt.tzinfo is None or dt.utcoffset() is None:
        fail("starts_at_timezone_required")
    ts = int(dt.timestamp())
    if ts <= 0:
        fail("invalid_starts_at")
    return ts


def main():
    parser = argparse.ArgumentParser(
        description="Create/update a non-demo event registration authority row."
    )
    parser.add_argument("--id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--starts-at", required=True)
    parser.add_argument("--capacity", required=True, type=int)
    parser.add_argument(
        "--status",
        choices=("open", "closed", "waitlist_only", "cancelled"),
        default="closed",
    )
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()

    event_id = args.id.strip()
    title = " ".join(args.title.strip().split())
    if not EVENT_ID.fullmatch(event_id):
        fail("invalid_event_id")
    if not title or len(title) > 160:
        fail("invalid_title")
    if args.capacity < 0 or args.capacity > 1000000:
        fail("invalid_capacity")
    starts_at = parse_start(args.starts_at)

    if db.backend_name() != "postgres":
        fail("postgres_required", backend=db.backend_name())
    if not db.require_postgres():
        fail("require_postgres_flag_required")
    if db.demo_seed_enabled():
        fail("demo_seed_must_be_disabled")
    ready = db.readiness()
    if not ready["production_ready"]:
        fail("database_not_production_ready", readiness=ready)

    now = int(time.time())
    c = db.connect()
    try:
        existing = c.execute(
            "SELECT id,capacity FROM event_editions_v1 WHERE id=?", (event_id,)
        ).fetchone()
        if existing and not args.update:
            fail("event_exists", event_id=event_id)
        if existing:
            confirmed = int(c.execute(
                "SELECT COUNT(*) n FROM participant_event_registrations_v1 "
                "WHERE event_id=? AND status='confirmed'", (event_id,)
            ).fetchone()["n"])
            if args.capacity < confirmed:
                fail(
                    "capacity_below_confirmed",
                    confirmed=confirmed,
                    requested_capacity=args.capacity,
                )
            c.execute(
                "UPDATE event_editions_v1 SET title=?,starts_at=?,"
                "registration_status=?,capacity=?,demo_only=0,updated_at=? "
                "WHERE id=?",
                (title, starts_at, args.status, args.capacity, now, event_id),
            )
            action = "updated"
        else:
            c.execute(
                "INSERT INTO event_editions_v1("
                "id,title,starts_at,registration_status,capacity,demo_only,created_at,updated_at"
                ") VALUES(?,?,?,?,?,0,?,?)",
                (event_id, title, starts_at, args.status, args.capacity, now, now),
            )
            action = "created"
        c.commit()
    except SystemExit:
        c.rollback()
        raise
    except Exception as exc:
        c.rollback()
        fail("event_write_failed", detail=type(exc).__name__)
    finally:
        c.close()

    print(json.dumps({
        "ok": True,
        "action": action,
        "event_id": event_id,
        "registration_status": args.status,
        "capacity": args.capacity,
        "starts_at": starts_at,
        "demo_only": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
