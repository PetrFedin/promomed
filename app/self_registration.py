"""Fail-closed public participant self-registration.

Request creates only a short-lived pending verification record. An active
participant account is created only after possession of the email-delivered code
is proven. Event registration remains a separate authenticated action.
"""
import hashlib
import hmac
import os
import re
import secrets
import time
import uuid

from app import db
from app.auth import hash_password, issue_session
from app.registration_delivery import configured as delivery_configured
from app.registration_delivery import send_verification

REQUEST_ROUTE = "/api/participant-registration/v1/request"
VERIFY_ROUTE = "/api/participant-registration/v1/verify"
PUBLIC_ROUTES = frozenset((REQUEST_ROUTE, VERIFY_ROUTE))
CODE_TTL_SECONDS = 10 * 60
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60
EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$")


def _secret():
    value = os.environ.get("PROMOMED_REGISTRATION_CODE_SECRET", "")
    if value:
        return value.encode("utf-8")
    if db.demo_seed_enabled():
        return b"promomed-demo-registration-secret-not-production"
    return None


def _code_hash(request_id, code):
    secret = _secret()
    if secret is None:
        raise RuntimeError("registration_secret_unconfigured")
    return hmac.new(
        secret, (request_id + ":" + code).encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _password_valid(value):
    if not isinstance(value, str) or len(value) < 14 or len(value) > 256:
        return False
    classes = (
        any(ch.islower() for ch in value),
        any(ch.isupper() for ch in value),
        any(ch.isdigit() for ch in value),
        any(not ch.isalnum() for ch in value),
    )
    return sum(classes) >= 3 and "\x00" not in value


def _identity(data):
    if set(data) != {"email", "name", "password"}:
        return None
    email = data.get("email")
    name = data.get("name")
    password = data.get("password")
    if not isinstance(email, str) or not isinstance(name, str):
        return None
    email = email.strip().lower()
    name = " ".join(name.strip().split())
    if (
        len(email) > 254
        or not EMAIL.fullmatch(email)
        or len(name) < 1
        or len(name) > 80
        or any(ord(ch) < 32 for ch in name)
        or not _password_valid(password)
    ):
        return None
    if not db.demo_seed_enabled() and email.endswith("@demo.ru"):
        return None
    return email, name, password


def _generic_request(request_id=None):
    return {
        "accepted": True,
        "next": "check_email",
        "expiresInSeconds": CODE_TTL_SECONDS,
        "requestId": request_id or uuid.uuid4().hex,
    }, 202


def request_registration(data):
    identity = _identity(data)
    if identity is None:
        return {"error": "invalid_registration_request"}, 422

    demo = bool(db.demo_seed_enabled())
    if not demo and (_secret() is None or not delivery_configured()):
        return {"error": "registration_delivery_unavailable"}, 503

    email, name, password = identity
    now = int(time.time())
    c = db.connect()
    try:
        account = c.execute(
            "SELECT 1 FROM accounts WHERE email=?", (email,)
        ).fetchone()
        if account:
            return _generic_request()

        existing = c.execute(
            "SELECT id,created_at FROM participant_registration_requests "
            "WHERE email=? AND status='pending' ORDER BY created_at DESC LIMIT 1",
            (email,),
        ).fetchone()
        if existing and now - int(existing["created_at"]) < RESEND_COOLDOWN_SECONDS:
            return _generic_request()
        if existing:
            c.execute(
                "UPDATE participant_registration_requests SET status='expired' "
                "WHERE id=? AND status='pending'", (existing["id"],)
            )

        request_id = uuid.uuid4().hex
        code = f"{secrets.randbelow(1000000):06d}"
        c.execute(
            "INSERT INTO participant_registration_requests("
            "id,email,name,password_hash,verification_hash,status,created_at,"
            "expires_at,verified_at,attempts,demo_only) "
            "VALUES(?,?,?,?,?,'pending',?,?,NULL,0,?)",
            (
                request_id, email, name, hash_password(password),
                _code_hash(request_id, code), now, now + CODE_TTL_SECONDS,
                1 if demo else 0,
            ),
        )

        if demo:
            c.commit()
            payload, status = _generic_request(request_id)
            payload = dict(payload)
            payload["demoVerificationCode"] = code
            payload["demoOnly"] = True
            return payload, status

        try:
            send_verification(email, code, request_id)
        except Exception:
            c.rollback()
            return {"error": "registration_delivery_failed"}, 503
        c.commit()
        payload, status = _generic_request(request_id)
        payload = dict(payload)
        return payload, status
    finally:
        c.close()


def verify_registration(data):
    if set(data) != {"request_id", "code"}:
        return {"error": "invalid_verification"}, 422
    request_id = data.get("request_id")
    code = data.get("code")
    if (
        not isinstance(request_id, str)
        or len(request_id) != 32
        or not all(ch in "0123456789abcdef" for ch in request_id)
        or not isinstance(code, str)
        or len(code) != 6
        or not code.isascii()
        or not code.isdecimal()
    ):
        return {"error": "invalid_verification"}, 422
    if _secret() is None:
        return {"error": "registration_delivery_unavailable"}, 503

    now = int(time.time())
    c = db.connect()
    try:
        row = c.execute(
            "SELECT * FROM participant_registration_requests WHERE id=?",
            (request_id,),
        ).fetchone()
        if not row or row["status"] != "pending":
            return {"error": "invalid_verification"}, 422
        if int(row["expires_at"]) <= now:
            c.execute(
                "UPDATE participant_registration_requests SET status='expired' "
                "WHERE id=? AND status='pending'", (request_id,)
            )
            c.commit()
            return {"error": "invalid_verification"}, 422

        expected = row["verification_hash"]
        actual = _code_hash(request_id, code)
        if not hmac.compare_digest(expected, actual):
            attempts = int(row["attempts"]) + 1
            status = "blocked" if attempts >= MAX_ATTEMPTS else "pending"
            c.execute(
                "UPDATE participant_registration_requests SET attempts=?,status=? "
                "WHERE id=?", (attempts, status, request_id)
            )
            c.commit()
            return {"error": "invalid_verification"}, 422

        if c.execute(
            "SELECT 1 FROM accounts WHERE email=?", (row["email"],)
        ).fetchone():
            c.execute(
                "UPDATE participant_registration_requests SET status='blocked' "
                "WHERE id=?", (request_id,)
            )
            c.commit()
            return {"error": "invalid_verification"}, 422

        c.execute(
            "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
            "VALUES(?,?, 'participant',?,'active',?,?)",
            (row["email"], row["password_hash"], row["name"], now, now),
        )
        c.execute(
            "UPDATE participant_registration_requests "
            "SET status='verified',verified_at=? WHERE id=? AND status='pending'",
            (now, request_id),
        )
        token, expires = issue_session(
            c, row["email"], "participant", row["name"]
        )
        return {
            "verified": True,
            "token": token,
            "expires_at": expires,
            "role": "participant",
            "name": row["name"],
            "eventRegistration": False,
            "next": "/personal/",
        }, 201
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def handle_public(route, data):
    if route == REQUEST_ROUTE:
        return request_registration(data)
    if route == VERIFY_ROUTE:
        return verify_registration(data)
    return None
