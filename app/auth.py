import hashlib
import hmac
import json
import os
import secrets
import time

from app import db
from app.request_body_io import BodyReadError, read_exact_body

SESSION_TTL = int(os.environ.get("PROMOMED_SESSION_TTL_SECONDS", "43200"))
SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1

DEMO_ACCOUNTS = (
    ("participant@demo.ru", "demo2027", "participant", "Участник"),
    ("participant2@demo.ru", "demo2027", "participant", "Участник 2"),
    ("participant3@demo.ru", "demo2027", "participant", "Участник 3"),
    ("organizer@demo.ru", "demo2027", "organizer", "Организатор"),
    ("partner@demo.ru", "demo2027", "partner", "Партнёр"),
    ("staff@demo.ru", "demo2027", "staff", "Check-in"),
    ("editor@demo.ru", "demo2027", "editor", "Редактор"),
    ("moderator@demo.ru", "demo2027", "moderator", "Модератор"),
    ("sales@demo.ru", "demo2027", "sales", "Demo Director"),
    ("reviewer@demo.ru", "demo2027", "reviewer", "Medical Reviewer · DEMO"),
    ("governance@demo.ru", "demo2027", "governance", "Medical Governance · DEMO"),
)


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password, salt=None):
    salt = salt or os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=32,
    )
    return "scrypt$" + "$".join(
        [str(SCRYPT_N), str(SCRYPT_R), str(SCRYPT_P), salt.hex(), digest.hex()]
    )


def verify_password(password, encoded):
    try:
        kind, n, r, p, salt_hex, expected_hex = encoded.split("$", 5)
        if kind != "scrypt":
            return False
        expected = bytes.fromhex(expected_hex)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def seed_demo_accounts(c):
    now = int(time.time())
    for email, password, role, name in DEMO_ACCOUNTS:
        exists = c.execute("SELECT 1 FROM accounts WHERE email=?", (email,)).fetchone()
        if exists:
            continue
        c.execute(
            "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) VALUES(?,?,?,?, 'active', ?, ?)",
            (email, hash_password(password), role, name, now, now),
        )


def authenticate(c, email, password):
    row = c.execute(
        "SELECT email,password_hash,role,name,status FROM accounts WHERE email=?",
        (email.lower(),),
    ).fetchone()
    if not row or row["status"] != "active":
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return {
        "email": row["email"],
        "role": row["role"],
        "name": row["name"],
    }


def issue_session(c, email, role, name):
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    expires = now + SESSION_TTL
    c.execute("DELETE FROM auth_sessions WHERE expires_at<? OR revoked_at IS NOT NULL", (now,))
    c.execute(
        "INSERT INTO auth_sessions(token_hash,email,role,name,created_at,expires_at,revoked_at) VALUES(?,?,?,?,?,?,NULL)",
        (token_hash(token), email, role, name, now, expires),
    )
    c.commit()
    return token, expires


def auth(h):
    """Validate the current account authority, never trust a stale session role."""
    header = h.headers.get("Authorization", "")
    if not isinstance(header, str) or len(header) > 256 or not header.startswith("Bearer "):
        return None
    token = header[len("Bearer "):]
    if not token or len(token) > 128 or any(ch.isspace() for ch in token):
        return None
    c = db.connect()
    try:
        row = c.execute(
            """SELECT s.email,s.role,s.expires_at,s.revoked_at,
                      a.role AS account_role,a.status AS account_status,a.name AS account_name
               FROM auth_sessions s
               JOIN accounts a ON a.email=s.email
               WHERE s.token_hash=?""",
            (token_hash(token),),
        ).fetchone()
        if (not row or row["revoked_at"] is not None
                or int(row["expires_at"]) <= int(time.time())
                or row["account_status"] != "active"
                or row["account_role"] != row["role"]):
            return None
        return (row["account_role"], row["account_name"], row["email"])
    finally:
        c.close()


# HTTP endpoints accept bounded JSON command objects only. Do not read the
# declared body when the client advertises a size above the limit.
MAX_JSON_BODY_BYTES = 4 * 1024 * 1024


class RequestBodyError(ValueError):
    """Malformed or unsupported HTTP JSON request envelope."""


class RequestBodyTooLarge(RequestBodyError):
    """The declared JSON body exceeds the explicit application limit."""


def body(h):
    """Read one bounded JSON object; never trust the client's byte count."""
    if h.headers.get("Transfer-Encoding") is not None:
        raise RequestBodyError("unsupported_transfer_encoding")
    get_all = getattr(h.headers, "get_all", None)
    lengths = get_all("Content-Length") if callable(get_all) else None
    if lengths is not None and len(lengths) != 1:
        raise RequestBodyError("ambiguous_content_length")
    declared = lengths[0] if lengths else h.headers.get("Content-Length", "0")
    if not isinstance(declared, str):
        raise RequestBodyError("invalid_content_length")
    declared = declared.strip()
    if not declared or len(declared) > 10 or not declared.isascii() or not declared.isdecimal():
        raise RequestBodyError("invalid_content_length")
    n = int(declared)
    if n > MAX_JSON_BODY_BYTES:
        raise RequestBodyTooLarge("json_body_too_large")
    try:
        payload = read_exact_body(h, n)
    except BodyReadError as exc:
        # Preserve the existing generic HTTP 400 contract; no socket details.
        raise RequestBodyError(str(exc)) from None
    try:
        data = json.loads(payload or b"{}")
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise RequestBodyError("malformed_json") from None
    if not isinstance(data, dict):
        raise RequestBodyError("json_object_required")
    return data
