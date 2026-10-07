from app.commanding import custom, error
from app import syndication_network


ROUTES={
    "/api/syndication/qualification/start",
    "/api/syndication/qualification/conformance",
    "/api/syndication/qualification/finalize",
    "/api/syndication/qualification/suspend",
    "/api/syndication/qualification/revoke",
    "/api/institution/member",
    "/api/syndication/subscription",
    "/api/syndication/obligation/acknowledge",
    "/api/external-contribution/submit",
    "/api/external-contribution/revise",
    "/api/external-contribution/review",
    "/api/external-contribution/admit",
}


def _governance_only(role):
    if role!="governance":
        return error("forbidden",403)
    return None


def handle_command(c,route,role,email,data):
    if route not in ROUTES:
        return None

    try:
        if route=="/api/external-contribution/submit":
            result=syndication_network.submit_contribution(
                c,
                str(data.get("organization_id") or "")[:100],
                str(data.get("contribution_type") or "")[:80],
                str(data.get("title") or "")[:240],
                data.get("payload") or {},
                email,
            )
            return custom({"data":result},201 if not result.get("idempotentReplay") else 200)

        if route=="/api/external-contribution/revise":
            result=syndication_network.revise_contribution(
                c,
                str(data.get("contribution_id") or "")[:120],
                str(data.get("title") or "")[:240],
                data.get("payload") or {},
                email,
            )
            return custom({"data":result},201 if not result.get("idempotentReplay") else 200)

        if route=="/api/syndication/obligation/acknowledge":
            result=syndication_network.acknowledge_obligation(
                c,
                str(data.get("obligation_id") or "")[:140],
                str(data.get("organization_id") or "")[:100],
                str(data.get("evidence_ref") or "")[:500],
                actor=email,
            )
            return custom({"data":result})

        if route=="/api/external-contribution/review":
            if role not in ("editor","reviewer","governance"):
                return error("forbidden",403)
            result=syndication_network.review_contribution(
                c,
                str(data.get("contribution_id") or "")[:120],
                str(data.get("review_role") or "")[:30],
                email,
                str(data.get("decision") or "")[:40],
                str(data.get("rationale") or "")[:2400],
                str(data.get("conflict_state") or "none")[:30],
            )
            return custom({"data":result})

        denied=_governance_only(role)
        if denied:
            return denied

        if route=="/api/institution/member":
            result=syndication_network.bind_member(
                c,
                str(data.get("organization_id") or "")[:100],
                str(data.get("account_email") or "")[:240],
                str(data.get("member_role") or "")[:40],
                email,
                str(data.get("verification_ref") or "")[:500],
                data.get("expires_at"),
                bool(data.get("demo_only",False)),
            )
            return custom({"data":result},201)

        if route=="/api/syndication/qualification/start":
            result=syndication_network.start_qualification(
                c,
                str(data.get("organization_id") or "")[:100],
                email,
                int(data.get("validity_seconds") or 15552000),
                bool(data.get("demo_only",False)),
            )
            return custom({"data":result},201)

        if route=="/api/syndication/qualification/conformance":
            result=syndication_network.record_conformance(
                c,
                str(data.get("qualification_id") or "")[:120],
                str(data.get("scope_key") or "")[:80],
                str(data.get("status") or "")[:30],
                email,
                str(data.get("evidence_ref") or "")[:500],
                str(data.get("details") or "")[:1000],
                data.get("expires_at"),
            )
            return custom({"data":result})

        if route=="/api/syndication/qualification/finalize":
            result=syndication_network.finalize_qualification(
                c,
                str(data.get("qualification_id") or "")[:120],
                email,
                int(data.get("validity_seconds") or 15552000),
            )
            return custom({"data":result})

        if route=="/api/syndication/qualification/suspend":
            result=syndication_network.suspend_qualification(
                c,
                str(data.get("organization_id") or "")[:100],
                str(data.get("reason") or "")[:500],
                email,
            )
            return custom({"data":result})

        if route=="/api/syndication/qualification/revoke":
            result=syndication_network.revoke_qualification(
                c,
                str(data.get("organization_id") or "")[:100],
                str(data.get("reason") or "")[:500],
                email,
            )
            return custom({"data":result})

        if route=="/api/syndication/subscription":
            result=syndication_network.create_subscription(
                c,
                str(data.get("organization_id") or "")[:100],
                str(data.get("subscription_scope") or "")[:40],
                str(data.get("scope_ref") or "")[:160],
                email,
                int(data.get("update_sla_seconds") or 86400),
                int(data.get("withdrawal_sla_seconds") or 14400),
                data.get("expires_at"),
            )
            return custom({"data":result},201)

        result=syndication_network.admit_contribution(
            c,
            str(data.get("contribution_id") or "")[:120],
            email,
        )
        return custom({"data":result},201)
    except ValueError as exc:
        return error(str(exc),409)


def handle_public(route,data):
    if route!="/api/external-contribution/receipt/verify-portable":
        return None
    result=syndication_network.verify_contribution_receipt(
        data.get("receipt") or {},
        data.get("issuer_document") or {},
    )
    return {"data":result},200
