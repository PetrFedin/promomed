import argparse
import getpass
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.auth import hash_password

ALLOWED_ROLES = {
    "participant",
    "organizer",
    "partner",
    "staff",
    "editor",
    "moderator",
    "sales",
}
PRIVILEGED_ROLES = {"organizer", "editor", "moderator", "sales", "partner", "staff"}


def fail(code, **extra):
    payload = {"ok": False, "error": code}
    payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False))
    raise SystemExit(1)


def password_from_input():
    env_value = os.environ.get("PROMOMED_ACCOUNT_PASSWORD", "")
    if env_value:
        return env_value
    if not sys.stdin.isatty():
        fail("password_required_via_tty_or_secret_env")
    first = getpass.getpass("Password: ")
    second = getpass.getpass("Confirm password: ")
    if first != second:
        fail("password_confirmation_mismatch")
    return first


def validate_password(password):
    if len(password) < 14:
        fail("password_too_short", min_length=14)
    classes = [
        any(ch.islower() for ch in password),
        any(ch.isupper() for ch in password),
        any(ch.isdigit() for ch in password),
        any(not ch.isalnum() for ch in password),
    ]
    if sum(classes) < 3:
        fail("password_complexity_insufficient")


def main():
    parser = argparse.ArgumentParser(
        description="Provision or rotate a Promomed account without exposing password material."
    )
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", required=True, choices=sorted(ALLOWED_ROLES))
    parser.add_argument("--name", required=True)
    parser.add_argument("--rotate", action="store_true")
    args = parser.parse_args()

    email = args.email.strip().lower()
    name = args.name.strip()
    if "@" not in email:
        fail("invalid_email")
    if email.endswith("@demo.ru"):
        fail("demo_identity_forbidden")
    if not name:
        fail("name_required")

    if db.backend_name() != "postgres":
        fail("postgres_required", backend=db.backend_name())
    if not db.require_postgres():
        fail("require_postgres_flag_required")
    if db.demo_seed_enabled():
        fail("demo_seed_must_be_disabled")

    ready = db.readiness()
    if not ready["production_ready"]:
        fail("database_not_production_ready", readiness=ready)

    password = password_from_input()
    validate_password(password)
    encoded = hash_password(password)
    now = int(time.time())

    c = db.connect()
    try:
        existing = c.execute(
            "SELECT email,role,status FROM accounts WHERE email=?",
            (email,),
        ).fetchone()
        if existing and not args.rotate:
            fail("account_exists", email=email)
        if existing:
            c.execute(
                "UPDATE accounts SET password_hash=?,role=?,name=?,status='active',updated_at=? WHERE email=?",
                (encoded, args.role, name, now, email),
            )
            c.execute(
                "UPDATE auth_sessions SET revoked_at=? WHERE email=? AND revoked_at IS NULL",
                (now, email),
            )
            action = "rotated"
        else:
            c.execute(
                "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
                "VALUES(?,?,?,?, 'active', ?, ?)",
                (email, encoded, args.role, name, now, now),
            )
            action = "created"
        c.commit()
    except SystemExit:
        c.rollback()
        raise
    except Exception as exc:
        c.rollback()
        fail("account_write_failed", detail=type(exc).__name__)
    finally:
        c.close()

    print(json.dumps({
        "ok": True,
        "action": action,
        "email": email,
        "role": args.role,
        "privileged": args.role in PRIVILEGED_ROLES,
        "session_revocation": action == "rotated",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
