import hashlib
import hmac
import os
import secrets
import time

PBKDF2_ITERATIONS = 260_000
SESSION_TTL_SECONDS = int(os.environ.get("PROMOMED_SESSION_TTL_SECONDS", "43200"))
DEMO_ENABLED = os.environ.get("PROMOMED_DEMO_ACCOUNTS", "1") == "1"

DEMO_ACCOUNTS = {
    "participant@demo.ru": ("demo2027", "participant", "Участник"),
    "participant2@demo.ru": ("demo2027", "participant", "Участник 2"),
    "participant3@demo.ru": ("demo2027", "participant", "Участник 3"),
    "organizer@demo.ru": ("demo2027", "organizer", "Организатор"),
    "partner@demo.ru": ("demo2027", "partner", "Партнёр"),
    "staff@demo.ru": ("demo2027", "staff", "Check-in"),
    "editor@demo.ru": ("demo2027", "editor", "Редактор"),
    "moderator@demo.ru": ("demo2027", "moderator", "Модератор"),
    "sales@demo.ru": ("demo2027", "sales", "Demo Director"),
}

def _password_hash(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256$%s$%s$%s" % (PBKDF2_ITERATIONS, salt.hex(), digest.hex())

def _password_ok(password, encoded):
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        calc = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(calc.hex(), digest_hex)
    except Exception:
        return False

def _token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def ensure_demo_accounts(c):
    if getattr(c, "backend", "sqlite") == "sqlite":
        c.execute("""CREATE TABLE IF NOT EXISTS accounts(
            email TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS sessions(
            token_hash TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            role TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            revoked_at INTEGER
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS consent_records(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            purpose TEXT NOT NULL,
            consent_version TEXT NOT NULL,
            granted INTEGER NOT NULL,
            source TEXT NOT NULL,
            business_ref TEXT,
            ts INTEGER NOT NULL
        )""")
    if not DEMO_ENABLED:
        return
    now = int(time.time())
    for email, (password, role, name) in DEMO_ACCOUNTS.items():
        row = c.execute("SELECT email FROM accounts WHERE email=?", (email,)).fetchone()
        if row:
            continue
        c.execute(
            "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (email, _password_hash(password), role, name, "active", now, now),
        )

def authenticate_password(c, email, password):
    row = c.execute(
        "SELECT email,password_hash,role,name,status FROM accounts WHERE email=?",
        (email.lower(),),
    ).fetchone()
    if not row or row["status"] != "active" or not _password_ok(password, row["password_hash"]):
        return None
    return (row["role"], row["name"], row["email"])

def create_session(c, email, role, name):
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    c.execute(
        "INSERT INTO sessions(token_hash,email,role,name,created_at,expires_at,revoked_at) VALUES(?,?,?,?,?,?,NULL)",
        (_token_hash(token), email, role, name, now, now + SESSION_TTL_SECONDS),
    )
    return token

def authenticate_headers(c, headers):
    raw = headers.get("Authorization", "")
    token = raw.replace("Bearer ", "", 1).strip()
    if not token:
        return None
    row = c.execute(
        "SELECT email,role,name FROM sessions WHERE token_hash=? AND revoked_at IS NULL AND expires_at>?",
        (_token_hash(token), int(time.time())),
    ).fetchone()
    if not row:
        return None
    return (row["role"], row["name"], row["email"])

def revoke_session(c, token):
    c.execute(
        "UPDATE sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
        (int(time.time()), _token_hash(token)),
    )
