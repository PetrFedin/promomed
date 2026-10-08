import hashlib
import json
import os
import time
from urllib.parse import quote

from app import evidence_checkpoint, federated_trust


PROFILE_VERSION="promomed-federation-interop-v1"
DISCOVERY_VERSION="promomed-federation-discovery-v1"
DISCOVERY_STATEMENT_TYPE="promomed-federation-discovery-bundle-v1"
DEFAULT_BUNDLE_VALIDITY=86400


def _canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)


def _sha(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def profile_definition():
    return {
        "profileVersion":PROFILE_VERSION,
        "identity":{
            "canonicalOrganizationId":"Promomed institutional organization ID",
            "didMethods":["did:web"],
            "didHostingAuthority":"Promomed",
            "externalDomainControlRequired":False,
        },
        "cryptography":{
            "signatureAlgorithms":["Ed25519"],
            "jwks":{
                "kty":["OKP"],
                "crv":["Ed25519"],
                "alg":["EdDSA"],
            },
            "externalPrivateKeyCustody":"institution",
        },
        "portableStatements":{
            "required":[
                "promomed-institutional-status-snapshot-v1",
                "promomed-institutional-snapshot-status-v1",
                "promomed-federated-anchor-status-v1",
            ],
            "receipts":[
                "promomed-institution-signed-verification-receipt-v1",
            ],
        },
        "statusSemantics":{
            "anchorStates":[
                "pending_proof","pending_governance","active",
                "retired","suspended","revoked",
            ],
            "currentSigningStates":["active"],
            "historicalVerificationStates":["active","retired"],
            "untrustedStates":["suspended","revoked"],
        },
        "freshness":{
            "anchorStatusMaxAgeSeconds":86400,
            "trustStatusMaxAgeSeconds":86400,
            "discoveryBundleMaxAgeSeconds":86400,
        },
        "surfaces":{
            "did":"/trust/{organization_id}/did.json",
            "jwks":"/trust/{organization_id}/jwks.json",
            "federationRegistry":"/api/federation",
            "receipt":"/api/federation/receipt?id={receipt_id}",
            "portableReceiptVerification":"/api/federation/receipt/verify-portable",
            "discoveryManifest":"/.well-known/promomed-federation.json",
            "interoperabilityProfile":"/api/federation/profile",
            "discoveryBundle":"/api/federation/discovery-bundle?id={bundle_id}",
        },
        "governance":{
            "discoveryDoesNotAdmitKeys":True,
            "proofOfPossessionRequiredBeforeActivation":True,
            "governanceActivationRequired":True,
            "automaticExternalAccreditation":False,
        },
        "truthBoundary":{
            "profileCompatibilityIsNotAccreditation":True,
            "profileCompatibilityIsNotEndorsement":True,
            "profileCompatibilityIsNotMedicalCertification":True,
            "externalAdoptionInferred":False,
        },
    }


def ensure_profile(c,actor="system",now=None):
    now=int(now or time.time())
    definition=profile_definition()
    digest=_sha(definition)
    profile_id="fip:"+digest[:24]
    row=c.execute(
        """SELECT id,profile_version,profile_sha256,profile_json,status,effective_at
           FROM federation_interoperability_profiles
           WHERE profile_version=?""",
        (PROFILE_VERSION,),
    ).fetchone()
    if row:
        if row["profile_sha256"]!=digest:
            raise ValueError("interoperability_profile_version_collision")
        return {
            "id":row["id"],
            "profileVersion":row["profile_version"],
            "profileSha256":row["profile_sha256"],
            "profile":json.loads(row["profile_json"]),
            "status":row["status"],
            "effectiveAt":row["effective_at"],
            "idempotentReplay":True,
        }
    c.execute(
        """INSERT INTO federation_interoperability_profiles(
             id,profile_version,profile_sha256,profile_json,status,
             effective_at,created_at,created_by
           ) VALUES(?,?,?,?,'active',?,?,?)""",
        (profile_id,PROFILE_VERSION,digest,_canonical(definition),now,now,actor),
    )
    return {
        "id":profile_id,
        "profileVersion":PROFILE_VERSION,
        "profileSha256":digest,
        "profile":definition,
        "status":"active",
        "effectiveAt":now,
        "idempotentReplay":False,
    }


def public_profile(c):
    definition=profile_definition()
    digest=_sha(definition)
    profile_id="fip:"+digest[:24]
    row=c.execute(
        """SELECT id,profile_version,profile_sha256,profile_json,status,effective_at
           FROM federation_interoperability_profiles
           WHERE profile_version=?""",
        (PROFILE_VERSION,),
    ).fetchone()
    if row:
        if row["profile_sha256"]!=digest:
            raise ValueError("interoperability_profile_version_collision")
        return {
            "id":row["id"],
            "profileVersion":row["profile_version"],
            "profileSha256":row["profile_sha256"],
            "profile":json.loads(row["profile_json"]),
            "status":row["status"],
            "effectiveAt":row["effective_at"],
            "persisted":True,
        }
    return {
        "id":profile_id,
        "profileVersion":PROFILE_VERSION,
        "profileSha256":digest,
        "profile":definition,
        "status":"active",
        "effectiveAt":None,
        "persisted":False,
    }


def _public_base():
    host=federated_trust.trust_host()
    return "https://"+host


def discovery_manifest(c):
    profile=public_profile(c)
    base=_public_base()
    return {
        "discoveryVersion":DISCOVERY_VERSION,
        "generatedAt":int(time.time()),
        "profile":{
            "id":profile["id"],
            "version":profile["profileVersion"],
            "sha256":profile["profileSha256"],
            "url":base+"/api/federation/profile",
        },
        "issuer":{
            "didHost":federated_trust.trust_host(),
            "didPattern":base+"/trust/{organization_id}/did.json",
            "jwksPattern":base+"/trust/{organization_id}/jwks.json",
        },
        "verification":{
            "receiptEndpoint":base+"/api/federation/receipt?id={receipt_id}",
            "portableVerificationEndpoint":base+"/api/federation/receipt/verify-portable",
        },
        "truthBoundary":{
            "discoveryIsAdmission":False,
            "discoveredKeyAutomaticallyTrusted":False,
            "profileCompatibilityIsAccreditation":False,
            "externalAdoptionInferred":False,
        },
    }


def anchor_directory(c,organization_id=None):
    params=()
    where=""
    if organization_id:
        federated_trust._organization(c,organization_id)
        where="WHERE a.organization_id=? AND s.status NOT IN ('pending_proof','pending_governance')"
        params=(organization_id,)
    else:
        where="WHERE s.status NOT IN ('pending_proof','pending_governance')"
    rows=list(c.execute(
        f"""SELECT a.id,a.organization_id,a.issuer_id,a.key_id,a.alg,
                   a.public_key_b64,a.rotated_from_anchor_id,a.demo_only,
                   s.status,s.proof_verified_at,s.valid_from,s.valid_until,
                   s.retired_at,s.suspended_at,s.revoked_at
            FROM institutional_federated_anchors a
            JOIN institutional_federated_anchor_state s ON s.anchor_id=a.id
            {where}
            ORDER BY a.organization_id,COALESCE(s.valid_from,a.created_at),a.id""",
        params,
    ))
    return [
        {
            "anchorId":r["id"],
            "organizationId":r["organization_id"],
            "issuerId":r["issuer_id"],
            "keyId":r["key_id"],
            "alg":r["alg"],
            "publicKeyB64":r["public_key_b64"],
            "status":r["status"],
            "proofVerified":r["proof_verified_at"] is not None,
            "validFrom":r["valid_from"],
            "validUntil":r["valid_until"],
            "retiredAt":r["retired_at"],
            "suspendedAt":r["suspended_at"],
            "revokedAt":r["revoked_at"],
            "rotatedFromAnchorId":r["rotated_from_anchor_id"],
            "did":federated_trust.did_id(r["organization_id"]),
            "jwksUrl":_public_base()+"/trust/"+quote(r["organization_id"],safe="")+"/jwks.json",
            "demoOnly":bool(r["demo_only"]),
        }
        for r in rows
    ]


def evaluate_compatibility(c,organization_id,actor="system",now=None):
    now=int(now or time.time())
    profile=ensure_profile(c,actor=actor,now=now)
    anchors=anchor_directory(c,organization_id)
    active=[x for x in anchors if x["status"]=="active"]
    warnings=[]
    failures=[]
    anchor=active[-1] if active else None
    if not anchor:
        status="no_active_anchor"
        failures.append("active_anchor_required")
    else:
        if anchor["alg"]!="Ed25519":
            failures.append("unsupported_signature_algorithm")
        if not anchor["proofVerified"]:
            failures.append("proof_of_possession_missing")
        if anchor["validFrom"] is None or int(anchor["validFrom"])>now:
            failures.append("anchor_not_yet_valid")
        if anchor["validUntil"] is not None and int(anchor["validUntil"])<now:
            failures.append("anchor_expired")
        if not failures:
            historical=[x for x in anchors if x["status"]=="retired"]
            if historical and any(x["rotatedFromAnchorId"] is None for x in historical):
                warnings.append("historical_rotation_lineage_incomplete")
            status="compatible_with_warnings" if warnings else "compatible"
        else:
            status="incompatible"
    core={
        "evaluationVersion":"promomed-federation-profile-evaluation-v1",
        "profileId":profile["id"],
        "profileVersion":profile["profileVersion"],
        "profileSha256":profile["profileSha256"],
        "organizationId":organization_id,
        "anchorId":anchor["anchorId"] if anchor else None,
        "compatibilityStatus":status,
        "warnings":warnings,
        "failures":failures,
        "evaluatedAt":now,
        "authorityBoundary":{
            "changesAnchorAdmission":False,
            "changesQualification":False,
            "createsAccreditation":False,
            "createsEndorsement":False,
        },
    }
    digest=_sha(core)
    evaluation_id="fip-eval:"+digest[:24]
    row=c.execute(
        "SELECT id FROM federation_profile_evaluations WHERE evaluation_sha256=?",
        (digest,),
    ).fetchone()
    if not row:
        org=federated_trust._organization(c,organization_id)
        c.execute(
            """INSERT INTO federation_profile_evaluations(
                 id,profile_id,organization_id,anchor_id,compatibility_status,
                 evaluation_sha256,evaluation_json,evaluated_at,evaluated_by,demo_only
               ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                evaluation_id,profile["id"],organization_id,
                anchor["anchorId"] if anchor else None,status,digest,
                _canonical(core),now,actor,int(bool(org["demo_only"])),
            ),
        )
    return {**core,"id":evaluation_id,"evaluationSha256":digest}


def issue_discovery_bundle(c,organization_id,actor,validity_seconds=DEFAULT_BUNDLE_VALIDITY,now=None):
    now=int(now or time.time())
    validity_seconds=int(validity_seconds)
    if validity_seconds<300 or validity_seconds>7*86400:
        raise ValueError("federation_discovery_bundle_validity_invalid")
    profile=ensure_profile(c,actor=actor,now=now)
    evaluation=evaluate_compatibility(c,organization_id,actor=actor,now=now)
    anchors=anchor_directory(c,organization_id)
    body={
        "bundleVersion":"promomed-federation-discovery-bundle-v1",
        "organizationId":organization_id,
        "profile":{
            "id":profile["id"],
            "version":profile["profileVersion"],
            "sha256":profile["profileSha256"],
        },
        "evaluation":evaluation,
        "anchors":anchors,
        "did":federated_trust.did_document(c,organization_id),
        "jwks":federated_trust.jwks_document(c,organization_id),
        "issuedAt":now,
        "validUntil":now+validity_seconds,
        "truthBoundary":{
            "discoveryIsAdmission":False,
            "compatibilityIsAccreditation":False,
            "compatibilityIsEndorsement":False,
            "medicalEfficacyCertified":False,
        },
    }
    envelope=evidence_checkpoint.sign_portable_statement(
        c,DISCOVERY_STATEMENT_TYPE,body,actor=actor
    )
    bundle_sha=envelope["statementSha256"]
    existing=c.execute(
        "SELECT id,bundle_json FROM federation_discovery_bundles WHERE bundle_sha256=?",
        (bundle_sha,),
    ).fetchone()
    if existing:
        return {
            "id":existing["id"],
            "bundleSha256":bundle_sha,
            "bundle":json.loads(existing["bundle_json"]),
            "idempotentReplay":True,
        }
    bundle_id="discovery:"+bundle_sha[:24]
    org=federated_trust._organization(c,organization_id)
    c.execute(
        """INSERT INTO federation_discovery_bundles(
             id,profile_id,organization_id,bundle_sha256,bundle_json,
             issued_at,valid_until,created_by,demo_only
           ) VALUES(?,?,?,?,?,?,?,?,?)""",
        (
            bundle_id,profile["id"],organization_id,bundle_sha,_canonical(envelope),
            now,now+validity_seconds,actor,int(bool(org["demo_only"])),
        ),
    )
    return {
        "id":bundle_id,
        "bundleSha256":bundle_sha,
        "bundle":envelope,
        "idempotentReplay":False,
    }


def discovery_bundle_document(c,bundle_id):
    row=c.execute(
        """SELECT id,profile_id,organization_id,bundle_sha256,bundle_json,
                  issued_at,valid_until,demo_only
           FROM federation_discovery_bundles WHERE id=?""",
        (bundle_id,),
    ).fetchone()
    if not row:
        raise ValueError("federation_discovery_bundle_not_found")
    return {
        "id":row["id"],
        "profileId":row["profile_id"],
        "organizationId":row["organization_id"],
        "bundleSha256":row["bundle_sha256"],
        "bundle":json.loads(row["bundle_json"]),
        "issuedAt":row["issued_at"],
        "validUntil":row["valid_until"],
        "demoOnly":bool(row["demo_only"]),
    }


def verify_discovery_bundle(bundle,issuer_document,now=None):
    now=int(now or time.time())
    verification=evidence_checkpoint.verify_portable_statement(bundle,issuer_document)
    if verification.get("status")!="VALID_PORTABLE_STATEMENT":
        return {
            "status":verification.get("status") or "INVALID_DISCOVERY_BUNDLE",
            "valid":False,
        }
    if verification.get("statementType")!=DISCOVERY_STATEMENT_TYPE:
        return {"status":"WRONG_DISCOVERY_STATEMENT_TYPE","valid":False}
    body=(bundle.get("payload") or {}).get("body") or {}
    if body.get("bundleVersion")!="promomed-federation-discovery-bundle-v1":
        return {"status":"INVALID_DISCOVERY_BUNDLE_VERSION","valid":False}
    if int(body.get("validUntil") or 0)<now:
        return {"status":"DISCOVERY_BUNDLE_EXPIRED","valid":False}
    profile=body.get("profile") or {}
    if profile.get("version")!=PROFILE_VERSION:
        return {"status":"UNSUPPORTED_INTEROPERABILITY_PROFILE","valid":False}
    if profile.get("sha256")!=_sha(profile_definition()):
        return {"status":"INTEROPERABILITY_PROFILE_HASH_MISMATCH","valid":False}
    return {
        "status":"VALID_FEDERATION_DISCOVERY_BUNDLE",
        "valid":True,
        "organizationId":body.get("organizationId"),
        "compatibilityStatus":((body.get("evaluation") or {}).get("compatibilityStatus")),
        "profileVersion":profile.get("version"),
        "discoveryIsAdmission":False,
        "externalAdoptionInferred":False,
    }
