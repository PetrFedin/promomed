import hashlib
import json
import time

from app import delivery_protocol, evidence_checkpoint, syndication_network


SNAPSHOT_VERSION="promomed-institutional-status-snapshot-v1"
SNAPSHOT_STATEMENT_TYPE="promomed-institutional-status-snapshot-v1"
STATUS_STATEMENT_TYPE="promomed-institutional-snapshot-status-v1"
BUNDLE_VERSION="promomed-partner-trust-bundle-v1"
BUNDLE_SCHEMA_ID="urn:promomed:schema:partner-trust-bundle:v1"
DEFAULT_SNAPSHOT_VALIDITY=7*86400
DEFAULT_STATUS_VALIDITY=86400
OBSERVATION_WINDOW=30*86400


def _canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)


def _sha(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _organization(c,organization_id):
    row=c.execute(
        """SELECT id,name,organization_type,status,demo_only
           FROM institutional_organizations WHERE id=?""",
        (organization_id,),
    ).fetchone()
    if not row:
        raise ValueError("organization_not_found")
    if row["status"]!="active":
        raise ValueError("organization_not_active")
    return row


def _snapshot_event(c,snapshot_id,event_type,actor,payload,demo_only=False,now=None):
    now=int(now or time.time())
    core={
        "snapshotId":snapshot_id,
        "eventType":event_type,
        "actorRole":"governance",
        "payload":payload,
        "createdAt":now,
    }
    digest=_sha(core)
    event_id="trust-event:"+digest[:24]
    c.execute(
        """INSERT INTO institutional_status_snapshot_events(
             id,snapshot_id,event_type,actor,payload_json,event_sha256,created_at,demo_only
           ) VALUES(?,?,?,?,?,?,?,?)
           ON CONFLICT(event_sha256) DO NOTHING""",
        (
            event_id,snapshot_id,event_type,actor,_canonical(core),digest,now,
            int(bool(demo_only)),
        ),
    )
    return event_id


def _current_projection(c,organization_id,now=None):
    now=int(now or time.time())
    org=_organization(c,organization_id)
    certification=syndication_network.public_certification(c,organization_id)
    scorecard=delivery_protocol.behavior_scorecard(
        c,organization_id,now=now,window_seconds=OBSERVATION_WINDOW
    )
    requalification=delivery_protocol.evaluate_requalification(
        c,organization_id,now=now,apply=False
    )
    endpoints=delivery_protocol.endpoint_snapshot(c,organization_id)
    endpoint_counts={"pending_verification":0,"active":0,"suspended":0,"revoked":0}
    for endpoint in endpoints:
        if endpoint.get("status") in endpoint_counts:
            endpoint_counts[endpoint["status"]]+=1
    return {
        "organization":{
            "id":org["id"],
            "name":org["name"],
            "type":org["organization_type"],
        },
        "certification":{
            "qualificationStatus":certification["qualificationStatus"],
            "qualificationVersion":certification["qualificationVersion"],
            "effectiveAt":certification["effectiveAt"],
            "validUntil":certification["validUntil"],
            "nextRequalificationAt":certification["nextRequalificationAt"],
            "certifications":certification["certifications"],
        },
        "deliveryTrust":{
            "protocolVersion":delivery_protocol.PROTOCOL_VERSION,
            "endpointStateCounts":endpoint_counts,
            "hasActiveEndpoint":endpoint_counts["active"]>0,
            "cursor":scorecard["cursor"],
            "observationWindow":{
                "windowSeconds":scorecard["windowSeconds"],
                "windowStart":scorecard["windowStart"],
                "windowEnd":scorecard["windowEnd"],
            },
            "events":scorecard["events"],
            "acknowledgedEvents":scorecard["acknowledgedEvents"],
            "attempts":scorecard["attempts"],
            "successfulAttempts":scorecard["successfulAttempts"],
            "retryableFailures":scorecard["retryableFailures"],
            "terminalFailures":scorecard["terminalFailures"],
            "observations":scorecard["observations"],
        },
        "requalification":{
            "requalificationDue":requalification["requalificationDue"],
            "suspensionReviewRecommended":requalification["suspensionReviewRecommended"],
            "automaticSuspension":False,
            "automaticRevocation":False,
            "evidence":requalification["evidence"],
            "ruleVersion":requalification["ruleVersion"],
        },
        "truthBoundary":{
            "technicalProcessStatusOnly":True,
            "medicalEfficacyCertified":False,
            "medicalSafetyCertified":False,
            "professionalAccreditation":False,
            "commercialEndorsement":False,
        },
    }


def issue_snapshot(c,organization_id,actor,validity_seconds=DEFAULT_SNAPSHOT_VALIDITY,now=None):
    now=int(now or time.time())
    validity_seconds=int(validity_seconds)
    if validity_seconds<3600 or validity_seconds>30*86400:
        raise ValueError("status_snapshot_validity_invalid")
    org=_organization(c,organization_id)
    projection=_current_projection(c,organization_id,now=now)
    fingerprint=_sha(projection)
    current=c.execute(
        """SELECT s.id,s.snapshot_sha256,s.envelope_json,s.valid_until
           FROM institutional_status_snapshots s
           JOIN institutional_status_snapshot_state st ON st.snapshot_id=s.id
           WHERE s.organization_id=? AND st.status='current'
           ORDER BY s.issued_at DESC,s.id DESC LIMIT 1""",
        (organization_id,),
    ).fetchone()
    if current:
        existing=json.loads(current["envelope_json"])
        body=(existing.get("payload") or {}).get("body") or {}
        if body.get("statusFingerprint")==fingerprint and int(current["valid_until"])>now:
            return {
                "id":current["id"],
                "snapshotSha256":current["snapshot_sha256"],
                "envelope":existing,
                "status":"current",
                "idempotentReplay":True,
            }

    body={
        "snapshotVersion":SNAPSHOT_VERSION,
        "organizationId":organization_id,
        "statusFingerprint":fingerprint,
        "validFrom":now,
        "validUntil":now+validity_seconds,
        "state":projection,
        "currentPromomedStateVerifiedAtIssuance":True,
        "medicalEfficacyCertified":False,
    }
    envelope=evidence_checkpoint.sign_portable_statement(
        c,SNAPSHOT_STATEMENT_TYPE,body,actor=actor
    )
    snapshot_sha=envelope["statementSha256"]
    snapshot_id="status:"+snapshot_sha[:24]

    if current:
        c.execute(
            """UPDATE institutional_status_snapshot_state
               SET status='superseded',updated_at=?
               WHERE snapshot_id=? AND status='current'""",
            (now,current["id"]),
        )
        _snapshot_event(
            c,current["id"],"superseded",actor,
            {"supersededBySnapshotId":snapshot_id},
            demo_only=bool(org["demo_only"]),now=now,
        )

    c.execute(
        """INSERT INTO institutional_status_snapshots(
             id,organization_id,schema_version,snapshot_sha256,envelope_json,
             issued_at,valid_until,supersedes_snapshot_id,created_by,demo_only
           ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (
            snapshot_id,organization_id,SNAPSHOT_VERSION,snapshot_sha,
            _canonical(envelope),now,now+validity_seconds,
            current["id"] if current else None,actor,int(org["demo_only"]),
        ),
    )
    c.execute(
        """INSERT INTO institutional_status_snapshot_state(
             snapshot_id,status,updated_at
           ) VALUES(?,'current',?)""",
        (snapshot_id,now),
    )
    _snapshot_event(
        c,snapshot_id,"issued",actor,
        {"snapshotSha256":snapshot_sha,"validUntil":now+validity_seconds},
        demo_only=bool(org["demo_only"]),now=now,
    )
    return {
        "id":snapshot_id,
        "snapshotSha256":snapshot_sha,
        "envelope":envelope,
        "status":"current",
        "idempotentReplay":False,
    }


def snapshot_document(c,snapshot_id):
    row=c.execute(
        """SELECT s.id,s.organization_id,s.schema_version,s.snapshot_sha256,
                  s.envelope_json,s.issued_at,s.valid_until,s.supersedes_snapshot_id,
                  s.demo_only,st.status,st.revoked_at,st.revocation_reason
           FROM institutional_status_snapshots s
           JOIN institutional_status_snapshot_state st ON st.snapshot_id=s.id
           WHERE s.id=?""",
        (snapshot_id,),
    ).fetchone()
    if not row:
        raise ValueError("status_snapshot_not_found")
    return {
        "id":row["id"],
        "organizationId":row["organization_id"],
        "schemaVersion":row["schema_version"],
        "snapshotSha256":row["snapshot_sha256"],
        "envelope":json.loads(row["envelope_json"]),
        "issuedAt":row["issued_at"],
        "validUntil":row["valid_until"],
        "supersedesSnapshotId":row["supersedes_snapshot_id"],
        "status":row["status"],
        "revokedAt":row["revoked_at"],
        "revocationReason":row["revocation_reason"],
        "demoOnly":bool(row["demo_only"]),
    }


def revoke_snapshot(c,snapshot_id,reason,actor,now=None):
    now=int(now or time.time())
    reason=str(reason or "").strip()
    if len(reason)<3 or len(reason)>500:
        raise ValueError("status_snapshot_revocation_reason_invalid")
    row=c.execute(
        """SELECT s.id,s.demo_only,st.status
           FROM institutional_status_snapshots s
           JOIN institutional_status_snapshot_state st ON st.snapshot_id=s.id
           WHERE s.id=?""",
        (snapshot_id,),
    ).fetchone()
    if not row:
        raise ValueError("status_snapshot_not_found")
    if row["status"]=="revoked":
        return snapshot_document(c,snapshot_id)
    c.execute(
        """UPDATE institutional_status_snapshot_state
           SET status='revoked',revoked_at=?,revoked_by=?,revocation_reason=?,updated_at=?
           WHERE snapshot_id=?""",
        (now,actor,reason,now,snapshot_id),
    )
    _snapshot_event(
        c,snapshot_id,"revoked",actor,{"reason":reason},
        demo_only=bool(row["demo_only"]),now=now,
    )
    return snapshot_document(c,snapshot_id)
