import hashlib
import json
import os
import secrets
import time

from app import db

SESSION_TTL = int(os.environ.get("PROMOMED_SESSION_TTL_SECONDS", "43200"))


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
