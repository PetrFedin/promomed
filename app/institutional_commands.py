from app.commanding import custom, error
from app import evidence_interchange


ROUTES={
    "/api/institution/register",
    "/api/institution/role",
    "/api/evidence-interchange/package/create",
    "/api/evidence-interchange/package/deliver",
    "/api/evidence-interchange/package/acknowledge",
    "/api/evidence-interchange/package/withdraw",
}


def handle_command(c,route,role,email,data):
    if route not in ROUTES:
        return None

    if role!="governance":
        return error("forbidden",403)

    try:
        if route=="/api/institution/register":
            result=evidence_interchange.register_organization(
                c,
                organization_id=str(data.get("organization_id") or "")[:100],
                name=str(data.get("name") or "")[:240],
                organization_type=str(data.get("organization_type") or "")[:80],
                actor=email,
                external_ref=str(data.get("external_ref") or "")[:400],
                credential_source=str(data.get("credential_source") or "")[:400],
                partner_id=(str(data.get("partner_id") or "")[:80] or None),
                demo_only=bool(data.get("demo_only",False)),
            )
            return custom({"data":result},201)

        if route=="/api/institution/role":
            result=evidence_interchange.bind_role(
                c,
                organization_id=str(data.get("organization_id") or "")[:100],
                role_scope=str(data.get("role_scope") or "")[:40],
                actor=email,
                verification_ref=str(data.get("verification_ref") or "")[:500],
                effective_at=data.get("effective_at"),
                expires_at=data.get("expires_at"),
                demo_only=bool(data.get("demo_only",False)),
            )
            return custom({"data":result})

        if route=="/api/evidence-interchange/package/create":
            kind=str(data.get("artifact_kind") or "")[:30]
            ref=str(data.get("artifact_ref") or "")[:80]
            if not kind or not ref:
                return error("artifact_required",422)
            result=evidence_interchange.create_package(
                c,
                artifact_kind=kind,
                artifact_ref=ref,
                actor=email,
                checkpoint_sha256=(str(data.get("checkpoint_sha256") or "")[:64] or None),
            )
            return custom({"data":result},201)

        if route=="/api/evidence-interchange/package/deliver":
            result=evidence_interchange.deliver_package(
                c,
                package_id=str(data.get("package_id") or "")[:100],
                organization_id=str(data.get("organization_id") or "")[:100],
                actor=email,
                delivery_role=str(data.get("delivery_role") or "consumer")[:30],
            )
            return custom({"data":result},201)

        if route=="/api/evidence-interchange/package/acknowledge":
            result=evidence_interchange.acknowledge_delivery(
                c,
                str(data.get("delivery_id") or "")[:100],
                str(data.get("organization_id") or "")[:100],
            )
            return custom({"data":result})

        kind=str(data.get("artifact_kind") or "")[:30]
        ref=str(data.get("artifact_ref") or "")[:80]
        if not kind or not ref:
            return error("artifact_required",422)
        result=evidence_interchange.withdraw_artifact_packages(
            c,kind,ref,str(data.get("reason") or "Governance withdrawal"),email
        )
        return custom({"data":result})
    except ValueError as exc:
        return error(str(exc),409)


def handle_public(route,data):
    if route!="/api/evidence-interchange/verify-portable":
        return None
    result=evidence_interchange.verify_package_portable(
        data.get("package") or {},
        data.get("issuer_document") or {},
        data.get("status_list") or {},
    )
    return {"data":result},200
