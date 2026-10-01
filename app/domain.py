import hashlib
import json
import secrets
import time

def now():
    return int(time.time())

def uid(prefix):
    return prefix + "_" + secrets.token_hex(8)

def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def hash_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def audit(c, kind, actor, payload=None):
    c.execute(
        "INSERT INTO events(kind,actor,payload,ts) VALUES(?,?,?,?)",
        (kind, actor or "system", dump(payload or {}), now()),
    )

def consent(c, email, purpose, version, granted, source, business_ref=None):
    c.execute(
        "INSERT INTO consent_records(email,purpose,consent_version,granted,source,business_ref,ts) VALUES(?,?,?,?,?,?,?)",
        (email, purpose, version, 1 if granted else 0, source, business_ref, now()),
    )

def require_role(auth, roles):
    return bool(auth and auth[0] in set(roles))

def record_webhook(c, provider, event_id, payload):
    checksum = hash_text(dump(payload))
    cur = c.execute(
        "INSERT INTO webhook_receipts(provider,event_id,checksum,status,processed_at) VALUES(?,?,?,?,?) ON CONFLICT(provider,event_id) DO NOTHING",
        (provider, event_id, checksum, "accepted", now()),
    )
    return {"accepted": getattr(cur, "rowcount", 0) != 0, "checksum": checksum}
