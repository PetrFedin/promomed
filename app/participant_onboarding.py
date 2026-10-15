"""One-time invite onboarding for participant accounts.

There is no open self-registration. An authenticated organizer creates a
short-lived invite; only its SHA-256 is stored. Acceptance creates a participant
account and confirmed registration atomically, but never creates a session.
"""
import re
import secrets
import time
import uuid

from app import db
from app.auth import hash_password, token_hash
from app.commanding import custom, error
from app.core import audit

CREATE_ROUTE = "/api/participant-invite/create"
REVOKE_ROUTE = "/api/participant-invite/revoke"
ACCEPT_ROUTE = "/api/participant-invite/accept"
ROUTES = frozenset((CREATE_ROUTE, REVOKE_ROUTE))
INVITE_TTL_SECONDS = 72 * 60 * 60
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{40,128}$")


def _email(value):
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    if (
        not value
        or len(value) > 254
        or value.count("@") != 1
        or any(ch.isspace() for ch in value)
    ):
        return None
    local, domain = value.rsplit("@", 1)
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        return None
    return value


def _name(value):
    if not isinstance(value, str):
        return None
    value = " ".join(value.strip().split())
    return value if 1 <= len(value) <= 120 else None


def _valid_password(value):
    if not isinstance(value, str) or not (14 <= len(value) <= 256):
        return False
    if "\x00" in value:
        return False
    classes = (
        any(ch.islower() for ch in value),
        any(ch.isupper() for ch in value),
        any(ch.isdigit() for ch in value),
        any(not ch.isalnum() for ch in value),
    )
    return sum(classes) >= 3


def handle_command(c, route, role, email, data):
    if route not in ROUTES:
        return None
    if role != "organizer":
        return error("forbidden", 403)
    if not isinstance(data, dict):
        return error("invalid_request", 422)

    if route == CREATE_ROUTE:
        if set(data) != {"email", "name"}:
            return error("invalid_request", 422)
        target = _email(data["email"])
        name = _name(data["name"])
        if target is None or name is None:
            return error("invalid_invite_identity", 422)
        if not db.demo_seed_enabled() and target.endswith("@demo.ru"):
            return error("demo_identity_forbidden", 422)
        if c.execute("SELECT 1 FROM accounts WHERE email=?", (target,)).fetchone():
            return error("account_exists", 409)
        if c.execute(
            "SELECT 1 FROM participant_invites WHERE email=? AND status='pending' LIMIT 1",
            (target,),
        ).fetchone():
            return error("invite_pending", 409)

        token = secrets.token_urlsafe(32)
        now = int(time.time())
        invite_id = uuid.uuid4().hex
        c.execute(
            "INSERT INTO participant_invites("
            "id,token_hash,email,name,status,created_by,created_at,expires_at"
            ") VALUES(?,?,?,?,'pending',?,?,?)",
            (
                invite_id,
                token_hash(token),
                target,
                name,
                email,
                now,
                now + INVITE_TTL_SECONDS,
            ),
        )
        # Never put the raw invite token in the audit ledger.
        audit(c, "participant_invite_created", email, {"invite_id": invite_id})
        return custom({
            "invite_id": invite_id,
            "token": token,
            "expires_at": now + INVITE_TTL_SECONDS,
            "delivery": "manual_secure_channel_required",
        }, 201)

    if set(data) != {"invite_id"}:
        return error("invalid_request", 422)
    invite_id = data["invite_id"]
    if not isinstance(invite_id, str) or not re.fullmatch(r"[a-f0-9]{32}", invite_id):
        return error("not_found", 404)
    row = c.execute(
        "SELECT status,created_by FROM participant_invites WHERE id=?",
        (invite_id,),
    ).fetchone()
    if row is None or row["created_by"] != email:
        return error("not_found", 404)
    if row["status"] == "pending":
        now = int(time.time())
        c.execute(
            "UPDATE participant_invites SET status='revoked',consumed_at=? "
            "WHERE id=? AND status='pending'",
            (now, invite_id),
        )
        audit(c, "participant_invite_revoked", email, {"invite_id": invite_id})
    return custom({"revoked": True, "invite_id": invite_id})


def _lock_invite(c, digest):
    suffix = " FOR UPDATE" if db.backend_name() == "postgres" else ""
    return c.execute(
        "SELECT id,email,name,status,expires_at FROM participant_invites "
        "WHERE token_hash=?" + suffix,
        (digest,),
    ).fetchone()


def handle_public(route, data):
    if route != ACCEPT_ROUTE:
        return None
    if not isinstance(data, dict) or set(data) != {"token", "password"}:
        return {"error": "invalid_request"}, 422
    token, password = data["token"], data["password"]
    if not isinstance(token, str) or not TOKEN_RE.fullmatch(token):
        return {"error": "invalid_or_expired_invite"}, 404
    if not _valid_password(password):
        return {"error": "password_policy"}, 422

    c = db.connect()
    try:
        if db.backend_name() == "sqlite":
            c.execute("BEGIN IMMEDIATE")
        now = int(time.time())
        row = _lock_invite(c, token_hash(token))
        if (
            row is None
            or row["status"] != "pending"
            or int(row["expires_at"]) <= now
        ):
            c.rollback()
            return {"error": "invalid_or_expired_invite"}, 404

        target = row["email"]
        if not db.demo_seed_enabled() and target.endswith("@demo.ru"):
            c.rollback()
            return {"error": "invalid_or_expired_invite"}, 404

        existing = c.execute(
            "SELECT 1 FROM accounts WHERE email=?", (target,)
        ).fetchone()
        if existing:
            c.execute(
                "UPDATE participant_invites SET status='revoked',consumed_at=? "
                "WHERE id=? AND status='pending'",
                (now, row["id"]),
            )
            c.commit()
            return {"error": "account_exists"}, 409

        encoded = hash_password(password)
        c.execute(
            "INSERT INTO accounts("
            "email,password_hash,role,name,status,created_at,updated_at"
            ") VALUES(?,?,'participant',?,'active',?,?)",
            (target, encoded, row["name"], now, now),
        )
        c.execute(
            "INSERT INTO registrations(email,status,ts) VALUES(?,'confirmed',?) "
            "ON CONFLICT(email) DO UPDATE SET status='confirmed',ts=excluded.ts",
            (target, now),
        )
        c.execute(
            "UPDATE participant_invites SET status='accepted',consumed_at=? "
            "WHERE id=? AND status='pending'",
            (now, row["id"]),
        )
        c.commit()
        return {
            "accepted": True,
            "next": "/personal/",
            "sessionCreated": False,
        }, 201
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
