from app.commanding import custom, error
from app import federated_trust, trust_bundle


ROUTES={
    "/api/trust/snapshot/issue",
    "/api/trust/snapshot/revoke",
    "/api/trust/status/issue",
    "/api/trust/bundle/create",
    "/api/trust/verification/record",
    "/api/federation/anchor/propose",
    "/api/federation/anchor/prove",
    "/api/federation/anchor/activate",
    "/api/federation/anchor/suspend",
    "/api/federation/anchor/revoke",
    "/api/federation/anchor/status/issue",
    "/api/federation/receipt/submit",
}


def handle_command(c,route,role,email,data):
    if route not in ROUTES:
        return None
    try:
        if route=="/api/federation/anchor/propose":
            result=federated_trust.propose_anchor(
                c,
                str(data.get("organization_id") or "")[:100],
                str(data.get("issuer_id") or "")[:240],
                str(data.get("key_id") or "")[:160],
                str(data.get("public_key_b64") or "")[:200],
                email,
                source_ref=str(data.get("source_ref") or "")[:500],
                metadata=data.get("metadata") or {},
                rotated_from_anchor_id=(str(data.get("rotated_from_anchor_id") or "")[:120] or None),
                demo_only=bool(data.get("demo_only",False)),
            )
            return custom({"data":result},201 if not result.get("idempotentReplay") else 200)

        if route=="/api/federation/anchor/prove":
            result=federated_trust.verify_anchor_proof(
                c,
                str(data.get("anchor_id") or "")[:120],
                str(data.get("signature") or "")[:200],
                email,
            )
            return custom({"data":result})

        if route=="/api/federation/receipt/submit":
            result=federated_trust.submit_signed_verification_receipt(
                c,
                str(data.get("bundle_id") or "")[:120],
                str(data.get("verifier_organization_id") or "")[:100],
                str(data.get("anchor_id") or "")[:120],
                data.get("receipt_body") or {},
                str(data.get("signature") or "")[:200],
                email,
            )
            return custom({"data":result},201 if not result.get("idempotentReplay") else 200)

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

        if route=="/api/federation/anchor/activate":
            result=federated_trust.activate_anchor(
                c,
                str(data.get("anchor_id") or "")[:120],
                email,
                validity_seconds=data.get("validity_seconds"),
            )
            return custom({"data":result})

        if route=="/api/federation/anchor/suspend":
            result=federated_trust.suspend_anchor(
                c,
                str(data.get("anchor_id") or "")[:120],
                str(data.get("reason") or "")[:500],
                email,
            )
            return custom({"data":result})

        if route=="/api/federation/anchor/revoke":
            result=federated_trust.revoke_anchor(
                c,
                str(data.get("anchor_id") or "")[:120],
                str(data.get("reason") or "")[:500],
                email,
            )
            return custom({"data":result})

        if route=="/api/federation/anchor/status/issue":
            result=federated_trust.signed_anchor_status(
                c,
                str(data.get("organization_id") or "")[:100],
                email,
                int(data.get("validity_seconds") or 86400),
            )
            return custom({"data":result},201)

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
    if route=="/api/federation/receipt/verify-portable":
        result=federated_trust.verify_signed_receipt_portable(
            data.get("receipt") or {},
            data.get("bundle") or {},
            data.get("anchor_status_statement") or {},
            data.get("promomed_issuer_document") or {},
        )
        return {"data":result},200
    if route!="/api/trust/verify-portable":
        return None
    result=trust_bundle.verify_bundle_portable(
        data.get("bundle") or {},
        current_status_statement=data.get("current_status_statement"),
        current_issuer_document=data.get("current_issuer_document"),
    )
    return {"data":result},200
