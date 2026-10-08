import base64
import hashlib
import json
import os
import secrets
import time
from urllib.parse import quote

from app import evidence_checkpoint, syndication_network, trust_bundle


ANCHOR_VERSION="promomed-federated-trust-anchor-v1"
RECEIPT_VERSION="promomed-institution-signed-verification-receipt-v1"
DID_CONTEXT=["https://www.w3.org/ns/did/v1","https://w3id.org/security/suites/jws-2020/v1"]
DEFAULT_TRUST_HOST="sostoyanie-promomed-live.onrender.com"


def _canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)


def _sha(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _b64u(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _ub64u(value):
    value=str(value or "")
    return base64.urlsafe_b64decode(value+"="*((-len(value))%4))


def _public_key(value):
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("cryptography_required_for_federated_trust") from exc
    raw=_ub64u(value)
    if len(raw)!=32:
        raise ValueError("federated_anchor_public_key_invalid")
    return Ed25519PublicKey.from_public_bytes(raw)


def _verify_signature(public_key_b64,payload,signature_b64):
    try:
        from cryptography.exceptions import InvalidSignature
        _public_key(public_key_b64).verify(_ub64u(signature_b64),_canonical(payload).encode("utf-8"))
        return True
    except (InvalidSignature,ValueError,TypeError,KeyError,ModuleNotFoundError):
        return False


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


def _account(c,email):
    row=c.execute(
        "SELECT email,role,status FROM accounts WHERE email=?",
        (str(email or "").lower(),),
    ).fetchone()
    return row


def _governance(c,email):
    row=_account(c,email)
    return bool(row and row["role"]=="governance" and row["status"]=="active")


def _org_admin(c,organization_id,email,now=None):
    return bool(syndication_network._active_member(
        c,organization_id,email,("administrator",),now=now
    ))


def _anchor_row(c,anchor_id):
    return c.execute(
        """SELECT a.id,a.organization_id,a.anchor_version,a.issuer_id,a.key_id,a.alg,
                  a.public_key_b64,a.proof_challenge,a.source_ref,a.metadata_json,
                  a.rotated_from_anchor_id,a.created_at,a.created_by,a.demo_only,
                  s.status,s.proof_verified_at,s.proof_signature_b64,s.valid_from,
                  s.valid_until,s.activated_at,s.activated_by,s.retired_at,
                  s.suspended_at,s.suspended_by,s.suspension_reason,s.revoked_at,
                  s.revoked_by,s.revocation_reason,s.updated_at
           FROM institutional_federated_anchors a
           JOIN institutional_federated_anchor_state s ON s.anchor_id=a.id
           WHERE a.id=?""",
        (anchor_id,),
    ).fetchone()


def _safe_anchor(row,include_internal=False):
    if not row:
        return None
    data={
        "id":row["id"],
        "organizationId":row["organization_id"],
        "anchorVersion":row["anchor_version"],
        "issuerId":row["issuer_id"],
        "keyId":row["key_id"],
        "alg":row["alg"],
        "publicKeyB64":row["public_key_b64"],
        "status":row["status"],
        "validFrom":row["valid_from"],
        "validUntil":row["valid_until"],
        "rotatedFromAnchorId":row["rotated_from_anchor_id"],
        "proofVerifiedAt":row["proof_verified_at"],
        "activatedAt":row["activated_at"],
        "retiredAt":row["retired_at"],
        "suspendedAt":row["suspended_at"],
        "suspensionReason":row["suspension_reason"],
        "revokedAt":row["revoked_at"],
        "revocationReason":row["revocation_reason"],
        "metadata":json.loads(row["metadata_json"] or "{}"),
        "demoOnly":bool(row["demo_only"]),
        "privateKeyStored":False,
    }
    if include_internal and row["status"] in ("pending_proof","pending_governance"):
        data["proofChallenge"]=row["proof_challenge"]
        data["sourceRef"]=row["source_ref"]
    return data


def _event(c,anchor_id,event_type,actor,payload,demo_only=False,now=None):
    now=int(now or time.time())
    core={
        "anchorId":anchor_id,
        "eventType":event_type,
        "actor":actor,
        "payload":payload,
        "createdAt":now,
    }
    digest=_sha(core)
    event_id="anchor-event:"+digest[:24]
    c.execute(
        """INSERT INTO institutional_federated_anchor_events(
             id,anchor_id,event_type,actor,payload_json,event_sha256,created_at,demo_only
           ) VALUES(?,?,?,?,?,?,?,?)
           ON CONFLICT(event_sha256) DO NOTHING""",
        (event_id,anchor_id,event_type,actor,_canonical(core),digest,now,int(bool(demo_only))),
    )
    return event_id


def proof_payload(anchor):
    return {
        "proofVersion":"promomed-federated-anchor-proof-v1",
        "anchorId":anchor["id"],
        "organizationId":anchor["organizationId"],
        "issuerId":anchor["issuerId"],
        "keyId":anchor["keyId"],
        "alg":"Ed25519",
        "challenge":anchor["proofChallenge"],
    }


def propose_anchor(
    c,organization_id,issuer_id,key_id,public_key_b64,actor,
    source_ref="",metadata=None,rotated_from_anchor_id=None,demo_only=False,now=None,
):
    now=int(now or time.time())
    org=_organization(c,organization_id)
    if not _governance(c,actor) and not _org_admin(c,organization_id,actor,now=now):
        raise ValueError("federated_anchor_proposer_not_authorized")
    if int(org["demo_only"])!=int(bool(demo_only)):
        raise ValueError("federated_anchor_demo_boundary_mismatch")
    issuer_id=str(issuer_id or "").strip()[:240]
    key_id=str(key_id or "").strip()[:160]
    if not issuer_id or not key_id:
        raise ValueError("federated_anchor_identity_required")
    public_key_b64=str(public_key_b64 or "").strip()
    _public_key(public_key_b64)
    metadata=metadata if isinstance(metadata,dict) else {}
    rotated_from_anchor_id=str(rotated_from_anchor_id or "").strip() or None

    current=c.execute(
        """SELECT a.id,s.status FROM institutional_federated_anchors a
           JOIN institutional_federated_anchor_state s ON s.anchor_id=a.id
           WHERE a.organization_id=? AND s.status IN ('active','suspended')
           ORDER BY COALESCE(s.valid_from,a.created_at) DESC,a.id DESC LIMIT 1""",
        (organization_id,),
    ).fetchone()
    if current and not rotated_from_anchor_id:
        raise ValueError("federated_anchor_rotation_link_required")
    if rotated_from_anchor_id:
        prior=_anchor_row(c,rotated_from_anchor_id)
        if not prior or prior["organization_id"]!=organization_id:
            raise ValueError("federated_anchor_rotation_source_invalid")
        if current and current["id"]!=rotated_from_anchor_id:
            raise ValueError("federated_anchor_rotation_source_not_current")

    existing=c.execute(
        """SELECT id FROM institutional_federated_anchors
           WHERE organization_id=? AND issuer_id=? AND key_id=?""",
        (organization_id,issuer_id,key_id),
    ).fetchone()
    if existing:
        row=_anchor_row(c,existing["id"])
        if row["public_key_b64"]!=public_key_b64:
            raise ValueError("federated_anchor_key_id_collision")
        return {
            "anchor":_safe_anchor(row,include_internal=True),
            "proof":proof_payload(_safe_anchor(row,include_internal=True)),
            "idempotentReplay":True,
        }

    identity={
        "organizationId":organization_id,
        "issuerId":issuer_id,
        "keyId":key_id,
        "publicKeyB64":public_key_b64,
    }
    anchor_id="anchor:"+_sha(identity)[:24]
    challenge=secrets.token_urlsafe(32)
    c.execute(
        """INSERT INTO institutional_federated_anchors(
             id,organization_id,anchor_version,issuer_id,key_id,alg,public_key_b64,
             proof_challenge,source_ref,metadata_json,rotated_from_anchor_id,
             created_at,created_by,demo_only
           ) VALUES(?,?,?,?,?,'Ed25519',?,?,?,?,?,?,?,?)""",
        (
            anchor_id,organization_id,ANCHOR_VERSION,issuer_id,key_id,public_key_b64,
            challenge,str(source_ref or "")[:500],_canonical(metadata),
            rotated_from_anchor_id,now,actor,int(bool(demo_only)),
        ),
    )
    c.execute(
        """INSERT INTO institutional_federated_anchor_state(
             anchor_id,status,updated_at
           ) VALUES(?,'pending_proof',?)""",
        (anchor_id,now),
    )
    _event(
        c,anchor_id,"proposed",actor,
        {"issuerId":issuer_id,"keyId":key_id,"rotatedFromAnchorId":rotated_from_anchor_id},
        demo_only=bool(demo_only),now=now,
    )
    safe=_safe_anchor(_anchor_row(c,anchor_id),include_internal=True)
    return {"anchor":safe,"proof":proof_payload(safe),"idempotentReplay":False}


def verify_anchor_proof(c,anchor_id,signature_b64,actor,now=None):
    now=int(now or time.time())
    row=_anchor_row(c,anchor_id)
    if not row:
        raise ValueError("federated_anchor_not_found")
    if not _governance(c,actor) and not _org_admin(c,row["organization_id"],actor,now=now):
        raise ValueError("federated_anchor_proof_actor_not_authorized")
    if row["status"]=="pending_governance":
        return _safe_anchor(row)
    if row["status"]!="pending_proof":
        raise ValueError("federated_anchor_proof_not_allowed")
    safe=_safe_anchor(row,include_internal=True)
    payload=proof_payload(safe)
    if not _verify_signature(row["public_key_b64"],payload,signature_b64):
        raise ValueError("federated_anchor_proof_invalid")
    c.execute(
        """UPDATE institutional_federated_anchor_state
           SET status='pending_governance',proof_verified_at=?,proof_signature_b64=?,updated_at=?
           WHERE anchor_id=?""",
        (now,str(signature_b64),now,anchor_id),
    )
    _event(
        c,anchor_id,"proof_verified",actor,
        {"proofPayloadSha256":_sha(payload)},
        demo_only=bool(row["demo_only"]),now=now,
    )
    return _safe_anchor(_anchor_row(c,anchor_id))


def activate_anchor(c,anchor_id,actor,validity_seconds=None,now=None):
    now=int(now or time.time())
    if not _governance(c,actor):
        raise ValueError("federated_anchor_governance_required")
    row=_anchor_row(c,anchor_id)
    if not row:
        raise ValueError("federated_anchor_not_found")
    if row["status"]=="active":
        return _safe_anchor(row)
    if row["status"]!="pending_governance":
        raise ValueError("federated_anchor_activation_not_allowed")
    valid_until=None
    if validity_seconds is not None:
        validity_seconds=int(validity_seconds)
        if validity_seconds<3600 or validity_seconds>3*365*86400:
            raise ValueError("federated_anchor_validity_invalid")
        valid_until=now+validity_seconds

    predecessors=list(c.execute(
        """SELECT a.id,s.status FROM institutional_federated_anchors a
           JOIN institutional_federated_anchor_state s ON s.anchor_id=a.id
           WHERE a.organization_id=? AND s.status IN ('active','suspended')""",
        (row["organization_id"],),
    ))
    if predecessors:
        if not row["rotated_from_anchor_id"]:
            raise ValueError("federated_anchor_rotation_link_required")
        if row["rotated_from_anchor_id"] not in [x["id"] for x in predecessors]:
            raise ValueError("federated_anchor_rotation_source_not_current")
        for prior in predecessors:
            c.execute(
                """UPDATE institutional_federated_anchor_state
                   SET status='retired',valid_until=COALESCE(valid_until,?),retired_at=?,updated_at=?
                   WHERE anchor_id=? AND status IN ('active','suspended')""",
                (now,now,now,prior["id"]),
            )
            _event(
                c,prior["id"],"retired",actor,{"rotatedToAnchorId":anchor_id},
                demo_only=bool(row["demo_only"]),now=now,
            )

    c.execute(
        """UPDATE institutional_federated_anchor_state
           SET status='active',valid_from=?,valid_until=?,activated_at=?,activated_by=?,updated_at=?
           WHERE anchor_id=?""",
        (now,valid_until,now,actor,now,anchor_id),
    )
    _event(
        c,anchor_id,"activated",actor,
        {"validFrom":now,"validUntil":valid_until},
        demo_only=bool(row["demo_only"]),now=now,
    )
    return _safe_anchor(_anchor_row(c,anchor_id))


def suspend_anchor(c,anchor_id,reason,actor,now=None):
    now=int(now or time.time())
    if not _governance(c,actor):
        raise ValueError("federated_anchor_governance_required")
    row=_anchor_row(c,anchor_id)
    if not row:
        raise ValueError("federated_anchor_not_found")
    if row["status"]=="revoked":
        raise ValueError("federated_anchor_revoked")
    if row["status"]=="suspended":
        return _safe_anchor(row)
    if row["status"]!="active":
        raise ValueError("federated_anchor_suspend_not_allowed")
    reason=str(reason or "").strip()
    if len(reason)<3 or len(reason)>500:
        raise ValueError("federated_anchor_reason_invalid")
    c.execute(
        """UPDATE institutional_federated_anchor_state
           SET status='suspended',suspended_at=?,suspended_by=?,suspension_reason=?,updated_at=?
           WHERE anchor_id=?""",
        (now,actor,reason,now,anchor_id),
    )
    _event(
        c,anchor_id,"suspended",actor,{"reason":reason},
        demo_only=bool(row["demo_only"]),now=now,
    )
    return _safe_anchor(_anchor_row(c,anchor_id))


def revoke_anchor(c,anchor_id,reason,actor,now=None):
    now=int(now or time.time())
    if not _governance(c,actor):
        raise ValueError("federated_anchor_governance_required")
    row=_anchor_row(c,anchor_id)
    if not row:
        raise ValueError("federated_anchor_not_found")
    if row["status"]=="revoked":
        return _safe_anchor(row)
    reason=str(reason or "").strip()
    if len(reason)<3 or len(reason)>500:
        raise ValueError("federated_anchor_reason_invalid")
    c.execute(
        """UPDATE institutional_federated_anchor_state
           SET status='revoked',valid_until=COALESCE(valid_until,?),revoked_at=?,
               revoked_by=?,revocation_reason=?,updated_at=?
           WHERE anchor_id=?""",
        (now,now,actor,reason,now,anchor_id),
    )
    _event(
        c,anchor_id,"revoked",actor,{"reason":reason},
        demo_only=bool(row["demo_only"]),now=now,
    )
    return _safe_anchor(_anchor_row(c,anchor_id))


def trust_host():
    value=os.environ.get("PROMOMED_TRUST_PUBLIC_HOST",DEFAULT_TRUST_HOST).strip().lower()
    value=value.removeprefix("https://").removeprefix("http://").strip("/")
    if not value or "/" in value:
        raise ValueError("trust_public_host_invalid")
    return value


def did_id(organization_id):
    return "did:web:"+trust_host()+":trust:"+quote(str(organization_id),safe="")


def _active_and_historical_anchors(c,organization_id):
    _organization(c,organization_id)
    return list(c.execute(
        """SELECT a.id,a.organization_id,a.anchor_version,a.issuer_id,a.key_id,a.alg,
                  a.public_key_b64,a.rotated_from_anchor_id,a.metadata_json,a.demo_only,
                  s.status,s.valid_from,s.valid_until,s.proof_verified_at,s.activated_at,
                  s.retired_at,s.suspended_at,s.suspension_reason,s.revoked_at,s.revocation_reason
           FROM institutional_federated_anchors a
           JOIN institutional_federated_anchor_state s ON s.anchor_id=a.id
           WHERE a.organization_id=? AND s.status NOT IN ('pending_proof','pending_governance')
           ORDER BY COALESCE(s.valid_from,a.created_at),a.id""",
        (organization_id,),
    ))


def jwks_document(c,organization_id):
    org=_organization(c,organization_id)
    did=did_id(organization_id)
    keys=[]
    for row in _active_and_historical_anchors(c,organization_id):
        keys.append({
            "kty":"OKP",
            "crv":"Ed25519",
            "x":row["public_key_b64"],
            "kid":did+"#"+quote(row["key_id"],safe=""),
            "use":"sig",
            "alg":"EdDSA",
            "promomedAnchorId":row["id"],
            "promomedStatus":row["status"],
            "validFrom":row["valid_from"],
            "validUntil":row["valid_until"],
            "revokedAt":row["revoked_at"],
            "rotatedFromAnchorId":row["rotated_from_anchor_id"],
        })
    return {
        "schemaVersion":"promomed-federated-jwks-v1",
        "organizationId":organization_id,
        "organizationName":org["name"],
        "keys":keys,
        "truthBoundary":{
            "publicKeyPublicationOnly":True,
            "professionalAccreditation":False,
            "commercialEndorsement":False,
            "medicalEfficacyCertified":False,
        },
    }


def did_document(c,organization_id):
    org=_organization(c,organization_id)
    did=did_id(organization_id)
    methods=[]
    assertions=[]
    for row in _active_and_historical_anchors(c,organization_id):
        method_id=did+"#"+quote(row["key_id"],safe="")
        methods.append({
            "id":method_id,
            "type":"JsonWebKey2020",
            "controller":did,
            "publicKeyJwk":{
                "kty":"OKP",
                "crv":"Ed25519",
                "x":row["public_key_b64"],
                "alg":"EdDSA",
                "kid":method_id,
            },
            "promomedAnchorId":row["id"],
            "promomedStatus":row["status"],
        })
        if row["status"]=="active":
            assertions.append(method_id)
    return {
        "@context":DID_CONTEXT,
        "id":did,
        "verificationMethod":methods,
        "assertionMethod":assertions,
        "service":[{
            "id":did+"#jwks",
            "type":"JsonWebKeySet",
            "serviceEndpoint":"https://"+trust_host()+"/trust/"+quote(organization_id,safe="")+"/jwks.json",
        }],
        "promomed":{
            "organizationId":organization_id,
            "organizationName":org["name"],
            "hostingAuthority":"Promomed",
            "identityBindingMeaning":"governance_admitted_public_key_binding",
            "externalDomainControlInferred":False,
            "professionalAccreditation":False,
        },
    }


def signed_anchor_status(c,organization_id,actor,validity_seconds=86400,now=None):
    now=int(now or time.time())
    validity_seconds=int(validity_seconds)
    if validity_seconds<300 or validity_seconds>7*86400:
        raise ValueError("federated_anchor_status_validity_invalid")
    org=_organization(c,organization_id)
    anchors=[]
    for row in _active_and_historical_anchors(c,organization_id):
        anchors.append({
            "anchorId":row["id"],
            "issuerId":row["issuer_id"],
            "keyId":row["key_id"],
            "alg":row["alg"],
            "publicKeyB64":row["public_key_b64"],
            "status":row["status"],
            "validFrom":row["valid_from"],
            "validUntil":row["valid_until"],
            "rotatedFromAnchorId":row["rotated_from_anchor_id"],
            "retiredAt":row["retired_at"],
            "suspendedAt":row["suspended_at"],
            "suspensionReason":row["suspension_reason"],
            "revokedAt":row["revoked_at"],
            "revocationReason":row["revocation_reason"],
        })
    body={
        "statusVersion":"promomed-federated-anchor-status-v1",
        "organizationId":organization_id,
        "organizationName":org["name"],
        "did":did_id(organization_id),
        "generatedAt":now,
        "validUntil":now+validity_seconds,
        "anchors":anchors,
        "truthBoundary":{
            "governanceAdmittedKeyBindingOnly":True,
            "externalDomainControlInferred":False,
            "professionalAccreditation":False,
            "commercialEndorsement":False,
            "medicalEfficacyCertified":False,
        },
    }
    return evidence_checkpoint.sign_portable_statement(
        c,"promomed-federated-anchor-status-v1",body,actor=actor
    )


def _anchor_for_receipt(c,anchor_id,verified_at):
    row=_anchor_row(c,anchor_id)
    if not row:
        raise ValueError("federated_anchor_not_found")
    if row["status"] in ("pending_proof","pending_governance","suspended","revoked"):
        raise ValueError("federated_anchor_not_usable_for_receipt")
    valid_from=row["valid_from"]
    valid_until=row["valid_until"]
    if valid_from is None or int(verified_at)<int(valid_from):
        raise ValueError("federated_anchor_not_valid_at_receipt_time")
    if valid_until is not None and int(verified_at)>int(valid_until):
        raise ValueError("federated_anchor_not_valid_at_receipt_time")
    return row


def verification_receipt_body(
    bundle_document,verifier_organization_id,anchor_id,issuer_id,key_id,
    verification_result,verified_at,verification_material=None,
):
    verification_material=verification_material if isinstance(verification_material,dict) else {}
    bundle=bundle_document["bundle"]
    material_hashes={
        "currentStatusStatementSha256":_sha(verification_material.get("current_status_statement"))
            if verification_material.get("current_status_statement") else None,
        "currentIssuerDocumentSha256":_sha(verification_material.get("current_issuer_document"))
            if verification_material.get("current_issuer_document") else None,
    }
    return {
        "receiptVersion":RECEIPT_VERSION,
        "bundleId":bundle_document["id"],
        "bundleSha256":bundle_document["bundleSha256"],
        "snapshotSha256":bundle["snapshot"]["snapshotSha256"],
        "verifierOrganizationId":verifier_organization_id,
        "anchorId":anchor_id,
        "issuerId":issuer_id,
        "keyId":key_id,
        "verifiedAt":int(verified_at),
        "verificationStatus":verification_result.get("status"),
        "verificationResultSha256":_sha(verification_result),
        "verificationMaterial":verification_material,
        "verificationMaterialHashes":material_hashes,
        "authorityBoundary":{
            "changesPartnerQualification":False,
            "changesCanonicalEvidence":False,
            "changesPromomedIssuerState":False,
            "externalEndorsementInferred":False,
            "professionalAccreditation":False,
        },
    }


def submit_signed_verification_receipt(
    c,bundle_id,verifier_organization_id,anchor_id,receipt_body,signature_b64,actor,now=None,
):
    now=int(now or time.time())
    bundle_doc=trust_bundle.bundle_document(c,bundle_id)
    verifier=_organization(c,verifier_organization_id)
    if not _governance(c,actor) and not syndication_network._active_member(
        c,verifier_organization_id,actor,("operator","administrator"),now=now
    ):
        raise ValueError("institution_signed_receipt_submitter_not_authorized")
    if not isinstance(receipt_body,dict):
        raise ValueError("institution_signed_receipt_body_invalid")
    if receipt_body.get("receiptVersion")!=RECEIPT_VERSION:
        raise ValueError("institution_signed_receipt_version_invalid")
    verified_at=int(receipt_body.get("verifiedAt") or 0)
    if verified_at<=0 or verified_at>now+300:
        raise ValueError("institution_signed_receipt_time_invalid")
    if receipt_body.get("bundleId")!=bundle_id:
        raise ValueError("institution_signed_receipt_bundle_mismatch")
    if receipt_body.get("bundleSha256")!=bundle_doc["bundleSha256"]:
        raise ValueError("institution_signed_receipt_bundle_hash_mismatch")
    if receipt_body.get("snapshotSha256")!=bundle_doc["bundle"]["snapshot"]["snapshotSha256"]:
        raise ValueError("institution_signed_receipt_snapshot_hash_mismatch")
    if receipt_body.get("verifierOrganizationId")!=verifier_organization_id:
        raise ValueError("institution_signed_receipt_verifier_mismatch")
    if receipt_body.get("anchorId")!=anchor_id:
        raise ValueError("institution_signed_receipt_anchor_mismatch")

    anchor=_anchor_for_receipt(c,anchor_id,verified_at)
    if anchor["organization_id"]!=verifier_organization_id:
        raise ValueError("institution_signed_receipt_anchor_organization_mismatch")
    if receipt_body.get("issuerId")!=anchor["issuer_id"] or receipt_body.get("keyId")!=anchor["key_id"]:
        raise ValueError("institution_signed_receipt_key_identity_mismatch")
    if not _verify_signature(anchor["public_key_b64"],receipt_body,signature_b64):
        raise ValueError("institution_signed_receipt_signature_invalid")

    material=receipt_body.get("verificationMaterial") or {}
    if not isinstance(material,dict):
        raise ValueError("institution_signed_receipt_material_invalid")
    expected_status_hash=_sha(material.get("current_status_statement")) if material.get("current_status_statement") else None
    expected_issuer_hash=_sha(material.get("current_issuer_document")) if material.get("current_issuer_document") else None
    hashes=receipt_body.get("verificationMaterialHashes") or {}
    if hashes.get("currentStatusStatementSha256")!=expected_status_hash:
        raise ValueError("institution_signed_receipt_status_material_hash_mismatch")
    if hashes.get("currentIssuerDocumentSha256")!=expected_issuer_hash:
        raise ValueError("institution_signed_receipt_issuer_material_hash_mismatch")

    result=trust_bundle.verify_bundle_portable(
        bundle_doc["bundle"],
        current_status_statement=material.get("current_status_statement"),
        current_issuer_document=material.get("current_issuer_document"),
        now=verified_at,
    )
    if receipt_body.get("verificationStatus")!=result.get("status"):
        raise ValueError("institution_signed_receipt_result_mismatch")
    if receipt_body.get("verificationResultSha256")!=_sha(result):
        raise ValueError("institution_signed_receipt_result_digest_mismatch")

    receipt_sha=_sha({"body":receipt_body,"signature":signature_b64})
    existing=c.execute(
        """SELECT id,verification_status,admitted_at
           FROM institutional_signed_verification_receipts
           WHERE receipt_sha256=?""",
        (receipt_sha,),
    ).fetchone()
    if existing:
        return {
            "id":existing["id"],
            "verificationStatus":existing["verification_status"],
            "admittedAt":existing["admitted_at"],
            "receiptSha256":receipt_sha,
            "idempotentReplay":True,
        }

    receipt_id="institution-receipt:"+receipt_sha[:24]
    c.execute(
        """INSERT INTO institutional_signed_verification_receipts(
             id,receipt_version,bundle_id,verifier_organization_id,anchor_id,
             issuer_id,key_id,verification_status,receipt_body_json,receipt_sha256,
             signature_b64,verified_at,admitted_at,submitted_by,demo_only
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            receipt_id,RECEIPT_VERSION,bundle_id,verifier_organization_id,anchor_id,
            anchor["issuer_id"],anchor["key_id"],result["status"],_canonical(receipt_body),
            receipt_sha,str(signature_b64),verified_at,now,actor,
            int(bool(bundle_doc["demoOnly"] or verifier["demo_only"])),
        ),
    )
    return {
        "id":receipt_id,
        "verificationStatus":result["status"],
        "verifiedAt":verified_at,
        "admittedAt":now,
        "receiptSha256":receipt_sha,
        "idempotentReplay":False,
        "authorityBoundary":receipt_body.get("authorityBoundary"),
    }


def signed_receipt_document(c,receipt_id):
    row=c.execute(
        """SELECT id,receipt_version,bundle_id,verifier_organization_id,anchor_id,
                  issuer_id,key_id,verification_status,receipt_body_json,receipt_sha256,
                  signature_b64,verified_at,admitted_at,demo_only
           FROM institutional_signed_verification_receipts WHERE id=?""",
        (receipt_id,),
    ).fetchone()
    if not row:
        raise ValueError("institution_signed_receipt_not_found")
    return {
        "id":row["id"],
        "receiptVersion":row["receipt_version"],
        "bundleId":row["bundle_id"],
        "verifierOrganizationId":row["verifier_organization_id"],
        "anchorId":row["anchor_id"],
        "issuerId":row["issuer_id"],
        "keyId":row["key_id"],
        "verificationStatus":row["verification_status"],
        "body":json.loads(row["receipt_body_json"]),
        "receiptSha256":row["receipt_sha256"],
        "signature":row["signature_b64"],
        "verifiedAt":row["verified_at"],
        "admittedAt":row["admitted_at"],
        "demoOnly":bool(row["demo_only"]),
    }


def verify_signed_receipt_portable(receipt,bundle,anchor_status_statement,promomed_issuer_document,now=None):
    now=int(now or time.time())
    try:
        if receipt.get("receiptVersion")!=RECEIPT_VERSION:
            return {"status":"INVALID_RECEIPT_VERSION","signatureValid":False}
        body=receipt["body"]
        signature=receipt["signature"]
        expected_receipt_sha=_sha({"body":body,"signature":signature})
        if expected_receipt_sha!=receipt.get("receiptSha256"):
            return {"status":"INVALID_RECEIPT_HASH","signatureValid":False}

        status_verification=evidence_checkpoint.verify_portable_statement(
            anchor_status_statement,promomed_issuer_document
        )
        if status_verification.get("status")!="VALID_PORTABLE_STATEMENT":
            return {
                "status":"INVALID_ANCHOR_STATUS_AUTHORITY",
                "signatureValid":False,
                "anchorStatusVerification":status_verification,
            }
        if status_verification.get("statementType")!="promomed-federated-anchor-status-v1":
            return {"status":"WRONG_ANCHOR_STATUS_STATEMENT","signatureValid":False}
        status_body=(anchor_status_statement.get("payload") or {}).get("body") or {}
        if status_body.get("organizationId")!=body.get("verifierOrganizationId"):
            return {"status":"ANCHOR_STATUS_ORGANIZATION_MISMATCH","signatureValid":False}
        if int(status_body.get("validUntil") or 0)<now:
            return {"status":"ANCHOR_STATUS_EXPIRED","signatureValid":False}
        anchor=next(
            (x for x in (status_body.get("anchors") or []) if x.get("anchorId")==body.get("anchorId")),
            None,
        )
        if not anchor:
            return {"status":"ANCHOR_UNKNOWN","signatureValid":False}
        if anchor.get("issuerId")!=body.get("issuerId") or anchor.get("keyId")!=body.get("keyId"):
            return {"status":"ANCHOR_KEY_IDENTITY_MISMATCH","signatureValid":False}
        if anchor.get("status") in ("revoked","suspended"):
            return {"status":"ANCHOR_NOT_TRUSTED","signatureValid":False,"anchorStatus":anchor.get("status")}
        verified_at=int(body.get("verifiedAt") or 0)
        if anchor.get("validFrom") is None or verified_at<int(anchor["validFrom"]):
            return {"status":"ANCHOR_NOT_VALID_AT_RECEIPT_TIME","signatureValid":False}
        if anchor.get("validUntil") is not None and verified_at>int(anchor["validUntil"]):
            return {"status":"ANCHOR_NOT_VALID_AT_RECEIPT_TIME","signatureValid":False}
        if not _verify_signature(anchor.get("publicKeyB64"),body,signature):
            return {"status":"INVALID_INSTITUTION_SIGNATURE","signatureValid":False}

        if body.get("bundleSha256")!=bundle.get("bundleSha256"):
            return {"status":"RECEIPT_BUNDLE_HASH_MISMATCH","signatureValid":True}
        if body.get("snapshotSha256")!=((bundle.get("snapshot") or {}).get("snapshotSha256")):
            return {"status":"RECEIPT_SNAPSHOT_HASH_MISMATCH","signatureValid":True}
        material=body.get("verificationMaterial") or {}
        result=trust_bundle.verify_bundle_portable(
            bundle,
            current_status_statement=material.get("current_status_statement"),
            current_issuer_document=material.get("current_issuer_document"),
            now=verified_at,
        )
        if result.get("status")!=body.get("verificationStatus") or _sha(result)!=body.get("verificationResultSha256"):
            return {"status":"RECEIPT_RESULT_NOT_REPRODUCIBLE","signatureValid":True}
        return {
            "status":"VALID_INSTITUTION_SIGNED_RECEIPT",
            "signatureValid":True,
            "verificationStatus":result.get("status"),
            "verifierOrganizationId":body.get("verifierOrganizationId"),
            "anchorId":body.get("anchorId"),
            "bundleSha256":body.get("bundleSha256"),
            "currentPromomedStateVerified":result.get("currentPromomedStateVerified",False),
            "externalEndorsementInferred":False,
            "professionalAccreditation":False,
            "medicalEfficacyCertified":False,
        }
    except (KeyError,TypeError,ValueError,ModuleNotFoundError):
        return {"status":"INVALID_INSTITUTION_SIGNED_RECEIPT","signatureValid":False}


def federation_snapshot(c,organization_id=None):
    params=()
    where=""
    if organization_id:
        _organization(c,organization_id)
        where="WHERE a.organization_id=?"
        params=(organization_id,)
    anchors=[
        _safe_anchor(r)
        for r in c.execute(
            f"""SELECT a.id,a.organization_id,a.anchor_version,a.issuer_id,a.key_id,a.alg,
                       a.public_key_b64,a.proof_challenge,a.source_ref,a.metadata_json,
                       a.rotated_from_anchor_id,a.created_at,a.created_by,a.demo_only,
                       s.status,s.proof_verified_at,s.proof_signature_b64,s.valid_from,
                       s.valid_until,s.activated_at,s.activated_by,s.retired_at,
                       s.suspended_at,s.suspended_by,s.suspension_reason,s.revoked_at,
                       s.revoked_by,s.revocation_reason,s.updated_at
                FROM institutional_federated_anchors a
                JOIN institutional_federated_anchor_state s ON s.anchor_id=a.id
                {where}
                ORDER BY a.organization_id,a.created_at,a.id""",
            params,
        )
    ]
    receipt_where=""
    receipt_params=()
    if organization_id:
        receipt_where="WHERE verifier_organization_id=?"
        receipt_params=(organization_id,)
    receipts=[
        {
            "id":r["id"],
            "bundleId":r["bundle_id"],
            "verifierOrganizationId":r["verifier_organization_id"],
            "anchorId":r["anchor_id"],
            "verificationStatus":r["verification_status"],
            "receiptSha256":r["receipt_sha256"],
            "verifiedAt":r["verified_at"],
            "admittedAt":r["admitted_at"],
            "demoOnly":bool(r["demo_only"]),
        }
        for r in c.execute(
            f"""SELECT id,bundle_id,verifier_organization_id,anchor_id,
                       verification_status,receipt_sha256,verified_at,admitted_at,demo_only
                FROM institutional_signed_verification_receipts
                {receipt_where}
                ORDER BY admitted_at DESC,id DESC LIMIT 100""",
            receipt_params,
        )
    ]
    return {
        "version":ANCHOR_VERSION,
        "anchors":anchors,
        "institutionSignedReceipts":receipts,
        "truthBoundary":{
            "proofOfPossessionRequired":True,
            "allPublishedAnchorsProofVerified":all(
                x.get("proofVerifiedAt") is not None
                for x in anchors
            ) if anchors else False,
            "governanceBindingRequired":True,
            "externalPrivateKeyStored":False,
            "externalDomainControlInferred":False,
            "professionalAccreditation":False,
            "medicalEfficacyCertified":False,
        },
    }
