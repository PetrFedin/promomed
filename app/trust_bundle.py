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


def signed_status_statement(c,organization_id,actor,validity_seconds=DEFAULT_STATUS_VALIDITY,now=None):
    now=int(now or time.time())
    validity_seconds=int(validity_seconds)
    if validity_seconds<300 or validity_seconds>7*86400:
        raise ValueError("snapshot_status_validity_invalid")
    _organization(c,organization_id)
    rows=list(c.execute(
        """SELECT s.id,s.snapshot_sha256,s.issued_at,s.valid_until,
                  st.status,st.revoked_at,st.revocation_reason
           FROM institutional_status_snapshots s
           JOIN institutional_status_snapshot_state st ON st.snapshot_id=s.id
           WHERE s.organization_id=?
           ORDER BY s.issued_at,s.id""",
        (organization_id,),
    ))
    body={
        "statusVersion":"promomed-institutional-snapshot-status-v1",
        "organizationId":organization_id,
        "generatedAt":now,
        "validUntil":now+validity_seconds,
        "snapshots":[
            {
                "snapshotId":r["id"],
                "snapshotSha256":r["snapshot_sha256"],
                "issuedAt":r["issued_at"],
                "validUntil":r["valid_until"],
                "status":r["status"],
                "revokedAt":r["revoked_at"],
                "revocationReason":r["revocation_reason"],
            }
            for r in rows
        ],
        "medicalEfficacyCertified":False,
    }
    return evidence_checkpoint.sign_portable_statement(
        c,STATUS_STATEMENT_TYPE,body,actor=actor
    )


def create_trust_bundle(c,snapshot_id,actor,now=None):
    now=int(now or time.time())
    snapshot=snapshot_document(c,snapshot_id)
    existing=c.execute(
        """SELECT id,bundle_sha256,bundle_json FROM institutional_trust_bundles
           WHERE snapshot_id=?""",
        (snapshot_id,),
    ).fetchone()
    if existing:
        return {
            "id":existing["id"],
            "bundleSha256":existing["bundle_sha256"],
            "bundle":json.loads(existing["bundle_json"]),
            "idempotentReplay":True,
        }
    issuer_id=(snapshot["envelope"].get("payload") or {}).get("issuerId")
    issuer_doc=evidence_checkpoint.issuer_document(c,issuer_id)
    issuer_status=evidence_checkpoint.status_list(c,issuer_id)
    status_statement=signed_status_statement(
        c,snapshot["organizationId"],actor,now=now
    )
    payload={
        "schemaId":BUNDLE_SCHEMA_ID,
        "bundleVersion":BUNDLE_VERSION,
        "createdAt":now,
        "snapshot":{
            "snapshotId":snapshot["id"],
            "snapshotSha256":snapshot["snapshotSha256"],
            "envelope":snapshot["envelope"],
        },
        "issuerDocument":issuer_doc,
        "issuerStatusAtPackaging":issuer_status,
        "snapshotStatusAtPackaging":status_statement,
        "truthBoundary":{
            "processAndIntegrationStatusOnly":True,
            "medicalEfficacyCertified":False,
            "medicalSafetyCertified":False,
            "professionalAccreditation":False,
            "commercialEndorsement":False,
            "currentPromomedStateRequiresFreshStatusMaterial":True,
        },
    }
    bundle_sha=_sha(payload)
    bundle={**payload,"bundleSha256":bundle_sha}
    bundle_id="trust:"+bundle_sha[:24]
    c.execute(
        """INSERT INTO institutional_trust_bundles(
             id,snapshot_id,bundle_version,bundle_sha256,bundle_json,
             created_at,created_by,demo_only
           ) VALUES(?,?,?,?,?,?,?,?)""",
        (
            bundle_id,snapshot_id,BUNDLE_VERSION,bundle_sha,_canonical(bundle),
            now,actor,int(snapshot["demoOnly"]),
        ),
    )
    return {
        "id":bundle_id,
        "bundleSha256":bundle_sha,
        "bundle":bundle,
        "idempotentReplay":False,
    }


def bundle_document(c,bundle_id):
    row=c.execute(
        """SELECT id,snapshot_id,bundle_version,bundle_sha256,bundle_json,
                  created_at,demo_only
           FROM institutional_trust_bundles WHERE id=?""",
        (bundle_id,),
    ).fetchone()
    if not row:
        raise ValueError("trust_bundle_not_found")
    return {
        "id":row["id"],
        "snapshotId":row["snapshot_id"],
        "bundleVersion":row["bundle_version"],
        "bundleSha256":row["bundle_sha256"],
        "bundle":json.loads(row["bundle_json"]),
        "createdAt":row["created_at"],
        "demoOnly":bool(row["demo_only"]),
    }


def _verify_status_statement(statement,issuer_doc,organization_id,snapshot_sha,now):
    verification=evidence_checkpoint.verify_portable_statement(statement,issuer_doc)
    if verification.get("status")!="VALID_PORTABLE_STATEMENT":
        return {"status":verification.get("status"),"valid":False}
    if verification.get("statementType")!=STATUS_STATEMENT_TYPE:
        return {"status":"WRONG_STATUS_STATEMENT_TYPE","valid":False}
    body=(statement.get("payload") or {}).get("body") or {}
    if body.get("organizationId")!=organization_id:
        return {"status":"STATUS_ORGANIZATION_MISMATCH","valid":False}
    try:
        if int(body.get("validUntil") or 0)<int(now):
            return {"status":"STATUS_STATEMENT_EXPIRED","valid":False}
    except (TypeError,ValueError):
        return {"status":"INVALID_STATUS_STATEMENT","valid":False}
    record=next(
        (x for x in (body.get("snapshots") or []) if x.get("snapshotSha256")==snapshot_sha),
        None,
    )
    if not record:
        return {"status":"SNAPSHOT_STATUS_UNKNOWN","valid":False}
    return {
        "status":"VALID_STATUS_STATEMENT",
        "valid":True,
        "snapshotStatus":record.get("status"),
        "revokedAt":record.get("revokedAt"),
        "revocationReason":record.get("revocationReason"),
        "statusGeneratedAt":body.get("generatedAt"),
        "statusValidUntil":body.get("validUntil"),
    }


def verify_bundle_portable(bundle,current_status_statement=None,current_issuer_document=None,now=None):
    now=int(now or time.time())
    try:
        if bundle.get("schemaId")!=BUNDLE_SCHEMA_ID or bundle.get("bundleVersion")!=BUNDLE_VERSION:
            return {"status":"INVALID_BUNDLE_SCHEMA","bundleHashValid":False}
        expected=_sha({k:v for k,v in bundle.items() if k!="bundleSha256"})
        if expected!=str(bundle.get("bundleSha256") or ""):
            return {"status":"INVALID_BUNDLE_HASH","bundleHashValid":False}

        snapshot=bundle["snapshot"]
        envelope=snapshot["envelope"]
        snapshot_sha=str(snapshot.get("snapshotSha256") or "")
        if snapshot_sha!=str(envelope.get("statementSha256") or ""):
            return {"status":"SNAPSHOT_HASH_MISMATCH","bundleHashValid":True}

        issuer_doc=current_issuer_document or bundle.get("issuerDocument") or {}
        verification=evidence_checkpoint.verify_portable_statement(envelope,issuer_doc)
        if verification.get("status")!="VALID_PORTABLE_STATEMENT":
            status=verification.get("status") or "INVALID_SIGNATURE"
            if status=="ISSUER_KEY_REVOKED":
                status="REVOKED_ISSUER_KEY"
            return {
                "status":status,
                "bundleHashValid":True,
                "snapshotSignatureValid":bool(verification.get("signature_valid")),
                "currentPromomedStateVerified":False,
            }
        if verification.get("statementType")!=SNAPSHOT_STATEMENT_TYPE:
            return {
                "status":"WRONG_SNAPSHOT_STATEMENT_TYPE",
                "bundleHashValid":True,
                "snapshotSignatureValid":True,
                "currentPromomedStateVerified":False,
            }

        body=(envelope.get("payload") or {}).get("body") or {}
        if body.get("snapshotVersion")!=SNAPSHOT_VERSION:
            return {
                "status":"INVALID_SNAPSHOT_VERSION",
                "bundleHashValid":True,
                "snapshotSignatureValid":True,
                "currentPromomedStateVerified":False,
            }
        organization_id=body.get("organizationId")
        try:
            if int(body.get("validUntil") or 0)<now:
                return {
                    "status":"EXPIRED_SNAPSHOT",
                    "bundleHashValid":True,
                    "snapshotSignatureValid":True,
                    "snapshotExpired":True,
                    "currentPromomedStateVerified":False,
                }
        except (TypeError,ValueError):
            return {"status":"INVALID_SNAPSHOT","bundleHashValid":True}

        status_statement=current_status_statement or bundle.get("snapshotStatusAtPackaging") or {}
        status_result=_verify_status_statement(
            status_statement,issuer_doc,organization_id,snapshot_sha,now
        )
        if not status_result.get("valid"):
            return {
                "status":status_result.get("status"),
                "bundleHashValid":True,
                "snapshotSignatureValid":True,
                "currentPromomedStateVerified":False,
            }
        is_fresh_external=bool(current_status_statement and current_issuer_document)
        if status_result.get("snapshotStatus")=="revoked":
            return {
                "status":"REVOKED_SNAPSHOT",
                "bundleHashValid":True,
                "snapshotSignatureValid":True,
                "snapshotExpired":False,
                "revocation":{
                    "revokedAt":status_result.get("revokedAt"),
                    "reason":status_result.get("revocationReason"),
                },
                "currentPromomedStateVerified":is_fresh_external,
            }
        return {
            "status":"VALID_TRUST_BUNDLE",
            "bundleHashValid":True,
            "snapshotSignatureValid":True,
            "snapshotExpired":False,
            "snapshotStatus":status_result.get("snapshotStatus"),
            "snapshotSha256":snapshot_sha,
            "organizationId":organization_id,
            "issuerId":verification.get("issuerId"),
            "keyId":verification.get("keyId"),
            "statusGeneratedAt":status_result.get("statusGeneratedAt"),
            "statusValidUntil":status_result.get("statusValidUntil"),
            "currentPromomedStateVerified":is_fresh_external,
            "medicalEfficacyCertified":False,
        }
    except (KeyError,TypeError,ValueError):
        return {
            "status":"INVALID_TRUST_BUNDLE",
            "bundleHashValid":False,
            "currentPromomedStateVerified":False,
        }
