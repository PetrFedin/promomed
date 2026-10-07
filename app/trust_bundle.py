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
