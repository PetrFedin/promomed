import hashlib
import hmac
import json
import os
import secrets
import time

from app import db

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
    token = h.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if not token:
        return None
    c = db.connect()
    try:
        row = c.execute(
            "SELECT role,name,email,expires_at,revoked_at FROM auth_sessions WHERE token_hash=?",
            (token_hash(token),),
        ).fetchone()
        if not row or row["revoked_at"] is not None or int(row["expires_at"]) <= int(time.time()):
            return None
        return (row["role"], row["name"], row["email"])
    finally:
        c.close()


def body(h):
    n = int(h.headers.get("Content-Length", "0") or 0)
    return json.loads(h.rfile.read(n) or b"{}")
