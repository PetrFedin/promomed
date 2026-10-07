import hashlib
import json
import time

from app import evidence_checkpoint, reviewer_authority


QUALIFICATION_VERSION="promomed-syndication-qualification-v1"
CONTRIBUTION_VERSION="promomed-external-contribution-v1"
CONTRIBUTION_RECEIPT_TYPE="promomed-external-contribution-admission-v1"

REQUIRED_CONFORMANCE_SCOPES=(
    "evidence_api_integration",
    "withdrawal_propagation",
    "disclosure_workflow",
)
OPTIONAL_CONFORMANCE_SCOPES=(
    "credential_verification",
    "education_completion_sync",
)
ALL_CONFORMANCE_SCOPES=REQUIRED_CONFORMANCE_SCOPES+OPTIONAL_CONFORMANCE_SCOPES

CONTRIBUTION_TYPES={
    "source_recommendation",
    "review_input",
    "disclosure_record",
    "programme_material",
    "correction_notice",
    "institutional_metadata",
}
REVIEW_ROLES=("editorial","scientific")
SCIENTIFIC_SCOPE="external_contribution.general"


def _canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)


def _sha(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


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


def _active_role(c,organization_id,role_scope,now=None):
    now=int(now or time.time())
    return c.execute(
        """SELECT id FROM institutional_role_bindings
           WHERE organization_id=? AND role_scope=? AND status='active'
             AND effective_at<=? AND (expires_at IS NULL OR expires_at>?)
           LIMIT 1""",
        (organization_id,role_scope,now,now),
    ).fetchone()


def bind_member(
    c,organization_id,account_email,member_role,verified_by,
    verification_ref="",expires_at=None,demo_only=False,
):
    org=_organization(c,organization_id)
    account_email=str(account_email or "").lower().strip()
    account=c.execute(
        "SELECT email,status FROM accounts WHERE email=?",(account_email,)
    ).fetchone()
    if not account or account["status"]!="active":
        raise ValueError("institutional_member_account_required")
    if member_role not in ("contributor","operator","administrator"):
        raise ValueError("institutional_member_role_invalid")
    if int(org["demo_only"])!=int(bool(demo_only)):
        raise ValueError("institutional_member_demo_boundary_mismatch")
    now=int(time.time())
    if expires_at is not None and int(expires_at)<=now:
        raise ValueError("institutional_member_expiry_invalid")
    member_id="imember:"+hashlib.sha256(
        f"{organization_id}|{account_email}|{member_role}".encode("utf-8")
    ).hexdigest()[:24]
    c.execute(
        """INSERT INTO institutional_memberships(
             id,organization_id,account_email,member_role,status,effective_at,
             expires_at,verified_by,verification_ref,demo_only
           ) VALUES(?,?,?,?, 'active',?,?,?,?,?)
           ON CONFLICT(organization_id,account_email,member_role) DO UPDATE SET
             status='active',
             effective_at=excluded.effective_at,
             expires_at=excluded.expires_at,
             verified_by=excluded.verified_by,
             verification_ref=excluded.verification_ref,
             demo_only=excluded.demo_only""",
        (
            member_id,organization_id,account_email,member_role,now,expires_at,
            verified_by,str(verification_ref or "")[:500],int(bool(demo_only)),
        ),
    )
    return dict(c.execute(
        "SELECT * FROM institutional_memberships WHERE id=?",(member_id,)
    ).fetchone())


def _active_member(c,organization_id,account_email,member_roles,now=None):
    now=int(now or time.time())
    member_roles=tuple(member_roles)
    if not member_roles:
        return None
    placeholders=",".join("?" for _ in member_roles)
    row=c.execute(
        f"""SELECT * FROM institutional_memberships
            WHERE organization_id=? AND account_email=? AND member_role IN ({placeholders})
              AND status='active' AND effective_at<=?
              AND (expires_at IS NULL OR expires_at>?)
            ORDER BY CASE member_role WHEN 'administrator' THEN 1 WHEN 'operator' THEN 2 ELSE 3 END
            LIMIT 1""",
        (organization_id,str(account_email or "").lower(),*member_roles,now,now),
    ).fetchone()
    return dict(row) if row else None


def _current_qualification(c,organization_id):
    return c.execute(
        """SELECT * FROM syndication_partner_qualifications
           WHERE organization_id=?
           ORDER BY created_at DESC,id DESC LIMIT 1""",
        (organization_id,),
    ).fetchone()


def refresh_qualification_state(c,organization_id,now=None):
    now=int(now or time.time())
    row=_current_qualification(c,organization_id)
    if not row:
        return None
    if row["status"] in ("suspended","revoked","expired"):
        return dict(row)
    if row["valid_until"] is not None and int(row["valid_until"])<=now:
        c.execute(
            "UPDATE syndication_partner_qualifications SET status='expired' WHERE id=?",
            (row["id"],),
        )
    elif row["next_requalification_at"] is not None and int(row["next_requalification_at"])<=now:
        c.execute(
            """UPDATE syndication_partner_qualifications
               SET status='requalification_due'
               WHERE id=? AND status='qualified'""",
            (row["id"],),
        )
    return dict(c.execute(
        "SELECT * FROM syndication_partner_qualifications WHERE id=?",(row["id"],)
    ).fetchone())


def start_qualification(c,organization_id,actor,validity_seconds=15552000,demo_only=False):
    org=_organization(c,organization_id)
    if int(org["demo_only"])!=int(bool(demo_only)):
        raise ValueError("qualification_demo_boundary_mismatch")
    validity_seconds=int(validity_seconds)
    if validity_seconds<86400 or validity_seconds>31536000:
        raise ValueError("qualification_validity_invalid")
    current=_current_qualification(c,organization_id)
    if current and current["status"]=="revoked":
        raise ValueError("qualification_revoked_reinstatement_required")
    if current and current["status"] in ("pending","qualified","requalification_due"):
        raise ValueError("qualification_cycle_already_open")
    now=int(time.time())
    seed=f"{organization_id}|{QUALIFICATION_VERSION}|{now}|{time.time_ns()}"
    qualification_id="qual:"+hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    c.execute(
        """INSERT INTO syndication_partner_qualifications(
             id,organization_id,status,qualification_version,created_at,created_by,demo_only
           ) VALUES(?,?,'pending',?,?,?,?)""",
        (qualification_id,organization_id,QUALIFICATION_VERSION,now,actor,int(bool(demo_only))),
    )
    for scope in ALL_CONFORMANCE_SCOPES:
        c.execute(
            """INSERT INTO syndication_conformance_checks(
                 id,qualification_id,scope_key,status,demo_only
               ) VALUES(?,?,?,'pending',?)""",
            (f"conf:{qualification_id}:{scope}",qualification_id,scope,int(bool(demo_only))),
        )
    return qualification_snapshot(c,organization_id)


def record_conformance(
    c,qualification_id,scope_key,status,actor,evidence_ref,details="",
    expires_at=None,
):
    if scope_key not in ALL_CONFORMANCE_SCOPES:
        raise ValueError("conformance_scope_invalid")
    if status not in ("passed","failed","waived"):
        raise ValueError("conformance_status_invalid")
    q=c.execute(
        "SELECT id,status,demo_only FROM syndication_partner_qualifications WHERE id=?",
        (qualification_id,),
    ).fetchone()
    if not q:
        raise ValueError("qualification_not_found")
    if q["status"] not in ("pending","requalification_due"):
        raise ValueError("qualification_not_testable")
    evidence_ref=str(evidence_ref or "").strip()
    if status=="passed" and not evidence_ref:
        raise ValueError("conformance_evidence_required")
    if scope_key in REQUIRED_CONFORMANCE_SCOPES and status=="waived":
        raise ValueError("required_conformance_cannot_be_waived")
    now=int(time.time())
    if expires_at is not None and int(expires_at)<=now:
        raise ValueError("conformance_expiry_invalid")
    c.execute(
        """UPDATE syndication_conformance_checks
           SET status=?,evidence_ref=?,checked_at=?,checked_by=?,expires_at=?,details=?
           WHERE qualification_id=? AND scope_key=?""",
        (
            status,evidence_ref[:500],now,actor,expires_at,str(details or "")[:1000],
            qualification_id,scope_key,
        ),
    )
    return dict(c.execute(
        """SELECT id,qualification_id,scope_key,status,evidence_ref,checked_at,checked_by,
                  expires_at,details,demo_only
           FROM syndication_conformance_checks
           WHERE qualification_id=? AND scope_key=?""",
        (qualification_id,scope_key),
    ).fetchone())


def finalize_qualification(c,qualification_id,actor,validity_seconds=15552000):
    q=c.execute(
        "SELECT * FROM syndication_partner_qualifications WHERE id=?",
        (qualification_id,),
    ).fetchone()
    if not q:
        raise ValueError("qualification_not_found")
    if q["status"] not in ("pending","requalification_due"):
        raise ValueError("qualification_not_finalizable")
    checks={
        r["scope_key"]:dict(r)
        for r in c.execute(
            "SELECT * FROM syndication_conformance_checks WHERE qualification_id=?",
            (qualification_id,),
        )
    }
    missing=[scope for scope in REQUIRED_CONFORMANCE_SCOPES if checks.get(scope,{}).get("status")!="passed"]
    if missing:
        raise ValueError("required_conformance_not_passed")
    now=int(time.time())
    for scope in REQUIRED_CONFORMANCE_SCOPES:
        expiry=checks[scope].get("expires_at")
        if expiry is not None and int(expiry)<=now:
            raise ValueError("conformance_evidence_expired")
    validity_seconds=int(validity_seconds)
    if validity_seconds<86400 or validity_seconds>31536000:
        raise ValueError("qualification_validity_invalid")
    requested_valid_until=now+validity_seconds
    required_expiries=[
        int(checks[scope]["expires_at"])
        for scope in REQUIRED_CONFORMANCE_SCOPES
        if checks[scope].get("expires_at") is not None
    ]
    valid_until=min([requested_valid_until,*required_expiries]) if required_expiries else requested_valid_until
    remaining=max(1,valid_until-now)
    next_requalification_at=now+max(3600,int(remaining*0.8))
    if next_requalification_at>=valid_until:
        next_requalification_at=max(now+1,valid_until-1)
    c.execute(
        """UPDATE syndication_partner_qualifications
           SET status='qualified',effective_at=?,valid_until=?,next_requalification_at=?,
               qualified_by=?,reason=''
           WHERE id=?""",
        (now,valid_until,next_requalification_at,actor,qualification_id),
    )
    return qualification_snapshot(c,q["organization_id"])


def _require_qualified(c,organization_id,now=None):
    q=refresh_qualification_state(c,organization_id,now=now)
    if not q or q["status"]!="qualified":
        raise ValueError("syndication_partner_not_qualified")
    return q


def suspend_qualification(c,organization_id,reason,actor):
    q=_current_qualification(c,organization_id)
    if not q:
        raise ValueError("qualification_not_found")
    if q["status"]=="revoked":
        raise ValueError("qualification_revoked")
    reason=str(reason or "").strip()
    if len(reason)<3:
        raise ValueError("qualification_reason_required")
    now=int(time.time())
    c.execute(
        """UPDATE syndication_partner_qualifications
           SET status='suspended',suspended_at=?,suspended_by=?,reason=?
           WHERE id=?""",
        (now,actor,reason[:500],q["id"]),
    )
    c.execute(
        "UPDATE syndication_subscriptions SET status='paused' WHERE organization_id=? AND status='active'",
        (organization_id,),
    )
    return qualification_snapshot(c,organization_id)


def revoke_qualification(c,organization_id,reason,actor):
    q=_current_qualification(c,organization_id)
    if not q:
        raise ValueError("qualification_not_found")
    if q["status"]=="revoked":
        return qualification_snapshot(c,organization_id)
    reason=str(reason or "").strip()
    if len(reason)<3:
        raise ValueError("qualification_reason_required")
    now=int(time.time())
    c.execute(
        """UPDATE syndication_partner_qualifications
           SET status='revoked',revoked_at=?,revoked_by=?,reason=?
           WHERE id=?""",
        (now,actor,reason[:500],q["id"]),
    )
    c.execute(
        "UPDATE syndication_subscriptions SET status='revoked' WHERE organization_id=? AND status IN ('active','paused')",
        (organization_id,),
    )
    return qualification_snapshot(c,organization_id)


def qualification_snapshot(c,organization_id):
    org=_organization(c,organization_id)
    q=refresh_qualification_state(c,organization_id)
    if not q:
        return {
            "organizationId":organization_id,
            "organizationName":org["name"],
            "qualification":None,
            "certifications":[],
            "truthBoundary":{
                "technicalProcessCertificationOnly":True,
                "medicalEfficacyCertified":False,
                "externalAccreditationInferred":False,
            },
        }
    checks=[
        dict(r) for r in c.execute(
            """SELECT scope_key,status,evidence_ref,checked_at,checked_by,expires_at,details
               FROM syndication_conformance_checks
               WHERE qualification_id=? ORDER BY scope_key""",
            (q["id"],),
        )
    ]
    return {
        "organizationId":organization_id,
        "organizationName":org["name"],
        "qualification":{
            k:q[k] for k in (
                "id","status","qualification_version","effective_at","valid_until",
                "next_requalification_at","qualified_by","reason","demo_only"
            )
        },
        "certifications":[
            {
                "scope":x["scope_key"],
                "status":x["status"],
                "evidenceRef":x["evidence_ref"],
                "checkedAt":x["checked_at"],
                "expiresAt":x["expires_at"],
                "processTechnicalOnly":True,
            }
            for x in checks
        ],
        "requiredScopes":list(REQUIRED_CONFORMANCE_SCOPES),
        "truthBoundary":{
            "technicalProcessCertificationOnly":True,
            "medicalEfficacyCertified":False,
            "medicalSafetyCertified":False,
            "externalAccreditationInferred":False,
        },
    }


def public_certification(c,organization_id):
    snapshot=qualification_snapshot(c,organization_id)
    qualification=snapshot.get("qualification")
    certifications=[
        {
            "scope":x["scope"],
            "status":x["status"],
            "expiresAt":x["expiresAt"],
            "label":{
                "evidence_api_integration":"Evidence API Integrated",
                "withdrawal_propagation":"Withdrawal Propagation Verified",
                "disclosure_workflow":"Disclosure Workflow Integrated",
                "credential_verification":"Credential Verification Integrated",
                "education_completion_sync":"Education Completion Sync Integrated",
            }.get(x["scope"],x["scope"]),
        }
        for x in snapshot.get("certifications") or []
        if x.get("status")=="passed"
    ]
    return {
        "registryVersion":"promomed-certified-syndication-registry-v1",
        "organizationId":snapshot["organizationId"],
        "organizationName":snapshot["organizationName"],
        "qualificationStatus":qualification.get("status") if qualification else "not_qualified",
        "qualificationVersion":qualification.get("qualification_version") if qualification else None,
        "effectiveAt":qualification.get("effective_at") if qualification else None,
        "validUntil":qualification.get("valid_until") if qualification else None,
        "nextRequalificationAt":qualification.get("next_requalification_at") if qualification else None,
        "certifications":certifications,
        "truthBoundary":{
            "technicalProcessCertificationOnly":True,
            "medicalEfficacyCertified":False,
            "medicalSafetyCertified":False,
            "professionalAccreditation":False,
            "commercialEndorsement":False,
        },
    }


def create_subscription(
    c,organization_id,subscription_scope,scope_ref,actor,
    update_sla_seconds=86400,withdrawal_sla_seconds=14400,expires_at=None,
):
    org=_organization(c,organization_id)
    _require_qualified(c,organization_id)
    if not (_active_role(c,organization_id,"consumer") or _active_role(c,organization_id,"publisher")):
        raise ValueError("institutional_delivery_role_required")
    if subscription_scope not in ("all_evidence","artifact_kind","artifact","topic"):
        raise ValueError("subscription_scope_invalid")
    scope_ref=str(scope_ref or "").strip()
    if subscription_scope!="all_evidence" and not scope_ref:
        raise ValueError("subscription_scope_ref_required")
    update_sla_seconds=int(update_sla_seconds)
    withdrawal_sla_seconds=int(withdrawal_sla_seconds)
    if not (3600<=update_sla_seconds<=604800):
        raise ValueError("update_sla_invalid")
    if not (3600<=withdrawal_sla_seconds<=172800):
        raise ValueError("withdrawal_sla_invalid")
    now=int(time.time())
    if expires_at is not None and int(expires_at)<=now:
        raise ValueError("subscription_expiry_invalid")
    seed=f"{organization_id}|{subscription_scope}|{scope_ref}"
    subscription_id="sub:"+hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    c.execute(
        """INSERT INTO syndication_subscriptions(
             id,organization_id,subscription_scope,scope_ref,status,
             update_sla_seconds,withdrawal_sla_seconds,effective_at,expires_at,
             created_at,created_by,demo_only
           ) VALUES(?,?,?,?, 'active',?,?,?,?,?,?,?)
           ON CONFLICT(organization_id,subscription_scope,scope_ref) DO UPDATE SET
             status='active',
             update_sla_seconds=excluded.update_sla_seconds,
             withdrawal_sla_seconds=excluded.withdrawal_sla_seconds,
             effective_at=excluded.effective_at,
             expires_at=excluded.expires_at,
             created_by=excluded.created_by""",
        (
            subscription_id,organization_id,subscription_scope,scope_ref,
            update_sla_seconds,withdrawal_sla_seconds,now,expires_at,
            now,actor,int(org["demo_only"]),
        ),
    )
    return dict(c.execute(
        "SELECT * FROM syndication_subscriptions WHERE id=?",(subscription_id,)
    ).fetchone())


def matching_subscription(c,organization_id,artifact_kind,artifact_ref,topic=None,now=None):
    now=int(now or time.time())
    qualification=refresh_qualification_state(c,organization_id,now=now)
    if not qualification or qualification["status"]!="qualified":
        return None
    rows=list(c.execute(
        """SELECT * FROM syndication_subscriptions
           WHERE organization_id=? AND status='active' AND effective_at<=?
             AND (expires_at IS NULL OR expires_at>?)
           ORDER BY CASE subscription_scope
             WHEN 'artifact' THEN 1 WHEN 'topic' THEN 2 WHEN 'artifact_kind' THEN 3 ELSE 4 END,
             created_at DESC""",
        (organization_id,now,now),
    ))
    for row in rows:
        if row["subscription_scope"]=="all_evidence":
            return dict(row)
        if row["subscription_scope"]=="artifact" and row["scope_ref"]==f"{artifact_kind}:{artifact_ref}":
            return dict(row)
        if row["subscription_scope"]=="artifact_kind" and row["scope_ref"]==artifact_kind:
            return dict(row)
        if row["subscription_scope"]=="topic" and topic and row["scope_ref"]==topic:
            return dict(row)
    return None


def _matching_subscription_at(c,organization_id,artifact_kind,artifact_ref,at_time,topic=None):
    rows=list(c.execute(
        """SELECT * FROM syndication_subscriptions
           WHERE organization_id=? AND effective_at<=?
             AND (expires_at IS NULL OR expires_at>?)
           ORDER BY CASE subscription_scope
             WHEN 'artifact' THEN 1 WHEN 'topic' THEN 2 WHEN 'artifact_kind' THEN 3 ELSE 4 END,
             created_at DESC""",
        (organization_id,int(at_time),int(at_time)),
    ))
    for row in rows:
        if row["subscription_scope"]=="all_evidence":
            return dict(row)
        if row["subscription_scope"]=="artifact" and row["scope_ref"]==f"{artifact_kind}:{artifact_ref}":
            return dict(row)
        if row["subscription_scope"]=="artifact_kind" and row["scope_ref"]==artifact_kind:
            return dict(row)
        if row["subscription_scope"]=="topic" and topic and row["scope_ref"]==topic:
            return dict(row)
    return None


def create_delivery_obligations(c,package_id,obligation_type,now=None):
    if obligation_type not in ("update","withdrawal"):
        raise ValueError("obligation_type_invalid")
    now=int(now or time.time())
    package=c.execute(
        "SELECT artifact_kind,artifact_ref FROM evidence_exchange_packages WHERE id=?",
        (package_id,),
    ).fetchone()
    if not package:
        return []
    created=[]
    deliveries=list(c.execute(
        """SELECT id,organization_id,delivered_at FROM evidence_exchange_deliveries
           WHERE package_id=? AND status IN ('delivered','acknowledged','withdrawn','superseded')""",
        (package_id,),
    ))
    for delivery in deliveries:
        subscription=_matching_subscription_at(
            c,delivery["organization_id"],package["artifact_kind"],package["artifact_ref"],
            delivery["delivered_at"]
        )
        if not subscription:
            continue
        sla=subscription["withdrawal_sla_seconds"] if obligation_type=="withdrawal" else subscription["update_sla_seconds"]
        due_at=now+int(sla)
        obligation_id=f"obl:{delivery['id']}:{obligation_type}"
        c.execute(
            """INSERT INTO syndication_delivery_obligations(
                 id,delivery_id,obligation_type,due_at,status,created_at,demo_only
               ) VALUES(?,?,?,?,'pending',?,?)
               ON CONFLICT(delivery_id,obligation_type) DO NOTHING""",
            (
                obligation_id,delivery["id"],obligation_type,due_at,now,
                int(subscription["demo_only"]),
            ),
        )
        created.append(obligation_id)
    return created


def acknowledge_obligation(c,obligation_id,organization_id,evidence_ref,actor=None):
    row=c.execute(
        """SELECT o.*,d.organization_id
           FROM syndication_delivery_obligations o
           JOIN evidence_exchange_deliveries d ON d.id=o.delivery_id
           WHERE o.id=?""",
        (obligation_id,),
    ).fetchone()
    if not row:
        raise ValueError("obligation_not_found")
    if row["organization_id"]!=organization_id:
        raise ValueError("obligation_organization_mismatch")
    if actor and not _active_member(c,organization_id,actor,("operator","administrator")):
        raise ValueError("institutional_operator_membership_required")
    if row["status"]=="acknowledged":
        return dict(row)
    if row["status"]!="pending":
        raise ValueError("obligation_not_acknowledgeable")
    evidence_ref=str(evidence_ref or "").strip()
    if not evidence_ref:
        raise ValueError("obligation_evidence_required")
    now=int(time.time())
    status="acknowledged" if now<=int(row["due_at"]) else "breached"
    c.execute(
        """UPDATE syndication_delivery_obligations
           SET status=?,acknowledged_at=?,evidence_ref=? WHERE id=?""",
        (status,now,evidence_ref[:500],obligation_id),
    )
    return dict(c.execute(
        "SELECT * FROM syndication_delivery_obligations WHERE id=?",(obligation_id,)
    ).fetchone())


def mark_overdue_obligations(c,now=None):
    now=int(now or time.time())
    c.execute(
        """UPDATE syndication_delivery_obligations
           SET status='breached'
           WHERE status='pending' AND due_at<?""",
        (now,),
    )
    return c.execute(
        "SELECT COUNT(*) n FROM syndication_delivery_obligations WHERE status='breached'"
    ).fetchone()["n"]


def submit_contribution(c,organization_id,contribution_type,title,payload,submitted_by):
    org=_organization(c,organization_id)
    _require_qualified(c,organization_id)
    if not _active_role(c,organization_id,"contributor"):
        raise ValueError("institutional_contributor_role_required")
    if not _active_member(c,organization_id,submitted_by,("contributor","administrator")):
        raise ValueError("institutional_contributor_membership_required")
    if contribution_type not in CONTRIBUTION_TYPES:
        raise ValueError("contribution_type_invalid")
    title=str(title or "").strip()
    if not title:
        raise ValueError("contribution_title_required")
    if not isinstance(payload,dict) or not payload:
        raise ValueError("contribution_payload_required")
    body={
        "contributionVersion":CONTRIBUTION_VERSION,
        "organizationId":organization_id,
        "contributionType":contribution_type,
        "title":title[:240],
        "payload":payload,
    }
    digest=_sha(body)
    existing=c.execute(
        "SELECT id,status FROM external_contributions WHERE payload_sha256=?",
        (digest,),
    ).fetchone()
    if existing:
        return {"id":existing["id"],"status":existing["status"],"idempotentReplay":True}
    now=int(time.time())
    contribution_id="contrib:"+digest[:24]
    c.execute(
        """INSERT INTO external_contributions(
             id,organization_id,contribution_type,title,payload_json,payload_sha256,
             status,submitted_by,submitted_at,demo_only
           ) VALUES(?,?,?,?,?,?,'submitted',?,?,?)""",
        (
            contribution_id,organization_id,contribution_type,title[:240],
            _canonical(body),digest,submitted_by,now,int(org["demo_only"]),
        ),
    )
    return {"id":contribution_id,"status":"submitted","payloadSha256":digest,"idempotentReplay":False}


def revise_contribution(c,contribution_id,title,payload,submitted_by):
    prior=c.execute(
        "SELECT * FROM external_contributions WHERE id=?",(contribution_id,)
    ).fetchone()
    if not prior:
        raise ValueError("contribution_not_found")
    if prior["status"]!="changes_requested":
        raise ValueError("contribution_revision_not_allowed")
    if str(prior["submitted_by"] or "").lower()!=str(submitted_by or "").lower():
        raise ValueError("contribution_submitter_mismatch")
    _require_qualified(c,prior["organization_id"])
    if not _active_role(c,prior["organization_id"],"contributor"):
        raise ValueError("institutional_contributor_role_required")
    if not _active_member(
        c,prior["organization_id"],submitted_by,("contributor","administrator")
    ):
        raise ValueError("institutional_contributor_membership_required")
    title=str(title or prior["title"]).strip()
    if not isinstance(payload,dict) or not payload:
        raise ValueError("contribution_payload_required")
    body={
        "contributionVersion":CONTRIBUTION_VERSION,
        "organizationId":prior["organization_id"],
        "contributionType":prior["contribution_type"],
        "title":title[:240],
        "payload":payload,
        "supersedesContributionId":contribution_id,
    }
    digest=_sha(body)
    existing=c.execute(
        "SELECT id,status FROM external_contributions WHERE payload_sha256=?",
        (digest,),
    ).fetchone()
    if existing:
        return {
            "id":existing["id"],
            "status":existing["status"],
            "supersedesContributionId":contribution_id,
            "idempotentReplay":True,
        }
    now=int(time.time())
    new_id="contrib:"+digest[:24]
    c.execute(
        """INSERT INTO external_contributions(
             id,organization_id,contribution_type,title,payload_json,payload_sha256,
             status,submitted_by,submitted_at,supersedes_contribution_id,demo_only
           ) VALUES(?,?,?,?,?,?,'submitted',?,?,?,?)""",
        (
            new_id,prior["organization_id"],prior["contribution_type"],title[:240],
            _canonical(body),digest,submitted_by,now,contribution_id,int(prior["demo_only"]),
        ),
    )
    return {
        "id":new_id,
        "status":"submitted",
        "payloadSha256":digest,
        "supersedesContributionId":contribution_id,
        "idempotentReplay":False,
    }


def review_contribution(c,contribution_id,review_role,reviewer,decision,rationale,conflict_state="none"):
    if review_role not in REVIEW_ROLES:
        raise ValueError("contribution_review_role_invalid")
    if decision not in ("accept","reject","request_changes"):
        raise ValueError("contribution_review_decision_invalid")
    if conflict_state not in ("none","potential","material"):
        raise ValueError("contribution_conflict_state_invalid")
    row=c.execute(
        "SELECT * FROM external_contributions WHERE id=?",(contribution_id,)
    ).fetchone()
    if not row:
        raise ValueError("contribution_not_found")
    if row["status"] in ("admitted","withdrawn","rejected"):
        raise ValueError("contribution_not_reviewable")
    reviewer=str(reviewer or "").lower()
    if reviewer==str(row["submitted_by"] or "").lower():
        raise ValueError("contribution_self_review_forbidden")
    existing=c.execute(
        "SELECT id FROM external_contribution_reviews WHERE contribution_id=? AND review_role=?",
        (contribution_id,review_role),
    ).fetchone()
    if existing:
        raise ValueError("contribution_review_already_recorded")
    if conflict_state!="none" and decision=="accept":
        raise ValueError("contribution_conflict_blocks_acceptance")

    if review_role=="editorial":
        account=c.execute(
            "SELECT role,status FROM accounts WHERE email=?",(reviewer,)
        ).fetchone()
        if not account or account["role"] not in ("editor","governance") or account["status"]!="active":
            raise ValueError("editorial_reviewer_not_authorized")
    else:
        reviewer_authority.validate_reviewer(
            c,reviewer,SCIENTIFIC_SCOPE,production=not bool(row["demo_only"])
        )

    now=time.time_ns()
    attestation={
        "contributionId":contribution_id,
        "payloadSha256":row["payload_sha256"],
        "reviewRole":review_role,
        "reviewer":reviewer,
        "decision":decision,
        "rationale":str(rationale or "")[:2400],
        "conflictState":conflict_state,
        "reviewedAt":now,
    }
    digest=_sha(attestation)
    review_id="contrib-review:"+digest[:24]
    c.execute(
        """INSERT INTO external_contribution_reviews(
             id,contribution_id,review_role,reviewer,decision,rationale,
             conflict_state,reviewed_at,review_digest,demo_only
           ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (
            review_id,contribution_id,review_role,reviewer,decision,
            attestation["rationale"],conflict_state,now,digest,int(row["demo_only"]),
        ),
    )
    reviews={
        x["review_role"]:dict(x)
        for x in c.execute(
            "SELECT * FROM external_contribution_reviews WHERE contribution_id=?",
            (contribution_id,),
        )
    }
    if decision=="reject":
        status="rejected"
    elif decision=="request_changes":
        status="changes_requested"
    elif reviews.get("editorial",{}).get("decision")=="accept" and reviews.get("scientific",{}).get("decision")=="accept":
        editorial=reviews["editorial"]["reviewer"].lower()
        scientific=reviews["scientific"]["reviewer"].lower()
        if editorial==scientific:
            raise ValueError("contribution_separation_of_duties_violation")
        status="review_ready"
    elif reviews.get("editorial",{}).get("decision")=="accept":
        status="scientific_review"
    else:
        status="editorial_review"
    c.execute("UPDATE external_contributions SET status=? WHERE id=?",(status,contribution_id))
    return {
        "reviewId":review_id,
        "reviewDigest":digest,
        "contributionId":contribution_id,
        "status":status,
    }


def admit_contribution(c,contribution_id,actor):
    row=c.execute(
        "SELECT * FROM external_contributions WHERE id=?",(contribution_id,)
    ).fetchone()
    if not row:
        raise ValueError("contribution_not_found")
    if row["status"]!="review_ready":
        raise ValueError("contribution_reviews_required")
    account=c.execute(
        "SELECT role,status FROM accounts WHERE email=?",(str(actor or "").lower(),)
    ).fetchone()
    if not account or account["role"]!="governance" or account["status"]!="active":
        raise ValueError("governance_admission_required")
    reviews=list(c.execute(
        """SELECT review_role,reviewer,decision,review_digest
           FROM external_contribution_reviews WHERE contribution_id=?
           ORDER BY review_role""",
        (contribution_id,),
    ))
    if len(reviews)!=2 or any(x["decision"]!="accept" for x in reviews):
        raise ValueError("contribution_reviews_required")
    actors={str(row["submitted_by"] or "").lower()}
    actors.update(str(x["reviewer"] or "").lower() for x in reviews)
    if str(actor or "").lower() in actors:
        raise ValueError("contribution_admission_separation_of_duties")
    body={
        "contributionId":contribution_id,
        "organizationId":row["organization_id"],
        "contributionType":row["contribution_type"],
        "payloadSha256":row["payload_sha256"],
        "editorialReviewDigest":next(x["review_digest"] for x in reviews if x["review_role"]=="editorial"),
        "scientificReviewDigest":next(x["review_digest"] for x in reviews if x["review_role"]=="scientific"),
        "admissionDecision":"accepted_into_promomed_governance_queue",
        "canonicalMutation":False,
        "nextAuthority":"domain_editorial_evidence_workflow",
        "medicalEfficacyCertified":False,
    }
    envelope=evidence_checkpoint.sign_portable_statement(
        c,CONTRIBUTION_RECEIPT_TYPE,body,actor=actor
    )
    now=int(time.time())
    receipt_sha=envelope["statementSha256"]
    receipt_id="admission:"+receipt_sha[:24]
    c.execute(
        """INSERT INTO external_contribution_admission_receipts(
             id,contribution_id,receipt_sha256,envelope_json,admitted_at,admitted_by,demo_only
           ) VALUES(?,?,?,?,?,?,?)""",
        (
            receipt_id,contribution_id,receipt_sha,_canonical(envelope),now,actor,
            int(row["demo_only"]),
        ),
    )
    c.execute(
        """UPDATE external_contributions
           SET status='admitted',admitted_at=?,admitted_by=? WHERE id=?""",
        (now,actor,contribution_id),
    )
    return {
        "contributionId":contribution_id,
        "status":"admitted",
        "receiptId":receipt_id,
        "receipt":envelope,
        "canonicalMutation":False,
    }


def contribution_receipt(c,contribution_id):
    row=c.execute(
        """SELECT receipt_sha256,envelope_json,admitted_at,admitted_by
           FROM external_contribution_admission_receipts WHERE contribution_id=?""",
        (contribution_id,),
    ).fetchone()
    if not row:
        raise ValueError("contribution_receipt_not_found")
    return {
        "receiptSha256":row["receipt_sha256"],
        "envelope":json.loads(row["envelope_json"]),
        "admittedAt":row["admitted_at"],
        "admittedByRole":"governance",
    }


def verify_contribution_receipt(document,issuer_document):
    envelope=(document or {}).get("envelope") or {}
    result=evidence_checkpoint.verify_portable_statement(envelope,issuer_document)
    if result.get("status")!="VALID_PORTABLE_STATEMENT":
        return result
    if result.get("statementType")!=CONTRIBUTION_RECEIPT_TYPE:
        return {"status":"WRONG_STATEMENT_TYPE","signature_valid":True}
    body=(envelope.get("payload") or {}).get("body") or {}
    if body.get("canonicalMutation") is not False or body.get("medicalEfficacyCertified") is not False:
        return {"status":"ADMISSION_BOUNDARY_INVALID","signature_valid":True}
    return {
        **result,
        "status":"VALID_CONTRIBUTION_ADMISSION_RECEIPT",
        "canonicalMutation":False,
        "medicalEfficacyCertified":False,
    }


def network_snapshot(c,organization_id=None):
    mark_overdue_obligations(c)
    if organization_id:
        organizations=[organization_id]
    else:
        organizations=[r["id"] for r in c.execute(
            "SELECT id FROM institutional_organizations ORDER BY id"
        )]
    return {
        "version":"certified-syndication-network-v1",
        "partners":[qualification_snapshot(c,oid) for oid in organizations],
        "memberships":[
            dict(r) for r in c.execute(
                """SELECT id,organization_id,account_email,member_role,status,effective_at,
                          expires_at,verified_by,verification_ref,demo_only
                   FROM institutional_memberships
                   ORDER BY organization_id,account_email,member_role"""
            )
        ],
        "subscriptions":[
            dict(r) for r in c.execute(
                """SELECT id,organization_id,subscription_scope,scope_ref,status,
                          update_sla_seconds,withdrawal_sla_seconds,effective_at,expires_at,demo_only
                   FROM syndication_subscriptions
                   ORDER BY organization_id,subscription_scope,scope_ref"""
            )
        ],
        "obligations":[
            dict(r) for r in c.execute(
                """SELECT id,delivery_id,obligation_type,due_at,status,acknowledged_at,evidence_ref,demo_only
                   FROM syndication_delivery_obligations
                   ORDER BY due_at,id"""
            )
        ],
        "contributions":[
            {
                "id":r["id"],
                "organizationId":r["organization_id"],
                "contributionType":r["contribution_type"],
                "title":r["title"],
                "payloadSha256":r["payload_sha256"],
                "status":r["status"],
                "submittedBy":r["submitted_by"],
                "submittedAt":r["submitted_at"],
                "admittedAt":r["admitted_at"],
                "admittedBy":r["admitted_by"],
                "supersedesContributionId":r["supersedes_contribution_id"],
                "demoOnly":bool(r["demo_only"]),
            }
            for r in c.execute(
                """SELECT * FROM external_contributions
                   ORDER BY submitted_at DESC,id DESC LIMIT 100"""
            )
        ],
        "truthBoundary":{
            "certificationScope":"technical_and_process_only",
            "medicalEfficacyCertified":False,
            "medicalSafetyCertified":False,
            "partnerSelfApproval":False,
            "externalContributionDirectCanonicalMutation":False,
            "contributorRoleIsNowSubmissionEnabled":True,
        },
    }
