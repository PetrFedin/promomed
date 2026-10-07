import hashlib
import json
import time

from app import change_impact, evidence_checkpoint, evidence_graph, evidence_seal, syndication_network


PROFILE_VERSION="promomed-evidence-governance-interchange-v1"
PACKAGE_VERSION="promomed-reference-evidence-package-v1"
PROFILE_SCHEMA_ID="urn:promomed:schema:evidence-governance-interchange:v1"
PACKAGE_SCHEMA_ID="urn:promomed:schema:reference-evidence-package:v1"
REFERENCE_FIXTURE_SCHEMA_ID="urn:promomed:schema:evidence-interchange-reference-fixture:v1"

ORGANIZATION_TYPES={
    "medical_society",
    "scientific_society",
    "university",
    "education_partner",
    "corporate_learning",
    "media_partner",
    "conference_partner",
    "knowledge_platform",
    "strategic_partner",
}
ROLE_SCOPES={"publisher","consumer","contributor"}


def _canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)


def _sha(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _demo_only(c,artifact_kind,artifact_ref):
    try:
        row=c.execute(
            "SELECT MAX(demo_only) demo_only FROM evidence_claims WHERE artifact_kind=? AND artifact_ref=?",
            (artifact_kind,artifact_ref),
        ).fetchone()
        return int(bool(row and row["demo_only"]))
    except Exception:
        return 0


def register_organization(
    c,*,organization_id,name,organization_type,actor,
    external_ref="",credential_source="",partner_id=None,demo_only=False,
):
    organization_id=str(organization_id or "").strip()[:100]
    name=str(name or "").strip()[:240]
    organization_type=str(organization_type or "").strip()
    if not organization_id or not name:
        raise ValueError("organization_identity_required")
    if organization_type not in ORGANIZATION_TYPES:
        raise ValueError("organization_type_invalid")
    existing=c.execute(
        "SELECT status,demo_only FROM institutional_organizations WHERE id=?",
        (organization_id,),
    ).fetchone()
    if existing:
        if existing["status"]!="active":
            raise ValueError("organization_not_active")
        if int(existing["demo_only"])!=int(bool(demo_only)):
            raise ValueError("organization_demo_boundary_mismatch")
    if partner_id:
        partner=c.execute("SELECT id FROM partners WHERE id=?",(str(partner_id),)).fetchone()
        if not partner:
            raise ValueError("partner_not_found")
    now=int(time.time())
    c.execute(
        """INSERT INTO institutional_organizations(
             id,name,organization_type,status,external_ref,credential_source,partner_id,
             created_at,created_by,demo_only
           ) VALUES(?,?,?,'active',?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             name=excluded.name,
             organization_type=excluded.organization_type,
             external_ref=excluded.external_ref,
             credential_source=excluded.credential_source,
             partner_id=excluded.partner_id""",
        (
            organization_id,name,organization_type,str(external_ref or "")[:400],
            str(credential_source or "")[:400],partner_id,now,actor,int(bool(demo_only)),
        ),
    )
    return organization(c,organization_id)


def organization(c,organization_id):
    row=c.execute(
        """SELECT id,name,organization_type,status,external_ref,credential_source,
                  partner_id,created_at,created_by,demo_only
           FROM institutional_organizations WHERE id=?""",
        (organization_id,),
    ).fetchone()
    if not row:
        raise ValueError("organization_not_found")
    roles=[
        dict(r) for r in c.execute(
            """SELECT id,role_scope,status,effective_at,expires_at,verified_by,
                      verification_ref,demo_only
               FROM institutional_role_bindings
               WHERE organization_id=? ORDER BY role_scope""",
            (organization_id,),
        )
    ]
    return {**dict(row),"roles":roles}


def bind_role(
    c,*,organization_id,role_scope,actor,verification_ref="",
    effective_at=None,expires_at=None,demo_only=False,
):
    org=c.execute(
        "SELECT id,status,demo_only FROM institutional_organizations WHERE id=?",
        (organization_id,),
    ).fetchone()
    if not org or org["status"]!="active":
        raise ValueError("organization_not_active")
    if int(org["demo_only"])!=int(bool(demo_only)):
        raise ValueError("institutional_role_demo_boundary_mismatch")
    if role_scope not in ROLE_SCOPES:
        raise ValueError("institutional_role_invalid")
    now=int(time.time())
    effective_at=int(effective_at or now)
    if expires_at is not None and int(expires_at)<=effective_at:
        raise ValueError("role_expiry_invalid")
    role_id=f"irole:{organization_id}:{role_scope}"
    c.execute(
        """INSERT INTO institutional_role_bindings(
             id,organization_id,role_scope,status,effective_at,expires_at,
             verified_by,verification_ref,demo_only
           ) VALUES(?,?,?,'active',?,?,?,?,?)
           ON CONFLICT(organization_id,role_scope) DO UPDATE SET
             status='active',
             effective_at=excluded.effective_at,
             expires_at=excluded.expires_at,
             verified_by=excluded.verified_by,
             verification_ref=excluded.verification_ref,
             demo_only=excluded.demo_only""",
        (
            role_id,organization_id,role_scope,effective_at,expires_at,
            actor,str(verification_ref or "")[:500],int(bool(demo_only)),
        ),
    )
    return organization(c,organization_id)


def _active_role(c,organization_id,role_scope,now=None):
    now=int(now or time.time())
    row=c.execute(
        """SELECT id FROM institutional_role_bindings
           WHERE organization_id=? AND role_scope=? AND status='active'
             AND effective_at<=?
             AND (expires_at IS NULL OR expires_at>?)
           LIMIT 1""",
        (organization_id,role_scope,now,now),
    ).fetchone()
    return bool(row)


def _review_role(c,reviewer):
    reviewer=str(reviewer or "").strip().lower()
    if not reviewer:
        return "not_recorded"
    try:
        row=c.execute("SELECT role FROM accounts WHERE email=?",(reviewer,)).fetchone()
        if row and row["role"] in ("reviewer","editor","governance"):
            return row["role"]
    except Exception:
        pass
    return "editorial_review_recorded"


def interchange_profile(c,*,artifact_kind,artifact_ref):
    graph=evidence_graph.snapshot(c,artifact_kind=artifact_kind,artifact_ref=artifact_ref)
    seal=evidence_seal.build(c,artifact_kind=artifact_kind,artifact_ref=artifact_ref)

    claims=[]
    sources={}
    disclosures=[]
    history=[]
    for claim in graph.get("claims") or []:
        trust=claim.get("trust") or {}
        citations=[]
        for citation in claim.get("citations") or []:
            source_id=citation.get("source_id")
            source={
                "sourceId":source_id,
                "sourceKind":citation.get("source_kind"),
                "title":citation.get("source_title"),
                "publisher":citation.get("publisher"),
                "sourceRef":citation.get("source_ref"),
                "publishedAt":citation.get("published_at"),
                "status":citation.get("source_status"),
            }
            if source_id:
                sources[source_id]=source
            citations.append({
                "citationId":citation.get("id"),
                "sourceId":source_id,
                "locator":citation.get("locator"),
                "supportType":citation.get("support_type"),
                "status":citation.get("status"),
            })
            disclosure=str(citation.get("disclosure") or "").strip()
            if disclosure:
                disclosures.append({
                    "claimId":claim.get("id"),
                    "sourceId":source_id,
                    "disclosure":disclosure,
                })

        item={
            "claimId":claim.get("id"),
            "version":claim.get("version"),
            "text":claim.get("claim_text"),
            "topic":claim.get("topic"),
            "status":trust.get("status"),
            "review":{
                "reviewed":bool(trust.get("reviewed")),
                "reviewRole":_review_role(c,claim.get("reviewer")),
                "reviewedAt":claim.get("reviewed_at"),
                "reviewerIdentityExported":False,
            },
            "citations":citations,
            "supersedesClaimId":claim.get("supersedes_claim_id"),
            "correctionNote":claim.get("correction_note"),
        }
        if trust.get("superseded") or trust.get("retracted"):
            history.append(item)
        else:
            claims.append(item)

    return {
        "schemaId":PROFILE_SCHEMA_ID,
        "profileVersion":PROFILE_VERSION,
        "artifact":{"kind":artifact_kind,"ref":artifact_ref},
        "sources":[sources[k] for k in sorted(sources)],
        "claims":claims,
        "history":history,
        "disclosures":disclosures,
        "approval":{
            "processState":seal.get("state"),
            "processValid":bool(seal.get("validForProcess")),
            "evidencePackageSha256":seal.get("evidencePackageSha256"),
            "reviewUntil":None,
            "reviewValidityPolicy":"not_configured_in_current_authority",
        },
        "changeState":{
            "publicationHeld":change_impact.is_held(c,artifact_kind,artifact_ref),
            "supersessionHistoryPresent":bool(history),
        },
        "truthBoundary":{
            "processProvenanceOnly":True,
            "medicalEfficacyCertified":False,
            "clinicalCorrectnessCertified":False,
            "reviewerIdentityExported":False,
            "externalQualificationClaimsSourceAttributed":True,
        },
    }


def _latest_checkpoint(c,artifact_kind,artifact_ref):
    row=c.execute(
        """SELECT checkpoint_sha256 FROM evidence_checkpoint_issuance
           WHERE artifact_kind=? AND artifact_ref=?
           ORDER BY issued_at DESC,checkpoint_sha256 DESC LIMIT 1""",
        (artifact_kind,artifact_ref),
    ).fetchone()
    return row["checkpoint_sha256"] if row else None


def create_package(c,*,artifact_kind,artifact_ref,actor,checkpoint_sha256=None):
    profile=interchange_profile(c,artifact_kind=artifact_kind,artifact_ref=artifact_ref)
    if not profile["approval"]["processValid"]:
        raise ValueError("interchange_artifact_not_process_valid")
    if profile["changeState"]["publicationHeld"]:
        raise ValueError("interchange_artifact_publication_held")

    checkpoint_sha256=checkpoint_sha256 or _latest_checkpoint(c,artifact_kind,artifact_ref)
    if not checkpoint_sha256:
        raise ValueError("signed_checkpoint_required")
    envelope=evidence_checkpoint.checkpoint_document(c,checkpoint_sha256)
    verification=evidence_checkpoint.verify(c,envelope)
    if verification.get("status")!="VALID":
        raise ValueError("checkpoint_not_current")

    package_core={
        "schemaId":PACKAGE_SCHEMA_ID,
        "packageVersion":PACKAGE_VERSION,
        "profile":profile,
        "checkpoint":envelope,
        "verificationAtPackaging":{
            "status":verification.get("status"),
            "checkpointSha256":checkpoint_sha256,
            "sealSha256":verification.get("sealSha256"),
            "issuerId":verification.get("issuerId"),
            "keyId":verification.get("keyId"),
        },
        "syndication":{
            "authority":"Promomed",
            "partnerMayRewriteClaims":False,
            "withdrawalPropagationRequired":True,
            "allowedUse":"reviewed scientific-content distribution / education / knowledge systems",
        },
    }
    package_sha=_sha(package_core)
    existing=c.execute(
        "SELECT id,payload_json,state FROM evidence_exchange_packages WHERE package_sha256=?",
        (package_sha,),
    ).fetchone()
    if existing:
        return {
            "id":existing["id"],
            "packageSha256":package_sha,
            "state":existing["state"],
            "payload":json.loads(existing["payload_json"]),
        }

    prior=c.execute(
        """SELECT id,state FROM evidence_exchange_packages
           WHERE artifact_kind=? AND artifact_ref=?
           ORDER BY created_at DESC,id DESC LIMIT 1""",
        (artifact_kind,artifact_ref),
    ).fetchone()
    now=int(time.time())
    package_id="pkg:"+package_sha[:24]
    if prior and prior["state"]=="active":
        c.execute(
            "UPDATE evidence_exchange_packages SET state='superseded' WHERE id=?",
            (prior["id"],),
        )
        c.execute(
            """UPDATE evidence_exchange_deliveries
               SET status='superseded',withdrawn_at=?,withdrawal_reason=?
               WHERE package_id=? AND status IN ('delivered','acknowledged')""",
            (now,f"Superseded by {package_id}",prior["id"]),
        )
        syndication_network.create_delivery_obligations(c,prior["id"],"update",now=now)
    c.execute(
        """INSERT INTO evidence_exchange_packages(
             id,artifact_kind,artifact_ref,profile_version,package_sha256,
             checkpoint_sha256,state,payload_json,created_at,created_by,
             supersedes_package_id,demo_only
           ) VALUES(?,?,?,?,?,?,'active',?,?,?,?,?)""",
        (
            package_id,artifact_kind,artifact_ref,PROFILE_VERSION,package_sha,
            checkpoint_sha256,_canonical(package_core),now,actor,
            prior["id"] if prior else None,_demo_only(c,artifact_kind,artifact_ref),
        ),
    )
    return {
        "id":package_id,
        "packageSha256":package_sha,
        "state":"active",
        "payload":package_core,
        "supersedesPackageId":prior["id"] if prior else None,
    }


def verify_package_portable(document,issuer_document,status_list=None):
    try:
        payload=document["payload"]
        package_sha=str(document.get("packageSha256") or "")
        if payload.get("schemaId")!=PACKAGE_SCHEMA_ID or payload.get("packageVersion")!=PACKAGE_VERSION:
            return {
                "status":"INVALID_PACKAGE_SCHEMA",
                "package_hash_valid":False,
                "checkpoint_signature_valid":False,
                "currentCanonicalStateVerified":False,
            }
        actual_sha=_sha(payload)
        if actual_sha!=package_sha:
            return {
                "status":"INVALID_PACKAGE_HASH",
                "package_hash_valid":False,
                "checkpoint_signature_valid":False,
                "currentCanonicalStateVerified":False,
            }
        profile=payload.get("profile") or {}
        if profile.get("schemaId")!=PROFILE_SCHEMA_ID or profile.get("profileVersion")!=PROFILE_VERSION:
            return {
                "status":"INVALID_PROFILE_SCHEMA",
                "package_hash_valid":True,
                "checkpoint_signature_valid":False,
                "currentCanonicalStateVerified":False,
            }
        checkpoint=payload.get("checkpoint") or {}
        verification=evidence_checkpoint.verify_portable(
            checkpoint,issuer_document,status_list or {}
        )
        if verification.get("status")!="VALID_PORTABLE":
            return {
                "status":"CHECKPOINT_"+str(verification.get("status") or "INVALID"),
                "package_hash_valid":True,
                "checkpoint_signature_valid":bool(verification.get("signature_valid")),
                "checkpoint":verification,
                "currentCanonicalStateVerified":False,
            }
        approval=profile.get("approval") or {}
        checkpoint_payload=checkpoint.get("payload") or {}
        packaging=payload.get("verificationAtPackaging") or {}
        if approval.get("evidencePackageSha256")!=checkpoint_payload.get("sealSha256"):
            return {
                "status":"SEAL_BINDING_MISMATCH",
                "package_hash_valid":True,
                "checkpoint_signature_valid":True,
                "currentCanonicalStateVerified":False,
            }
        if packaging.get("checkpointSha256")!=checkpoint.get("checkpointSha256"):
            return {
                "status":"CHECKPOINT_BINDING_MISMATCH",
                "package_hash_valid":True,
                "checkpoint_signature_valid":True,
                "currentCanonicalStateVerified":False,
            }
        if (
            packaging.get("sealSha256")!=checkpoint_payload.get("sealSha256")
            or packaging.get("issuerId")!=checkpoint_payload.get("issuerId")
            or packaging.get("keyId")!=checkpoint_payload.get("keyId")
        ):
            return {
                "status":"PACKAGING_ATTESTATION_MISMATCH",
                "package_hash_valid":True,
                "checkpoint_signature_valid":True,
                "currentCanonicalStateVerified":False,
            }
        if payload.get("syndication",{}).get("partnerMayRewriteClaims") is not False:
            return {
                "status":"AUTHORITY_BOUNDARY_INVALID",
                "package_hash_valid":True,
                "checkpoint_signature_valid":True,
                "currentCanonicalStateVerified":False,
            }
        return {
            "status":"VALID_PORTABLE_PACKAGE",
            "package_hash_valid":True,
            "checkpoint_signature_valid":True,
            "packageSha256":package_sha,
            "checkpointSha256":checkpoint.get("checkpointSha256"),
            "issuerId":verification.get("issuerId"),
            "keyId":verification.get("keyId"),
            "currentCanonicalStateVerified":False,
            "medicalEfficacyCertified":False,
        }
    except (KeyError,TypeError,ValueError):
        return {
            "status":"INVALID_PACKAGE",
            "package_hash_valid":False,
            "checkpoint_signature_valid":False,
            "currentCanonicalStateVerified":False,
        }


def package_document(c,package_id):
    row=c.execute(
        """SELECT id,artifact_kind,artifact_ref,profile_version,package_sha256,
                  checkpoint_sha256,state,payload_json,created_at,supersedes_package_id,demo_only
           FROM evidence_exchange_packages WHERE id=?""",
        (package_id,),
    ).fetchone()
    if not row:
        raise ValueError("evidence_package_not_found")
    payload=json.loads(row["payload_json"])
    valid_hash=_sha(payload)==row["package_sha256"]
    checkpoint_result=evidence_checkpoint.verify_portable(
        payload.get("checkpoint") or {},
        evidence_checkpoint.issuer_document(
            c,(payload.get("checkpoint") or {}).get("payload",{}).get("issuerId")
        ),
        evidence_checkpoint.status_list(
            c,(payload.get("checkpoint") or {}).get("payload",{}).get("issuerId")
        ),
    )
    return {
        "id":row["id"],
        "artifact":{"kind":row["artifact_kind"],"ref":row["artifact_ref"]},
        "profileVersion":row["profile_version"],
        "packageSha256":row["package_sha256"],
        "checkpointSha256":row["checkpoint_sha256"],
        "state":row["state"],
        "createdAt":row["created_at"],
        "supersedesPackageId":row["supersedes_package_id"],
        "payload":payload,
        "integrity":{
            "packageHashValid":valid_hash,
            "checkpointVerification":checkpoint_result,
        },
    }


def deliver_package(c,*,package_id,organization_id,actor,delivery_role="consumer"):
    package=c.execute(
        "SELECT id,package_sha256,state,demo_only FROM evidence_exchange_packages WHERE id=?",
        (package_id,),
    ).fetchone()
    if not package:
        raise ValueError("evidence_package_not_found")
    if package["state"]!="active":
        raise ValueError("evidence_package_not_active")
    if delivery_role not in ("consumer","publisher"):
        raise ValueError("delivery_role_invalid")
    org=c.execute(
        "SELECT status,demo_only FROM institutional_organizations WHERE id=?",
        (organization_id,),
    ).fetchone()
    if not org or org["status"]!="active":
        raise ValueError("organization_not_active")
    if int(org["demo_only"])!=int(package["demo_only"]):
        raise ValueError("package_organization_demo_boundary_mismatch")
    if not _active_role(c,organization_id,delivery_role):
        raise ValueError("institutional_role_not_active")
    existing=c.execute(
        """SELECT id,status,delivered_at,receipt_sha256 FROM evidence_exchange_deliveries
           WHERE package_id=? AND organization_id=? AND delivery_role=?""",
        (package_id,organization_id,delivery_role),
    ).fetchone()
    if existing:
        return {
            "id":existing["id"],
            "status":existing["status"],
            "receiptSha256":existing["receipt_sha256"],
            "receipt":{
                "packageId":package_id,
                "packageSha256":package["package_sha256"],
                "organizationId":organization_id,
                "deliveryRole":delivery_role,
                "deliveredAt":existing["delivered_at"],
            },
            "idempotentReplay":True,
        }

    now=int(time.time())
    receipt_core={
        "packageId":package_id,
        "packageSha256":package["package_sha256"],
        "organizationId":organization_id,
        "deliveryRole":delivery_role,
        "deliveredAt":now,
    }
    receipt_sha=_sha(receipt_core)
    delivery_id="delivery:"+receipt_sha[:24]
    c.execute(
        """INSERT INTO evidence_exchange_deliveries(
             id,package_id,organization_id,delivery_role,status,delivered_at,
             receipt_sha256,created_by,demo_only
           ) VALUES(?,?,?,?, 'delivered',?,?,?,?)
           ON CONFLICT(id) DO NOTHING""",
        (
            delivery_id,package_id,organization_id,delivery_role,now,
            receipt_sha,actor,int(package["demo_only"]),
        ),
    )
    return {
        "id":delivery_id,
        "status":"delivered",
        "receiptSha256":receipt_sha,
        "receipt":receipt_core,
    }


def acknowledge_delivery(c,delivery_id,organization_id):
    row=c.execute(
        """SELECT id,organization_id,status FROM evidence_exchange_deliveries
           WHERE id=?""",
        (delivery_id,),
    ).fetchone()
    if not row:
        raise ValueError("delivery_not_found")
    if row["organization_id"]!=organization_id:
        raise ValueError("delivery_organization_mismatch")
    if row["status"]=="acknowledged":
        return {"id":delivery_id,"status":"acknowledged"}
    if row["status"]!="delivered":
        raise ValueError("delivery_not_acknowledgeable")
    now=int(time.time())
    c.execute(
        "UPDATE evidence_exchange_deliveries SET status='acknowledged',acknowledged_at=? WHERE id=?",
        (now,delivery_id),
    )
    return {"id":delivery_id,"status":"acknowledged","acknowledgedAt":now}


def withdraw_artifact_packages(c,artifact_kind,artifact_ref,reason,actor):
    now=int(time.time())
    package_rows=list(c.execute(
        """SELECT id FROM evidence_exchange_packages
           WHERE artifact_kind=? AND artifact_ref=? AND state='active'""",
        (artifact_kind,artifact_ref),
    ))
    for row in package_rows:
        c.execute("UPDATE evidence_exchange_packages SET state='withdrawn' WHERE id=?",(row["id"],))
        c.execute(
            """UPDATE evidence_exchange_deliveries
               SET status='withdrawn',withdrawn_at=?,withdrawal_reason=?
               WHERE package_id=? AND status IN ('delivered','acknowledged')""",
            (now,str(reason or "Canonical authority withdrawal")[:500],row["id"]),
        )
        syndication_network.create_delivery_obligations(c,row["id"],"withdrawal",now=now)
    return {
        "artifact":{"kind":artifact_kind,"ref":artifact_ref},
        "withdrawnPackages":[r["id"] for r in package_rows],
        "withdrawnAt":now,
        "actor":actor,
    }


def reference_package():
    core={
        "schemaId":REFERENCE_FIXTURE_SCHEMA_ID,
        "fixtureVersion":"promomed-evidence-interchange-reference-fixture-v1",
        "packageVersion":PACKAGE_VERSION,
        "profileSchemaId":PROFILE_SCHEMA_ID,
        "profileVersion":PROFILE_VERSION,
        "exampleType":"synthetic_non_clinical",
        "artifact":{"kind":"reference","ref":"SYNTHETIC-KNOWLEDGE-001"},
        "source":{
            "sourceId":"SRC-SYNTH-001",
            "sourceKind":"synthetic_reference",
            "title":"Synthetic source for interoperability testing",
            "publisher":"Promomed Reference Fixture",
            "sourceRef":"urn:promomed:synthetic:source:001",
            "status":"active",
        },
        "claim":{
            "claimId":"CLAIM-SYNTH-001",
            "version":1,
            "text":"Synthetic interoperability claims must remain distinguishable from medical claims.",
            "topic":"Interoperability",
            "status":"VERIFIED_PROCESS_FIXTURE",
        },
        "review":{
            "reviewRole":"synthetic_governance_fixture",
            "reviewerIdentityExported":False,
            "decision":"approved_fixture",
        },
        "disclosure":{
            "commercialContext":"none",
            "synthetic":True,
            "medicalContent":False,
        },
        "approval":{
            "processState":"REFERENCE_FIXTURE",
            "medicalEfficacyCertified":False,
            "clinicalCorrectnessCertified":False,
        },
        "seal":{
            "state":"REFERENCE_FIXTURE",
            "evidencePackageSha256":"synthetic-not-a-production-seal",
        },
        "checkpoint":{
            "state":"REFERENCE_FIXTURE",
            "signatureStatus":"not_a_production_signature",
        },
        "syndication":{
            "publisherRole":"institutional publisher",
            "consumerRole":"institutional consumer",
            "partnerMayRewriteClaims":False,
            "withdrawalPropagationRequired":True,
        },
        "lifecycle":[
            {"step":1,"event":"source_admitted","state":"active"},
            {"step":2,"event":"claim_reviewed","state":"approved_fixture"},
            {"step":3,"event":"package_published","state":"active"},
            {"step":4,"event":"package_syndicated","state":"delivered"},
            {"step":5,"event":"source_corrected","state":"review_required"},
            {"step":6,"event":"prior_package_withdrawn","state":"withdrawn"},
            {"step":7,"event":"corrected_package_published","state":"superseding"},
        ],
        "truthBoundary":{
            "synthetic":True,
            "medicalAdvice":False,
            "medicalEfficacyCertified":False,
            "productionCredential":False,
        },
    }
    return {**core,"referencePackageSha256":_sha(core)}


def institutional_snapshot(c,organization_id=None):
    if organization_id:
        organizations=[organization(c,organization_id)]
    else:
        organizations=[
            organization(c,r["id"])
            for r in c.execute("SELECT id FROM institutional_organizations ORDER BY name")
        ]
    packages=[
        dict(r) for r in c.execute(
            """SELECT id,artifact_kind,artifact_ref,profile_version,package_sha256,
                      checkpoint_sha256,state,created_at,supersedes_package_id,demo_only
               FROM evidence_exchange_packages ORDER BY created_at DESC,id DESC LIMIT 100"""
        )
    ]
    deliveries=[
        dict(r) for r in c.execute(
            """SELECT id,package_id,organization_id,delivery_role,status,delivered_at,
                      acknowledged_at,withdrawn_at,withdrawal_reason,receipt_sha256,demo_only
               FROM evidence_exchange_deliveries ORDER BY delivered_at DESC,id DESC LIMIT 100"""
        )
    ]
    return {
        "version":"institutional-evidence-network-v1",
        "organizations":organizations,
        "packages":packages,
        "deliveries":deliveries,
        "rules":[
            "Institutional publisher/consumer roles do not grant claim-editing authority.",
            "External professional qualifications remain source-attributed.",
            "Only active, process-valid, non-held artifacts may create active interchange packages.",
            "Withdrawal/supersession must propagate to prior deliveries.",
        ],
        "truthBoundary":{
            "medicalEfficacyCertified":False,
            "clinicalAdviceIncluded":False,
            "externalOrganizationAccreditationInferred":False,
            "partnerMaySelfApproveEvidence":False,
        },
    }
