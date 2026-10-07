import base64
import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import socket
import time
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

from app import syndication_network


PROTOCOL_VERSION="promomed-partner-delivery-v2"
SIGNATURE_VERSION="v1"
MAX_ATTEMPTS=8
ACK_EXPECTATION_SECONDS=86400
RETRY_DELAYS=(60,300,900,3600,10800,21600,21600,21600)
EVENT_TYPES={
    "package_delivery",
    "package_update",
    "package_withdrawal",
    "contribution_admission",
    "qualification_status",
}


def _canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)


def _sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def _sha(value):
    return _sha_bytes(_canonical(value).encode("utf-8"))


def _b64u(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _master_secret():
    raw=os.environ.get("PROMOMED_WEBHOOK_MASTER_SECRET","").strip()
    if len(raw)<32:
        raise ValueError("webhook_master_secret_not_configured")
    return raw.encode("utf-8")


def _endpoint_secret(endpoint_id,secret_version):
    material=f"{PROTOCOL_VERSION}|{endpoint_id}|{int(secret_version)}".encode("utf-8")
    return _b64u(hmac.new(_master_secret(),material,hashlib.sha256).digest())


def _secret_hash(secret):
    return hashlib.sha256(str(secret).encode("utf-8")).hexdigest()


def _sign(secret,timestamp,event_id,payload_sha256):
    message=f"{int(timestamp)}.{event_id}.{payload_sha256}".encode("utf-8")
    digest=hmac.new(str(secret).encode("utf-8"),message,hashlib.sha256).hexdigest()
    return f"{SIGNATURE_VERSION}={digest}"


def webhook_signature(secret,timestamp,event_id,payload_sha256):
    return _sign(secret,timestamp,event_id,payload_sha256)


def acknowledgement_signature(secret,timestamp,event_id,ack_payload):
    if not isinstance(ack_payload,dict):
        raise ValueError("delivery_ack_payload_invalid")
    ack_sha=_sha_bytes(_canonical(ack_payload).encode("utf-8"))
    return _sign(secret,timestamp,event_id,ack_sha)


def verify_signature(secret,timestamp,event_id,payload_sha256,signature):
    expected=_sign(secret,timestamp,event_id,payload_sha256)
    return hmac.compare_digest(expected,str(signature or ""))


def _organization(c,organization_id):
    row=c.execute(
        "SELECT id,name,status,demo_only FROM institutional_organizations WHERE id=?",
        (organization_id,),
    ).fetchone()
    if not row:
        raise ValueError("organization_not_found")
    if row["status"]!="active":
        raise ValueError("organization_not_active")
    return row


def _validate_endpoint_url(url):
    value=str(url or "").strip()
    parsed=urlparse.urlparse(value)
    if parsed.scheme!="https":
        raise ValueError("webhook_https_required")
    if not parsed.hostname:
        raise ValueError("webhook_hostname_required")
    if parsed.username or parsed.password:
        raise ValueError("webhook_userinfo_forbidden")
    if parsed.fragment:
        raise ValueError("webhook_fragment_forbidden")
    if parsed.port is not None and not (1<=int(parsed.port)<=65535):
        raise ValueError("webhook_port_invalid")
    return value


def _validate_public_network_target(url):
    value=_validate_endpoint_url(url)
    parsed=urlparse.urlparse(value)
    host=parsed.hostname
    port=parsed.port or 443
    try:
        addresses=socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("webhook_dns_resolution_failed") from exc
    if not addresses:
        raise ValueError("webhook_dns_resolution_failed")
    for item in addresses:
        ip_text=item[4][0]
        try:
            ip=ipaddress.ip_address(ip_text)
        except ValueError as exc:
            raise ValueError("webhook_resolved_ip_invalid") from exc
        if not ip.is_global:
            raise ValueError("webhook_private_network_forbidden")
    return value


def _https_post(url,body,headers,timeout=10):
    _validate_public_network_target(url)
    req=urlrequest.Request(
        url,
        data=body,
        headers={str(k):str(v) for k,v in headers.items()},
        method="POST",
    )
    try:
        with urlrequest.urlopen(req,timeout=timeout) as response:
            return {
                "status":int(response.status),
                "body":response.read(1024*1024),
            }
    except urlerror.HTTPError as exc:
        return {
            "status":int(exc.code),
            "body":exc.read(1024*1024),
        }


def _endpoint_row(c,endpoint_id):
    return c.execute(
        """SELECT id,organization_id,endpoint_url,status,secret_version,secret_hash,
                  verification_challenge,verified_at,verified_by,last_rotated_at,
                  last_rotated_by,created_at,created_by,demo_only
           FROM syndication_delivery_endpoints WHERE id=?""",
        (endpoint_id,),
    ).fetchone()


def _endpoint_document(row):
    if not row:
        return None
    return {
        "id":row["id"],
        "organizationId":row["organization_id"],
        "endpointUrl":row["endpoint_url"],
        "status":row["status"],
        "secretVersion":row["secret_version"],
        "verifiedAt":row["verified_at"],
        "verifiedByRole":"governance" if row["verified_by"] else None,
        "lastRotatedAt":row["last_rotated_at"],
        "createdAt":row["created_at"],
        "demoOnly":bool(row["demo_only"]),
        "secretExposed":False,
    }


def register_endpoint(c,organization_id,endpoint_url,actor,demo_only=False):
    org=_organization(c,organization_id)
    if int(org["demo_only"])!=int(bool(demo_only)):
        raise ValueError("webhook_endpoint_demo_boundary_mismatch")
    endpoint_url=_validate_endpoint_url(endpoint_url)
    existing=c.execute(
        "SELECT * FROM syndication_delivery_endpoints WHERE organization_id=? AND endpoint_url=?",
        (organization_id,endpoint_url),
    ).fetchone()
    if existing:
        return {
            "endpoint":_endpoint_document(existing),
            "secret":None,
            "secretIssued":False,
            "idempotentReplay":True,
        }
    now=int(time.time())
    seed=f"{organization_id}|{endpoint_url}".encode("utf-8")
    endpoint_id="wh:"+hashlib.sha256(seed).hexdigest()[:24]
    secret_version=1
    secret=_endpoint_secret(endpoint_id,secret_version)
    challenge=secrets.token_urlsafe(24)
    c.execute(
        """INSERT INTO syndication_delivery_endpoints(
             id,organization_id,endpoint_url,status,secret_version,secret_hash,
             verification_challenge,created_at,created_by,demo_only
           ) VALUES(?,?,?,'pending_verification',?,?,?,?,?,?)""",
        (
            endpoint_id,organization_id,endpoint_url,secret_version,
            _secret_hash(secret),challenge,now,actor,int(bool(demo_only)),
        ),
    )
    row=_endpoint_row(c,endpoint_id)
    return {
        "endpoint":_endpoint_document(row),
        "verificationChallenge":challenge,
        "secret":secret,
        "secretIssued":True,
        "idempotentReplay":False,
    }


def rotate_endpoint_secret(c,endpoint_id,actor):
    row=_endpoint_row(c,endpoint_id)
    if not row:
        raise ValueError("webhook_endpoint_not_found")
    if row["status"]=="revoked":
        raise ValueError("webhook_endpoint_revoked")
    version=int(row["secret_version"])+1
    secret=_endpoint_secret(endpoint_id,version)
    now=int(time.time())
    c.execute(
        """UPDATE syndication_delivery_endpoints
           SET secret_version=?,secret_hash=?,last_rotated_at=?,last_rotated_by=?
           WHERE id=?""",
        (version,_secret_hash(secret),now,actor,endpoint_id),
    )
    return {
        "endpoint":_endpoint_document(_endpoint_row(c,endpoint_id)),
        "secret":secret,
        "secretIssued":True,
    }


def suspend_endpoint(c,endpoint_id,actor,reason=""):
    row=_endpoint_row(c,endpoint_id)
    if not row:
        raise ValueError("webhook_endpoint_not_found")
    if row["status"]=="revoked":
        raise ValueError("webhook_endpoint_revoked")
    c.execute(
        "UPDATE syndication_delivery_endpoints SET status='suspended' WHERE id=?",
        (endpoint_id,),
    )
    return {
        "endpoint":_endpoint_document(_endpoint_row(c,endpoint_id)),
        "reason":str(reason or "")[:500],
        "actorRole":"governance",
    }


def revoke_endpoint(c,endpoint_id,actor,reason=""):
    row=_endpoint_row(c,endpoint_id)
    if not row:
        raise ValueError("webhook_endpoint_not_found")
    if row["status"]!="revoked":
        c.execute(
            "UPDATE syndication_delivery_endpoints SET status='revoked' WHERE id=?",
            (endpoint_id,),
        )
    return {
        "endpoint":_endpoint_document(_endpoint_row(c,endpoint_id)),
        "reason":str(reason or "")[:500],
        "actorRole":"governance",
    }


def verify_endpoint(c,endpoint_id,actor,transport=None):
    row=_endpoint_row(c,endpoint_id)
    if not row:
        raise ValueError("webhook_endpoint_not_found")
    if row["status"]=="revoked":
        raise ValueError("webhook_endpoint_revoked")
    secret=_endpoint_secret(endpoint_id,row["secret_version"])
    if _secret_hash(secret)!=row["secret_hash"]:
        raise ValueError("webhook_secret_registry_mismatch")
    body_obj={
        "protocolVersion":PROTOCOL_VERSION,
        "action":"endpoint_verification",
        "endpointId":endpoint_id,
        "organizationId":row["organization_id"],
        "challenge":row["verification_challenge"],
    }
    body=_canonical(body_obj).encode("utf-8")
    payload_sha=_sha_bytes(body)
    timestamp=int(time.time())
    event_id=f"verify:{endpoint_id}:{payload_sha[:16]}"
    headers={
        "Content-Type":"application/json",
        "X-Promomed-Protocol":PROTOCOL_VERSION,
        "X-Promomed-Event-Id":event_id,
        "X-Promomed-Timestamp":str(timestamp),
        "X-Promomed-Payload-SHA256":payload_sha,
        "X-Promomed-Signature":_sign(secret,timestamp,event_id,payload_sha),
        "X-Promomed-Verification":"challenge",
    }
    transport=transport or _https_post
    try:
        response=transport(row["endpoint_url"],body,headers)
    except Exception as exc:
        raise ValueError("webhook_endpoint_verification_transport_failed") from exc
    status=int(response.get("status") or 0)
    raw=response.get("body") or b""
    if isinstance(raw,str):
        raw=raw.encode("utf-8")
    if not 200<=status<300:
        raise ValueError("webhook_endpoint_verification_rejected")
    text=raw.decode("utf-8","replace").strip()
    echoed=None
    try:
        parsed=json.loads(text)
        if isinstance(parsed,dict):
            echoed=parsed.get("challenge")
    except Exception:
        echoed=text
    if str(echoed or "")!=row["verification_challenge"]:
        raise ValueError("webhook_endpoint_challenge_mismatch")
    now=int(time.time())
    c.execute(
        """UPDATE syndication_delivery_endpoints
           SET status='active',verified_at=?,verified_by=? WHERE id=?""",
        (now,actor,endpoint_id),
    )
    return _endpoint_document(_endpoint_row(c,endpoint_id))


def _active_endpoint(c,organization_id):
    row=c.execute(
        """SELECT * FROM syndication_delivery_endpoints
           WHERE organization_id=? AND status='active'
           ORDER BY verified_at DESC,created_at DESC,id DESC LIMIT 1""",
        (organization_id,),
    ).fetchone()
    return row


def _allocate_sequence(c,organization_id,now):
    c.execute(
        """INSERT INTO syndication_partner_delivery_cursors(
             organization_id,next_sequence,last_acked_sequence,updated_at
           ) VALUES(?,1,0,?)
           ON CONFLICT(organization_id) DO NOTHING""",
        (organization_id,now),
    )
    row=c.execute(
        """UPDATE syndication_partner_delivery_cursors
           SET next_sequence=next_sequence+1,updated_at=?
           WHERE organization_id=?
           RETURNING next_sequence""",
        (now,organization_id),
    ).fetchone()
    if not row:
        raise ValueError("delivery_cursor_allocation_failed")
    return int(row["next_sequence"])-1


def create_event(
    c,organization_id,event_type,subject_kind,subject_ref,data,actor,
    obligation_id=None,demo_only=False,
):
    org=_organization(c,organization_id)
    if int(org["demo_only"])!=int(bool(demo_only)):
        raise ValueError("delivery_event_demo_boundary_mismatch")
    syndication_network._require_qualified(c,organization_id)
    endpoint=_active_endpoint(c,organization_id)
    if not endpoint:
        raise ValueError("active_webhook_endpoint_required")
    if event_type not in EVENT_TYPES:
        raise ValueError("delivery_event_type_invalid")
    if not isinstance(data,dict):
        raise ValueError("delivery_event_payload_invalid")
    subject_kind=str(subject_kind or "").strip()[:80]
    subject_ref=str(subject_ref or "").strip()[:180]
    if not subject_kind or not subject_ref:
        raise ValueError("delivery_event_subject_required")
    obligation_id=str(obligation_id or "").strip() or None
    if obligation_id:
        obligation=c.execute(
            """SELECT o.id,d.organization_id
               FROM syndication_delivery_obligations o
               JOIN evidence_exchange_deliveries d ON d.id=o.delivery_id
               WHERE o.id=?""",
            (obligation_id,),
        ).fetchone()
        if not obligation or obligation["organization_id"]!=organization_id:
            raise ValueError("delivery_event_obligation_mismatch")
    data_hash=_sha(data)
    identity={
        "organizationId":organization_id,
        "eventType":event_type,
        "subject":{"kind":subject_kind,"ref":subject_ref},
        "obligationId":obligation_id,
        "dataSha256":data_hash,
    }
    event_id="delivery:"+_sha(identity)[:28]
    existing=c.execute(
        """SELECT e.id,e.organization_id,e.endpoint_id,e.sequence_no,e.event_type,
                  e.subject_kind,e.subject_ref,e.obligation_id,e.payload_sha256,
                  e.created_at,s.status
           FROM syndication_delivery_events e
           JOIN syndication_delivery_event_state s ON s.event_id=e.id
           WHERE e.id=?""",
        (event_id,),
    ).fetchone()
    if existing:
        return {**dict(existing),"idempotentReplay":True}
    now=int(time.time())
    sequence=_allocate_sequence(c,organization_id,now)
    payload={
        "protocolVersion":PROTOCOL_VERSION,
        "eventId":event_id,
        "organizationId":organization_id,
        "sequence":sequence,
        "eventType":event_type,
        "subject":{"kind":subject_kind,"ref":subject_ref},
        "obligationId":obligation_id,
        "createdAt":now,
        "data":data,
    }
    payload_json=_canonical(payload)
    payload_sha=_sha_bytes(payload_json.encode("utf-8"))
    c.execute(
        """INSERT INTO syndication_delivery_events(
             id,organization_id,endpoint_id,sequence_no,event_type,subject_kind,
             subject_ref,obligation_id,payload_json,payload_sha256,created_at,
             created_by,demo_only
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            event_id,organization_id,endpoint["id"],sequence,event_type,subject_kind,
            subject_ref,obligation_id,payload_json,payload_sha,now,actor,int(bool(demo_only)),
        ),
    )
    c.execute(
        """INSERT INTO syndication_delivery_event_state(
             event_id,status,next_attempt_at,updated_at
           ) VALUES(?,'queued',?,?)""",
        (event_id,now,now),
    )
    return {
        "id":event_id,
        "organization_id":organization_id,
        "endpoint_id":endpoint["id"],
        "sequence_no":sequence,
        "event_type":event_type,
        "subject_kind":subject_kind,
        "subject_ref":subject_ref,
        "obligation_id":obligation_id,
        "payload_sha256":payload_sha,
        "created_at":now,
        "status":"queued",
        "idempotentReplay":False,
    }


def enqueue_package_delivery(c,delivery_id,actor="distribution_authority"):
    row=c.execute(
        """SELECT d.id delivery_id,d.organization_id,d.package_id,d.status delivery_status,
                  p.artifact_kind,p.artifact_ref,p.package_sha256,p.state package_state,
                  o.demo_only
           FROM evidence_exchange_deliveries d
           JOIN evidence_exchange_packages p ON p.id=d.package_id
           JOIN institutional_organizations o ON o.id=d.organization_id
           WHERE d.id=?""",
        (delivery_id,),
    ).fetchone()
    if not row:
        raise ValueError("evidence_delivery_not_found")
    if row["delivery_status"] not in ("delivered","acknowledged"):
        return None
    try:
        return create_event(
            c,row["organization_id"],"package_delivery","evidence_package",row["package_id"],
            {
                "packageId":row["package_id"],
                "packageSha256":row["package_sha256"],
                "artifact":{"kind":row["artifact_kind"],"ref":row["artifact_ref"]},
                "packageState":row["package_state"],
                "deliveryId":row["delivery_id"],
            },
            actor,demo_only=bool(row["demo_only"]),
        )
    except ValueError as exc:
        if str(exc) in ("active_webhook_endpoint_required","syndication_partner_not_qualified"):
            return None
        raise


def enqueue_obligation(c,obligation_id,actor="distribution_authority"):
    row=c.execute(
        """SELECT o.id obligation_id,o.obligation_type,o.due_at,o.status obligation_status,
                  d.id delivery_id,d.organization_id,d.package_id,
                  p.artifact_kind,p.artifact_ref,p.package_sha256,p.state package_state,
                  io.demo_only
           FROM syndication_delivery_obligations o
           JOIN evidence_exchange_deliveries d ON d.id=o.delivery_id
           JOIN evidence_exchange_packages p ON p.id=d.package_id
           JOIN institutional_organizations io ON io.id=d.organization_id
           WHERE o.id=?""",
        (obligation_id,),
    ).fetchone()
    if not row:
        raise ValueError("delivery_obligation_not_found")
    event_type="package_withdrawal" if row["obligation_type"]=="withdrawal" else "package_update"
    try:
        return create_event(
            c,row["organization_id"],event_type,"evidence_package",row["package_id"],
            {
                "packageId":row["package_id"],
                "packageSha256":row["package_sha256"],
                "artifact":{"kind":row["artifact_kind"],"ref":row["artifact_ref"]},
                "packageState":row["package_state"],
                "deliveryId":row["delivery_id"],
                "obligationId":row["obligation_id"],
                "obligationType":row["obligation_type"],
                "dueAt":row["due_at"],
            },
            actor,obligation_id=row["obligation_id"],demo_only=bool(row["demo_only"]),
        )
    except ValueError as exc:
        if str(exc) in ("active_webhook_endpoint_required","syndication_partner_not_qualified"):
            return None
        raise


def enqueue_contribution_admission(c,contribution_id,actor="contribution_authority"):
    row=c.execute(
        """SELECT ec.id,ec.organization_id,ec.contribution_type,ec.payload_sha256,
                  ec.status,ec.demo_only,r.receipt_sha256
           FROM external_contributions ec
           JOIN external_contribution_admission_receipts r ON r.contribution_id=ec.id
           WHERE ec.id=?""",
        (contribution_id,),
    ).fetchone()
    if not row:
        raise ValueError("admitted_contribution_not_found")
    if row["status"]!="admitted":
        return None
    try:
        return create_event(
            c,row["organization_id"],"contribution_admission","external_contribution",row["id"],
            {
                "contributionId":row["id"],
                "contributionType":row["contribution_type"],
                "payloadSha256":row["payload_sha256"],
                "admissionReceiptSha256":row["receipt_sha256"],
                "canonicalMutation":False,
            },
            actor,demo_only=bool(row["demo_only"]),
        )
    except ValueError as exc:
        if str(exc) in ("active_webhook_endpoint_required","syndication_partner_not_qualified"):
            return None
        raise


def _event_row(c,event_id):
    return c.execute(
        """SELECT e.id,e.organization_id,e.endpoint_id,e.sequence_no,e.event_type,
                  e.subject_kind,e.subject_ref,e.obligation_id,e.payload_json,
                  e.payload_sha256,e.created_at,e.demo_only,
                  s.status,s.next_attempt_at,s.delivered_at,s.acknowledged_at,
                  s.dead_at,s.terminal_reason
           FROM syndication_delivery_events e
           JOIN syndication_delivery_event_state s ON s.event_id=e.id
           WHERE e.id=?""",
        (event_id,),
    ).fetchone()


def _record_observation(c,organization_id,event_id,observation_type,severity,details,stable_key=None,demo_only=False):
    stable_key=stable_key or f"{event_id or organization_id}|{observation_type}|{time.time_ns()}"
    observation_id="obs:"+hashlib.sha256(stable_key.encode("utf-8")).hexdigest()[:24]
    c.execute(
        """INSERT OR IGNORE INTO syndication_delivery_observations(
             id,organization_id,event_id,observation_type,severity,details_json,
             observed_at,demo_only
           ) VALUES(?,?,?,?,?,?,?,?)""",
        (
            observation_id,organization_id,event_id,observation_type,severity,
            _canonical(details),int(time.time()),int(bool(demo_only)),
        ),
    )
    return observation_id


def _attempt_count(c,event_id):
    return int(c.execute(
        "SELECT COUNT(*) n FROM syndication_delivery_attempts WHERE event_id=?",
        (event_id,),
    ).fetchone()["n"])


def _classify_http(status):
    status=int(status or 0)
    if 200<=status<300:
        return "success"
    if status in (408,425,429) or status>=500 or status==0:
        return "retryable_failure"
    return "terminal_failure"


def dispatch_event(c,event_id,actor="delivery_worker",transport=None,now=None):
    now=int(now or time.time())
    event=_event_row(c,event_id)
    if not event:
        raise ValueError("delivery_event_not_found")
    if event["status"] in ("delivered","acknowledged","dead","cancelled"):
        return {
            "eventId":event_id,
            "status":event["status"],
            "idempotentReplay":True,
        }
    if int(event["next_attempt_at"])>now:
        return {
            "eventId":event_id,
            "status":event["status"],
            "nextAttemptAt":event["next_attempt_at"],
            "notDue":True,
        }
    endpoint=_endpoint_row(c,event["endpoint_id"])
    if not endpoint or endpoint["status"]!="active":
        raise ValueError("delivery_endpoint_not_active")
    attempts=_attempt_count(c,event_id)
    if attempts>=MAX_ATTEMPTS:
        c.execute(
            """UPDATE syndication_delivery_event_state
               SET status='dead',dead_at=?,terminal_reason='max_attempts_exhausted',updated_at=?
               WHERE event_id=?""",
            (now,now,event_id),
        )
        _record_observation(
            c,event["organization_id"],event_id,"dead_event","critical",
            {"attempts":attempts,"reason":"max_attempts_exhausted"},
            stable_key=f"dead|{event_id}",demo_only=event["demo_only"],
        )
        return {"eventId":event_id,"status":"dead","attempts":attempts}
    attempt_no=attempts+1
    secret_version=int(endpoint["secret_version"])
    secret=_endpoint_secret(endpoint["id"],secret_version)
    if _secret_hash(secret)!=endpoint["secret_hash"]:
        raise ValueError("webhook_secret_registry_mismatch")
    timestamp=now
    signature=_sign(secret,timestamp,event_id,event["payload_sha256"])
    headers={
        "Content-Type":"application/json",
        "X-Promomed-Protocol":PROTOCOL_VERSION,
        "X-Promomed-Event-Id":event_id,
        "X-Promomed-Sequence":str(event["sequence_no"]),
        "X-Promomed-Timestamp":str(timestamp),
        "X-Promomed-Payload-SHA256":event["payload_sha256"],
        "X-Promomed-Signature":signature,
        "X-Promomed-Secret-Version":str(secret_version),
    }
    body=event["payload_json"].encode("utf-8")
    sent_at=int(time.time())
    http_status=0
    raw=b""
    error_class=""
    transport=transport or _https_post
    try:
        response=transport(endpoint["endpoint_url"],body,headers)
        http_status=int(response.get("status") or 0)
        raw=response.get("body") or b""
        if isinstance(raw,str):
            raw=raw.encode("utf-8")
        classification=_classify_http(http_status)
    except Exception as exc:
        classification="retryable_failure"
        error_class=type(exc).__name__
    completed_at=int(time.time())
    next_retry_at=None
    terminal=False
    if classification=="retryable_failure":
        if attempt_no>=MAX_ATTEMPTS:
            terminal=True
        else:
            delay=RETRY_DELAYS[min(attempt_no-1,len(RETRY_DELAYS)-1)]
            next_retry_at=completed_at+int(delay)
    elif classification=="terminal_failure":
        terminal=True

    attempt_id=f"attempt:{event_id}:{attempt_no}"
    c.execute(
        """INSERT INTO syndication_delivery_attempts(
             id,event_id,endpoint_id,attempt_no,secret_version,request_timestamp,
             request_signature,sent_at,completed_at,transport_status,http_status,
             response_sha256,error_class,next_retry_at,demo_only
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            attempt_id,event_id,endpoint["id"],attempt_no,secret_version,timestamp,
            signature,sent_at,completed_at,classification,http_status or None,
            _sha_bytes(raw) if raw else "",error_class,next_retry_at,int(event["demo_only"]),
        ),
    )

    if classification=="success":
        c.execute(
            """UPDATE syndication_delivery_event_state
               SET status=CASE WHEN status='acknowledged' THEN status ELSE 'delivered' END,
                   delivered_at=COALESCE(delivered_at,?),updated_at=?
               WHERE event_id=?""",
            (completed_at,completed_at,event_id),
        )
        _record_observation(
            c,event["organization_id"],event_id,"delivery_success","info",
            {"attempt":attempt_no,"httpStatus":http_status},
            stable_key=f"delivery-success|{event_id}",demo_only=event["demo_only"],
        )
    elif terminal:
        c.execute(
            """UPDATE syndication_delivery_event_state
               SET status='dead',dead_at=?,terminal_reason=?,updated_at=?
               WHERE event_id=?""",
            (
                completed_at,
                "terminal_http_failure" if classification=="terminal_failure" else "max_attempts_exhausted",
                completed_at,event_id,
            ),
        )
        _record_observation(
            c,event["organization_id"],event_id,"delivery_terminal_failure","critical",
            {"attempt":attempt_no,"httpStatus":http_status,"errorClass":error_class},
            stable_key=f"terminal|{event_id}",demo_only=event["demo_only"],
        )
        _record_observation(
            c,event["organization_id"],event_id,"dead_event","critical",
            {"attempts":attempt_no},
            stable_key=f"dead|{event_id}",demo_only=event["demo_only"],
        )
    else:
        c.execute(
            """UPDATE syndication_delivery_event_state
               SET status='queued',next_attempt_at=?,updated_at=? WHERE event_id=?""",
            (next_retry_at,completed_at,event_id),
        )
        _record_observation(
            c,event["organization_id"],event_id,"delivery_retryable_failure","warning",
            {"attempt":attempt_no,"httpStatus":http_status,"errorClass":error_class,"nextRetryAt":next_retry_at},
            stable_key=f"retry|{event_id}|{attempt_no}",demo_only=event["demo_only"],
        )

    return {
        "eventId":event_id,
        "attemptId":attempt_id,
        "attempt":attempt_no,
        "transportStatus":classification,
        "httpStatus":http_status or None,
        "nextRetryAt":next_retry_at,
        "eventStatus":_event_row(c,event_id)["status"],
    }


def due_event_ids(c,now=None,limit=100):
    now=int(now or time.time())
    limit=max(1,min(int(limit),500))
    return [
        r["event_id"] for r in c.execute(
            """SELECT event_id FROM syndication_delivery_event_state
               WHERE status='queued' AND next_attempt_at<=?
               ORDER BY next_attempt_at,event_id LIMIT ?""",
            (now,limit),
        )
    ]


def dispatch_due(c,actor="delivery_worker",transport=None,now=None,limit=100):
    results=[]
    for event_id in due_event_ids(c,now=now,limit=limit):
        results.append(dispatch_event(c,event_id,actor=actor,transport=transport,now=now))
    return results


def _successful_attempt(c,event_id):
    return c.execute(
        """SELECT a.* FROM syndication_delivery_attempts a
           WHERE a.event_id=? AND a.transport_status='success'
           ORDER BY a.attempt_no DESC LIMIT 1""",
        (event_id,),
    ).fetchone()


def _advance_cursor(c,organization_id):
    cursor=c.execute(
        """SELECT organization_id,next_sequence,last_acked_sequence,updated_at
           FROM syndication_partner_delivery_cursors WHERE organization_id=?""",
        (organization_id,),
    ).fetchone()
    if not cursor:
        return 0
    last=int(cursor["last_acked_sequence"])
    while True:
        next_seq=last+1
        ack=c.execute(
            """SELECT 1 FROM syndication_delivery_acknowledgements
               WHERE organization_id=? AND sequence_no=?""",
            (organization_id,next_seq),
        ).fetchone()
        if not ack:
            break
        last=next_seq
    if last!=int(cursor["last_acked_sequence"]):
        c.execute(
            """UPDATE syndication_partner_delivery_cursors
               SET last_acked_sequence=?,updated_at=? WHERE organization_id=?""",
            (last,int(time.time()),organization_id),
        )
    return last


def acknowledge_event(c,event_id,organization_id,ack_payload,ack_timestamp,signature):
    event=_event_row(c,event_id)
    if not event:
        raise ValueError("delivery_event_not_found")
    if event["organization_id"]!=organization_id:
        raise ValueError("delivery_ack_organization_mismatch")
    attempt=_successful_attempt(c,event_id)
    if not attempt:
        raise ValueError("delivery_success_required_before_ack")
    if not isinstance(ack_payload,dict):
        raise ValueError("delivery_ack_payload_invalid")
    expected_event=str(ack_payload.get("eventId") or "")
    expected_payload=str(ack_payload.get("payloadSha256") or "")
    if expected_event!=event_id or expected_payload!=event["payload_sha256"]:
        raise ValueError("delivery_ack_binding_mismatch")
    if ack_payload.get("status")!="accepted":
        raise ValueError("delivery_ack_status_invalid")
    ack_timestamp=int(ack_timestamp)
    now=int(time.time())
    ack_payload_json=_canonical(ack_payload)
    ack_sha=_sha_bytes(ack_payload_json.encode("utf-8"))
    existing=c.execute(
        """SELECT id,ack_payload_sha256,ack_signature
           FROM syndication_delivery_acknowledgements WHERE event_id=?""",
        (event_id,),
    ).fetchone()
    if existing:
        if (
            existing["ack_payload_sha256"]!=ack_sha
            or existing["ack_signature"]!=str(signature or "")
        ):
            raise ValueError("delivery_ack_conflict")
        return {
            "eventId":event_id,
            "status":"acknowledged",
            "idempotentReplay":True,
            "lastAckedSequence":_advance_cursor(c,organization_id),
        }
    if abs(now-ack_timestamp)>86400:
        raise ValueError("delivery_ack_timestamp_out_of_range")
    secret=_endpoint_secret(event["endpoint_id"],attempt["secret_version"])
    if not verify_signature(secret,ack_timestamp,event_id,ack_sha,signature):
        raise ValueError("delivery_ack_signature_invalid")
    received_at=now
    ack_id="ack:"+_sha({
        "eventId":event_id,
        "organizationId":organization_id,
        "ackSha256":ack_sha,
    })[:24]
    c.execute(
        """INSERT INTO syndication_delivery_acknowledgements(
             id,event_id,endpoint_id,organization_id,sequence_no,ack_payload_json,
             ack_payload_sha256,ack_timestamp,ack_signature,received_at,demo_only
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (
            ack_id,event_id,event["endpoint_id"],organization_id,event["sequence_no"],
            ack_payload_json,ack_sha,ack_timestamp,signature,received_at,int(event["demo_only"]),
        ),
    )
    c.execute(
        """UPDATE syndication_delivery_event_state
           SET status='acknowledged',acknowledged_at=?,updated_at=? WHERE event_id=?""",
        (received_at,received_at,event_id),
    )
    observation="ack_success"
    severity="info"
    obligation_result=None
    if event["obligation_id"]:
        obligation_result=syndication_network.acknowledge_obligation(
            c,event["obligation_id"],organization_id,
            f"delivery-event:{event_id}",actor=None,
        )
        if obligation_result.get("status")=="breached":
            observation="ack_late"
            severity="critical"
            _record_observation(
                c,organization_id,event_id,"sla_breach","critical",
                {
                    "obligationId":event["obligation_id"],
                    "obligationType":obligation_result.get("obligation_type"),
                    "dueAt":obligation_result.get("due_at"),
                    "acknowledgedAt":obligation_result.get("acknowledged_at"),
                },
                stable_key=f"sla-breach|{event['obligation_id']}",
                demo_only=event["demo_only"],
            )
    _record_observation(
        c,organization_id,event_id,observation,severity,
        {"sequence":event["sequence_no"],"obligationId":event["obligation_id"]},
        stable_key=f"ack|{event_id}",demo_only=event["demo_only"],
    )
    last=_advance_cursor(c,organization_id)
    return {
        "eventId":event_id,
        "status":"acknowledged",
        "acknowledgementId":ack_id,
        "lastAckedSequence":last,
        "obligation":obligation_result,
        "idempotentReplay":False,
    }


def reconcile_sla(c,now=None):
    now=int(now or time.time())
    syndication_network.mark_overdue_obligations(c,now=now)
    missing_ack_rows=list(c.execute(
        """SELECT e.id,e.organization_id,e.sequence_no,e.demo_only,s.delivered_at
           FROM syndication_delivery_events e
           JOIN syndication_delivery_event_state s ON s.event_id=e.id
           WHERE s.status='delivered' AND s.delivered_at IS NOT NULL
             AND s.delivered_at<=?""",
        (now-ACK_EXPECTATION_SECONDS,),
    ))
    for item in missing_ack_rows:
        _record_observation(
            c,item["organization_id"],item["id"],"ack_missing","warning",
            {
                "sequence":item["sequence_no"],
                "deliveredAt":item["delivered_at"],
                "expectedWithinSeconds":ACK_EXPECTATION_SECONDS,
            },
            stable_key=f"ack-missing|{item['id']}",
            demo_only=bool(item["demo_only"]),
        )
    rows=list(c.execute(
        """SELECT o.id obligation_id,o.obligation_type,o.due_at,o.acknowledged_at,
                  d.organization_id,e.id event_id,e.demo_only
           FROM syndication_delivery_obligations o
           JOIN evidence_exchange_deliveries d ON d.id=o.delivery_id
           LEFT JOIN syndication_delivery_events e ON e.obligation_id=o.id
           WHERE o.status='breached'"""
    ))
    observations=0
    organizations=set()
    for row in rows:
        organizations.add(row["organization_id"])
        _record_observation(
            c,row["organization_id"],row["event_id"],"sla_breach","critical",
            {
                "obligationId":row["obligation_id"],
                "obligationType":row["obligation_type"],
                "dueAt":row["due_at"],
                "acknowledgedAt":row["acknowledged_at"],
            },
            stable_key=f"sla-breach|{row['obligation_id']}",
            demo_only=bool(row["demo_only"] or 0),
        )
        observations+=1
    evaluations=[evaluate_requalification(c,org,now=now) for org in sorted(organizations)]
    return {
        "breachedObligations":len(rows),
        "missingAcknowledgements":len(missing_ack_rows),
        "observationsProcessed":observations+len(missing_ack_rows),
        "evaluations":evaluations,
    }


def behavior_scorecard(c,organization_id,now=None,window_seconds=30*86400):
    _organization(c,organization_id)
    now=int(now or time.time())
    since=now-int(window_seconds)
    events=int(c.execute(
        "SELECT COUNT(*) n FROM syndication_delivery_events WHERE organization_id=? AND created_at>=?",
        (organization_id,since),
    ).fetchone()["n"])
    attempts=list(c.execute(
        """SELECT a.transport_status,a.http_status
           FROM syndication_delivery_attempts a
           JOIN syndication_delivery_events e ON e.id=a.event_id
           WHERE e.organization_id=? AND a.completed_at>=?""",
        (organization_id,since),
    ))
    observations=[dict(r) for r in c.execute(
        """SELECT observation_type,severity,observed_at,details_json
           FROM syndication_delivery_observations
           WHERE organization_id=? AND observed_at>=?""",
        (organization_id,since),
    )]
    acked=int(c.execute(
        """SELECT COUNT(*) n FROM syndication_delivery_acknowledgements
           WHERE organization_id=? AND received_at>=?""",
        (organization_id,since),
    ).fetchone()["n"])
    cursor=c.execute(
        """SELECT next_sequence,last_acked_sequence,updated_at
           FROM syndication_partner_delivery_cursors WHERE organization_id=?""",
        (organization_id,),
    ).fetchone()
    counts={}
    for item in observations:
        counts[item["observation_type"]]=counts.get(item["observation_type"],0)+1
    attempts_total=len(attempts)
    success_attempts=sum(1 for x in attempts if x["transport_status"]=="success")
    return {
        "organizationId":organization_id,
        "protocolVersion":PROTOCOL_VERSION,
        "windowSeconds":int(window_seconds),
        "windowStart":since,
        "windowEnd":now,
        "events":events,
        "acknowledgedEvents":acked,
        "attempts":attempts_total,
        "successfulAttempts":success_attempts,
        "retryableFailures":sum(1 for x in attempts if x["transport_status"]=="retryable_failure"),
        "terminalFailures":sum(1 for x in attempts if x["transport_status"]=="terminal_failure"),
        "deliverySuccessRate":round(success_attempts/attempts_total,4) if attempts_total else None,
        "observations":counts,
        "cursor":{
            "nextSequence":cursor["next_sequence"] if cursor else 1,
            "lastAckedSequence":cursor["last_acked_sequence"] if cursor else 0,
            "updatedAt":cursor["updated_at"] if cursor else None,
        },
        "truthBoundary":{
            "productionTrafficObserved":bool(events and not any(bool(r["demo_only"]) for r in c.execute(
                "SELECT demo_only FROM syndication_delivery_events WHERE organization_id=? AND created_at>=?",
                (organization_id,since),
            ))),
            "medicalEfficacyMeasured":False,
            "commercialOutcomeMeasured":False,
        },
    }


def evaluate_requalification(c,organization_id,now=None):
    now=int(now or time.time())
    q=syndication_network.refresh_qualification_state(c,organization_id,now=now)
    score=behavior_scorecard(c,organization_id,now=now)
    obs=score["observations"]
    sla_breaches=int(obs.get("sla_breach",0))
    dead_events=int(obs.get("dead_event",0))
    retryable=int(score["retryableFailures"])
    missing_ack=int(obs.get("ack_missing",0))
    critical_withdrawal=False
    for row in c.execute(
        """SELECT details_json FROM syndication_delivery_observations
           WHERE organization_id=? AND observation_type='sla_breach'
             AND observed_at>=?""",
        (organization_id,now-30*86400),
    ):
        try:
            if json.loads(row["details_json"]).get("obligationType")=="withdrawal":
                critical_withdrawal=True
                break
        except Exception:
            pass
    requalification=(
        sla_breaches>=2 or dead_events>=2 or retryable>=10
        or missing_ack>=3 or critical_withdrawal
    )
    suspension_review=(critical_withdrawal or dead_events>=3)
    changed=False
    if requalification and q and q["status"]=="qualified":
        reason=(
            "Observed delivery behaviour requires requalification: "
            f"sla_breaches={sla_breaches}, dead_events={dead_events}, "
            f"retryable_failures={retryable}, missing_acknowledgements={missing_ack}."
        )
        c.execute(
            """UPDATE syndication_partner_qualifications
               SET status='requalification_due',reason=?
               WHERE id=? AND status='qualified'""",
            (reason[:500],q["id"]),
        )
        changed=True
    return {
        "organizationId":organization_id,
        "requalificationDue":bool(requalification),
        "qualificationStateChanged":changed,
        "suspensionReviewRecommended":bool(suspension_review),
        "automaticSuspension":False,
        "automaticRevocation":False,
        "evidence":{
            "slaBreaches":sla_breaches,
            "deadEvents":dead_events,
            "retryableFailures":retryable,
            "missingAcknowledgements":missing_ack,
            "withdrawalSlaBreach":critical_withdrawal,
        },
        "ruleVersion":"promomed-delivery-behaviour-requalification-v1",
    }


def endpoint_snapshot(c,organization_id=None):
    params=()
    where=""
    if organization_id:
        _organization(c,organization_id)
        where="WHERE organization_id=?"
        params=(organization_id,)
    endpoints=[
        _endpoint_document(r) for r in c.execute(
            f"""SELECT id,organization_id,endpoint_url,status,secret_version,secret_hash,
                       verification_challenge,verified_at,verified_by,last_rotated_at,
                       last_rotated_by,created_at,created_by,demo_only
                FROM syndication_delivery_endpoints {where}
                ORDER BY organization_id,created_at,id""",
            params,
        )
    ]
    return endpoints


def runtime_snapshot(c,organization_id=None):
    reconcile_sla(c)
    orgs=[organization_id] if organization_id else [
        r["organization_id"] for r in c.execute(
            "SELECT DISTINCT organization_id FROM syndication_delivery_endpoints ORDER BY organization_id"
        )
    ]
    events=[]
    attempts=[]
    for org in orgs:
        events.extend(dict(r) for r in c.execute(
            """SELECT e.id,e.organization_id,e.endpoint_id,e.sequence_no,e.event_type,
                      e.subject_kind,e.subject_ref,e.obligation_id,e.payload_sha256,
                      e.created_at,s.status,s.next_attempt_at,s.delivered_at,
                      s.acknowledged_at,s.dead_at,s.terminal_reason,e.demo_only
               FROM syndication_delivery_events e
               JOIN syndication_delivery_event_state s ON s.event_id=e.id
               WHERE e.organization_id=?
               ORDER BY e.sequence_no DESC LIMIT 100""",
            (org,),
        ))
        attempts.extend(dict(r) for r in c.execute(
            """SELECT a.id,a.event_id,a.attempt_no,a.secret_version,a.sent_at,
                      a.completed_at,a.transport_status,a.http_status,a.error_class,
                      a.next_retry_at
               FROM syndication_delivery_attempts a
               JOIN syndication_delivery_events e ON e.id=a.event_id
               WHERE e.organization_id=?
               ORDER BY a.completed_at DESC,a.attempt_no DESC LIMIT 200""",
            (org,),
        ))
    endpoint_docs=endpoint_snapshot(c,organization_id)
    production_endpoint=any(
        not x["demoOnly"] and x["status"]=="active" for x in endpoint_docs
    )
    production_success=bool(c.execute(
        """SELECT 1 FROM syndication_delivery_attempts a
           JOIN syndication_delivery_events e ON e.id=a.event_id
           WHERE e.demo_only=0 AND a.transport_status='success' LIMIT 1"""
    ).fetchone())
    production_ack=bool(c.execute(
        """SELECT 1 FROM syndication_delivery_acknowledgements
           WHERE demo_only=0 LIMIT 1"""
    ).fetchone())
    return {
        "version":PROTOCOL_VERSION,
        "endpoints":endpoint_docs,
        "events":events,
        "attempts":attempts,
        "scorecards":[behavior_scorecard(c,org) for org in orgs],
        "requalification":[evaluate_requalification(c,org) for org in orgs],
        "truthBoundary":{
            "signedWebhookProtocolImplemented":True,
            "productionExternalEndpointConfigured":production_endpoint,
            "productionDeliveryObserved":production_success,
            "productionAcknowledgementObserved":production_ack,
            "automaticPartnerRevocation":False,
            "medicalEfficacyCertified":False,
        },
    }
