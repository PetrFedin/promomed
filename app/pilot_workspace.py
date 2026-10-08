import json
import time

WORKSPACE_VERSION = "promomed-institutional-pilot-readiness-v1"


def _organization(c, organization_id):
    row = c.execute(
        """SELECT id,name,organization_type,status,external_ref,credential_source,
                  partner_id,created_at,created_by,demo_only
           FROM institutional_organizations WHERE id=?""",
        (organization_id,),
    ).fetchone()
    if not row:
        raise ValueError("organization_not_found")
    return dict(row)


def _active_members(c, organization_id, now):
    rows = list(c.execute(
        """SELECT account_email,member_role,effective_at,expires_at,verification_ref,demo_only
           FROM institutional_memberships
           WHERE organization_id=? AND status='active'
             AND effective_at<=? AND (expires_at IS NULL OR expires_at>?)
           ORDER BY CASE member_role
             WHEN 'administrator' THEN 1 WHEN 'operator' THEN 2 ELSE 3 END,
             account_email""",
        (organization_id, now, now),
    ))
    return [dict(r) for r in rows]


def _active_roles(c, organization_id, now):
    rows = list(c.execute(
        """SELECT role_scope,effective_at,expires_at,verification_ref,demo_only
           FROM institutional_role_bindings
           WHERE organization_id=? AND status='active'
             AND effective_at<=? AND (expires_at IS NULL OR expires_at>?)
           ORDER BY role_scope""",
        (organization_id, now, now),
    ))
    return [dict(r) for r in rows]


def _qualification(c, organization_id):
    row = c.execute(
        """SELECT id,status,qualification_version,effective_at,valid_until,
                  next_requalification_at,reason,demo_only,created_at
           FROM syndication_partner_qualifications
           WHERE organization_id=?
           ORDER BY CASE
             WHEN status IN ('pending','qualified','requalification_due') THEN 0 ELSE 1
           END,created_at DESC,id DESC
           LIMIT 1""",
        (organization_id,),
    ).fetchone()
    return dict(row) if row else None


def _anchors(c, organization_id):
    rows = list(c.execute(
        """SELECT a.id,a.issuer_id,a.key_id,a.alg,a.rotated_from_anchor_id,a.demo_only,
                  s.status,s.proof_verified_at,s.valid_from,s.valid_until,
                  s.retired_at,s.suspended_at,s.revoked_at
           FROM institutional_federated_anchors a
           JOIN institutional_federated_anchor_state s ON s.anchor_id=a.id
           WHERE a.organization_id=?
           ORDER BY COALESCE(s.valid_from,a.created_at),a.id""",
        (organization_id,),
    ))
    return [dict(r) for r in rows]


def _latest_evaluation(c, organization_id):
    row = c.execute(
        """SELECT id,profile_id,anchor_id,compatibility_status,evaluation_sha256,
                  evaluation_json,evaluated_at,demo_only
           FROM federation_profile_evaluations
           WHERE organization_id=?
           ORDER BY evaluated_at DESC,id DESC
           LIMIT 1""",
        (organization_id,),
    ).fetchone()
    if not row:
        return None
    data = dict(row)
    try:
        data["evaluation"] = json.loads(data.pop("evaluation_json"))
    except Exception:
        data["evaluation"] = None
        data.pop("evaluation_json", None)
    return data


def _latest_discovery_bundle(c, organization_id):
    row = c.execute(
        """SELECT id,profile_id,bundle_sha256,issued_at,valid_until,demo_only
           FROM federation_discovery_bundles
           WHERE organization_id=?
           ORDER BY issued_at DESC,id DESC
           LIMIT 1""",
        (organization_id,),
    ).fetchone()
    return dict(row) if row else None


def _delivery_endpoints(c, organization_id):
    rows = list(c.execute(
        """SELECT id,status,verified_at,created_at,demo_only
           FROM syndication_delivery_endpoints
           WHERE organization_id=?
           ORDER BY created_at DESC,id DESC""",
        (organization_id,),
    ))
    return [dict(r) for r in rows]


def _step(key, label, state, evidence=None, blocker=None, required=True):
    return {
        "key": key,
        "label": label,
        "state": state,
        "required": bool(required),
        "evidence": evidence,
        "blocker": blocker,
    }


def snapshot(c, organization_id, now=None):
    now = int(now or time.time())
    organization_id = str(organization_id or "").strip()[:100]
    if not organization_id:
        raise ValueError("organization_id_required")

    org = _organization(c, organization_id)
    members = _active_members(c, organization_id, now)
    roles = _active_roles(c, organization_id, now)
    qualification = _qualification(c, organization_id)
    anchors = _anchors(c, organization_id)
    evaluation = _latest_evaluation(c, organization_id)
    bundle = _latest_discovery_bundle(c, organization_id)
    endpoints = _delivery_endpoints(c, organization_id)

    authoritative_members = [
        m for m in members
        if m["member_role"] in ("administrator", "operator")
        and not bool(m["demo_only"])
    ]
    active_roles = sorted({
        r["role_scope"] for r in roles if not bool(r["demo_only"])
    })
    active_anchors = [
        a for a in anchors
        if a["status"] == "active"
        and a["proof_verified_at"] is not None
        and not bool(a["demo_only"])
        and (a["valid_from"] is None or int(a["valid_from"]) <= now)
        and (a["valid_until"] is None or int(a["valid_until"]) > now)
    ]
    active_endpoint = next(
        (
            e for e in endpoints
            if e["status"] == "active"
            and e["verified_at"] is not None
            and not bool(e["demo_only"])
        ),
        None,
    )

    non_demo_identity = org["status"] == "active" and not bool(org["demo_only"])
    attributable_identity = non_demo_identity and bool(
        str(org.get("external_ref") or "").strip()
        and str(org.get("credential_source") or "").strip()
    )
    qualified = bool(
        qualification
        and qualification["status"] == "qualified"
        and not bool(qualification["demo_only"])
        and (qualification["valid_until"] is None or int(qualification["valid_until"]) > now)
    )
    compatible = bool(
        evaluation
        and evaluation["compatibility_status"] in ("compatible", "compatible_with_warnings")
        and not bool(evaluation["demo_only"])
    )
    current_bundle = bool(
        bundle
        and not bool(bundle["demo_only"])
        and int(bundle["valid_until"] or 0) > now
    )

    steps = [
        _step(
            "institution_identity",
            "Attributable institutional identity",
            "ready" if attributable_identity else ("demo_only" if bool(org["demo_only"]) else "blocked"),
            {
                "organizationId": org["id"],
                "name": org["name"],
                "type": org["organization_type"],
                "externalRef": org["external_ref"],
                "credentialSource": org["credential_source"],
            },
            None if attributable_identity else (
                "demo_organization_cannot_be_external_pilot"
                if bool(org["demo_only"])
                else "external_identity_evidence_required"
            ),
        ),
        _step(
            "human_authority",
            "Verified institutional administrator/operator",
            "ready" if authoritative_members else "blocked",
            {
                "activeMemberCount": len(members),
                "authoritativeNonDemoCount": len(authoritative_members),
            },
            None if authoritative_members else "verified_institutional_member_required",
        ),
        _step(
            "institution_role",
            "Institutional role scope",
            "ready" if active_roles else "blocked",
            {"activeNonDemoRoles": active_roles},
            None if active_roles else "publisher_consumer_or_contributor_role_required",
        ),
        _step(
            "syndication_qualification",
            "Technical/process qualification",
            "ready" if qualified else "blocked",
            {
                "qualificationId": qualification["id"] if qualification else None,
                "status": qualification["status"] if qualification else None,
                "validUntil": qualification["valid_until"] if qualification else None,
            },
            None if qualified else "qualified_syndication_status_required",
        ),
        _step(
            "independent_key",
            "Independently controlled institutional public key",
            "ready" if active_anchors else "blocked",
            {
                "activeAdmittedAnchorCount": len(active_anchors),
                "anchorIds": [a["id"] for a in active_anchors],
            },
            None if active_anchors else "active_proof_verified_non_demo_anchor_required",
        ),
        _step(
            "federation_compatibility",
            "Federation interoperability evaluation",
            "ready" if compatible else "blocked",
            {
                "evaluationId": evaluation["id"] if evaluation else None,
                "status": evaluation["compatibility_status"] if evaluation else None,
                "evaluatedAt": evaluation["evaluated_at"] if evaluation else None,
            },
            None if compatible else "compatible_profile_evaluation_required",
        ),
        _step(
            "portable_evidence_pack",
            "Current portable discovery evidence pack",
            "ready" if current_bundle else "blocked",
            {
                "bundleId": bundle["id"] if bundle else None,
                "bundleSha256": bundle["bundle_sha256"] if bundle else None,
                "validUntil": bundle["valid_until"] if bundle else None,
            },
            None if current_bundle else "current_non_demo_discovery_bundle_required",
        ),
        _step(
            "delivery_runtime",
            "Verified production delivery endpoint",
            "ready" if active_endpoint else "not_started",
            {
                "endpointId": active_endpoint["id"] if active_endpoint else None,
                "verifiedAt": active_endpoint["verified_at"] if active_endpoint else None,
            },
            None if active_endpoint else "verified_delivery_endpoint_not_yet_required_for_admission",
            required=False,
        ),
        _step(
            "participation_evidence",
            "Explicit external pilot participation evidence",
            "blocked",
            None,
            "no_canonical_participation_evidence_authority_implemented_until_real_participant_exists",
        ),
    ]

    blockers = [
        s["blocker"] for s in steps
        if s["required"] and s["state"] != "ready" and s["blocker"]
    ]
    readiness = "ready_for_external_pilot_admission_review" if not blockers else "blocked"

    return {
        "workspaceVersion": WORKSPACE_VERSION,
        "organization": {
            "id": org["id"],
            "name": org["name"],
            "type": org["organization_type"],
            "status": org["status"],
            "demoOnly": bool(org["demo_only"]),
        },
        "readiness": readiness,
        "steps": steps,
        "blockers": blockers,
        "nextAction": blockers[0] if blockers else "governance_external_pilot_admission_review",
        "truthBoundary": {
            "readOnlyProjection": True,
            "createsOrganization": False,
            "createsMembership": False,
            "admitsTrustAnchor": False,
            "changesQualification": False,
            "createsAccreditation": False,
            "createsEndorsement": False,
            "externalAdoptionInferred": False,
            "demoOrganizationCanBecomeRealPilot": False,
        },
    }
