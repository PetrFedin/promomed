from app.commanding import custom, error
from app import trust_bundle


ROUTES={
    "/api/trust/snapshot/issue",
    "/api/trust/snapshot/revoke",
    "/api/trust/status/issue",
    "/api/trust/bundle/create",
    "/api/trust/verification/record",
}


def handle_command(c,route,role,email,data):
    if route not in ROUTES:
        return None
    try:
        if route=="/api/trust/verification/record":
            result=trust_bundle.record_cross_organization_verification(
                c,
                str(data.get("bundle_id") or "")[:120],
                str(data.get("verifier_organization_id") or "")[:100],
                email,
                current_status_statement=data.get("current_status_statement"),
                current_issuer_document=data.get("current_issuer_document"),
            )
            return custom({"data":result},201 if not result.get("idempotentReplay") else 200)

        if role!="governance":
            return error("forbidden",403)

        if route=="/api/trust/snapshot/issue":
            result=trust_bundle.issue_snapshot(
                c,
                str(data.get("organization_id") or "")[:100],
                email,
                int(data.get("validity_seconds") or trust_bundle.DEFAULT_SNAPSHOT_VALIDITY),
            )
            return custom({"data":result},201 if not result.get("idempotentReplay") else 200)

        if route=="/api/trust/snapshot/revoke":
            result=trust_bundle.revoke_snapshot(
                c,
                str(data.get("snapshot_id") or "")[:120],
                str(data.get("reason") or "")[:500],
                email,
            )
            return custom({"data":result})

        if route=="/api/trust/status/issue":
            result=trust_bundle.signed_status_statement(
                c,
                str(data.get("organization_id") or "")[:100],
                email,
                int(data.get("validity_seconds") or trust_bundle.DEFAULT_STATUS_VALIDITY),
            )
            return custom({"data":result},201)

        result=trust_bundle.create_trust_bundle(
            c,
            str(data.get("snapshot_id") or "")[:120],
            email,
        )
        return custom({"data":result},201 if not result.get("idempotentReplay") else 200)
    except ValueError as exc:
        return error(str(exc),409)


def handle_public(route,data):
    if route!="/api/trust/verify-portable":
        return None
    result=trust_bundle.verify_bundle_portable(
        data.get("bundle") or {},
        current_status_statement=data.get("current_status_statement"),
        current_issuer_document=data.get("current_issuer_document"),
    )
    return {"data":result},200
