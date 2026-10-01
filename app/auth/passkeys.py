import hashlib
import json
import os
import secrets
import time

from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.domain import dump, now, uid

PRIVILEGED_ROLES={"organizer","editor","administrator","partner","sales"}
RP_ID=os.environ.get("WEBAUTHN_RP_ID","sostoyanie-promomed-live.onrender.com")
RP_NAME=os.environ.get("WEBAUTHN_RP_NAME","СОСТОЯНИЕ")
EXPECTED_ORIGIN=os.environ.get("WEBAUTHN_EXPECTED_ORIGIN","https://sostoyanie-promomed-live.onrender.com")
CHALLENGE_TTL=int(os.environ.get("WEBAUTHN_CHALLENGE_TTL_SECONDS","300"))
STEP_UP_TTL=int(os.environ.get("WEBAUTHN_STEP_UP_TTL_SECONDS","600"))

def _event(c,email,kind,details=None):
    safe=details or {}
    c.execute(
        "INSERT INTO security_events(id,email,kind,details_json,ts) VALUES(?,?,?,?,?)",
        (uid("security"),email,kind,dump(safe),now()),
    )

def _store_challenge(c,email,purpose,challenge):
    ts=now()
    c.execute(
        "INSERT INTO auth_challenges(id,email,purpose,challenge,created_at,expires_at,used_at) VALUES(?,?,?,?,?,?,NULL)",
        (uid("challenge"),email,purpose,challenge,ts,ts+CHALLENGE_TTL),
    )

def _consume_challenge(c,email,purpose):
    row=c.execute(
        """SELECT id,challenge FROM auth_challenges
           WHERE email=? AND purpose=? AND used_at IS NULL AND expires_at>?
           ORDER BY created_at DESC LIMIT 1""",
        (email,purpose,now()),
    ).fetchone()
    if not row:
        raise ValueError("passkey_challenge_missing_or_expired")
    c.execute("UPDATE auth_challenges SET used_at=? WHERE id=?",(now(),row["id"]))
    return bytes(row["challenge"])

def _user_handle(c,email):
    row=c.execute("SELECT user_handle FROM webauthn_users WHERE email=?",(email,)).fetchone()
    if row:
        return bytes(row["user_handle"])
    handle=secrets.token_bytes(32)
    c.execute("INSERT INTO webauthn_users(email,user_handle,created_at) VALUES(?,?,?)",(email,handle,now()))
    return handle

def _descriptors(c,email):
    return [
        PublicKeyCredentialDescriptor(id=bytes(r["credential_id"]))
        for r in c.execute("SELECT credential_id FROM webauthn_credentials WHERE email=? ORDER BY created_at",(email,))
    ]

def begin_registration(c,email,display_name):
    options=generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=_user_handle(c,email),
        user_name=email,
        user_display_name=display_name or email,
        exclude_credentials=_descriptors(c,email),
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )
    _store_challenge(c,email,"register",options.challenge)
    _event(c,email,"passkey_registration_started",{"rp_id":RP_ID})
    return json.loads(options_to_json(options))

def complete_registration(c,email,credential,device_name="Passkey"):
    challenge=_consume_challenge(c,email,"register")
    verified=verify_registration_response(
        credential=credential,
        expected_challenge=challenge,
        expected_origin=EXPECTED_ORIGIN,
        expected_rp_id=RP_ID,
        require_user_verification=True,
    )
    credential_id=bytes(verified.credential_id)
    public_key=bytes(verified.credential_public_key)
    cid="cred_"+hashlib.sha256(credential_id).hexdigest()[:24]
    transports=((credential or {}).get("response") or {}).get("transports") or []
    c.execute(
        """INSERT INTO webauthn_credentials(
           id,email,credential_id,public_key,sign_count,transports,device_name,created_at,last_used_at
           ) VALUES(?,?,?,?,?,?,?,?,NULL)
           ON CONFLICT(credential_id) DO UPDATE SET
           public_key=excluded.public_key,sign_count=excluded.sign_count,transports=excluded.transports,
           device_name=excluded.device_name""",
        (cid,email,credential_id,public_key,int(verified.sign_count),dump(transports),str(device_name)[:120],now()),
    )
    _event(c,email,"passkey_registered",{"credential_ref":cid,"user_verified":bool(verified.user_verified)})
    return {"verified":True,"credential_ref":cid}

def begin_authentication(c,email):
    descriptors=_descriptors(c,email)
    if not descriptors:
        raise ValueError("passkey_not_registered")
    options=generate_authentication_options(
        rp_id=RP_ID,
        allow_credentials=descriptors,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    _store_challenge(c,email,"authenticate",options.challenge)
    _event(c,email,"passkey_step_up_started",{"rp_id":RP_ID})
    return json.loads(options_to_json(options))

def _issue_step_up(c,email):
    token=secrets.token_urlsafe(32)
    digest=hashlib.sha256(token.encode("utf-8")).hexdigest()
    ts=now()
    c.execute(
        "INSERT INTO step_up_sessions(token_hash,email,method,created_at,expires_at,revoked_at) VALUES(?,?, 'passkey', ?, ?, NULL)",
        (digest,email,ts,ts+STEP_UP_TTL),
    )
    return token,ts+STEP_UP_TTL

def complete_authentication(c,email,credential):
    challenge=_consume_challenge(c,email,"authenticate")
    raw_id=base64url_to_bytes(str((credential or {}).get("id") or ""))
    row=c.execute(
        "SELECT id,public_key,sign_count FROM webauthn_credentials WHERE email=? AND credential_id=?",
        (email,raw_id),
    ).fetchone()
    if not row:
        raise ValueError("passkey_credential_not_found")
    verified=verify_authentication_response(
        credential=credential,
        expected_challenge=challenge,
        expected_rp_id=RP_ID,
        expected_origin=EXPECTED_ORIGIN,
        credential_public_key=bytes(row["public_key"]),
        credential_current_sign_count=int(row["sign_count"]),
        require_user_verification=True,
    )
    c.execute(
        "UPDATE webauthn_credentials SET sign_count=?,last_used_at=? WHERE id=?",
        (int(verified.new_sign_count),now(),row["id"]),
    )
    token,expires_at=_issue_step_up(c,email)
    _event(c,email,"passkey_step_up_verified",{"credential_ref":row["id"],"expires_at":expires_at})
    return {"verified":True,"step_up_token":token,"expires_at":expires_at}

def has_step_up(c,email,token):
    if not token:
        return False
    digest=hashlib.sha256(str(token).encode("utf-8")).hexdigest()
    row=c.execute(
        """SELECT 1 FROM step_up_sessions
           WHERE token_hash=? AND email=? AND method='passkey' AND revoked_at IS NULL AND expires_at>?""",
        (digest,email,now()),
    ).fetchone()
    return bool(row)

def require_step_up(c,email,token):
    if not has_step_up(c,email,token):
        _event(c,email,"step_up_denied",{"reason":"missing_or_expired"})
        raise PermissionError("step_up_required")

def status(c,email):
    count=c.execute("SELECT COUNT(*) n FROM webauthn_credentials WHERE email=?",(email,)).fetchone()["n"]
    last=c.execute("SELECT MAX(last_used_at) ts FROM webauthn_credentials WHERE email=?",(email,)).fetchone()["ts"]
    return {
        "eligible":True,
        "credential_count":count,
        "last_used_at":last,
        "rp_id":RP_ID,
        "expected_origin":EXPECTED_ORIGIN,
        "step_up_ttl_seconds":STEP_UP_TTL,
    }
