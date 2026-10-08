from urllib.parse import parse_qs, urlparse

from app import db, delivery_protocol, federated_trust, federation_interop, pilot_workspace, institutional_onboarding, institutional_data_room, transcript_intelligence, evidence_graph, change_impact, evidence_monitor, reviewer_authority, evidence_seal, evidence_checkpoint, evidence_interchange, syndication_network, trust_bundle


PUBLIC_EVIDENCE_ROUTES=(
    "/api/evidence-checkpoint/public-key",
    "/api/evidence-checkpoint/issuer",
    "/api/evidence-checkpoint/status-list",
    "/api/evidence-checkpoint/checkpoint",
)


def serve(raw_path, role):
    parsed=urlparse(raw_path)
    dynamic_federated_public=(
        parsed.path.startswith("/trust/")
        and (parsed.path.endswith("/did.json") or parsed.path.endswith("/jwks.json"))
    )
    if not dynamic_federated_public and parsed.path not in (
        "/api/transcript-intelligence",
        "/api/evidence-graph",
        "/api/evidence-coverage",
        "/api/change-impact",
        "/api/evidence-monitor",
        "/api/reviewer-authority",
        "/api/evidence-seal",
        "/api/evidence-bundle",
        "/api/evidence-interchange/package",
        "/api/evidence-interchange/reference",
        "/api/institutional-network",
        "/api/syndication-network",
        "/api/syndication/delivery-runtime",
        "/api/syndication/certification",
        "/api/external-contribution/receipt",
        "/api/trust/snapshot",
        "/api/trust/bundle",
        "/api/trust-network",
        "/api/federation",
        "/api/federation/receipt",
        "/.well-known/promomed-federation.json",
        "/api/federation/profile",
        "/api/federation/discovery",
        "/api/federation/discovery-bundle",
        "/api/institutional-pilot-readiness",
        "/api/institutional-onboarding-room",
        "/api/institutional-data-room",
        *PUBLIC_EVIDENCE_ROUTES,
    ):
        return None

    q=parse_qs(parsed.query)
    c=db.connect()
    try:
        if parsed.path=="/api/evidence-checkpoint/public-key":
            try:
                return {"data":evidence_checkpoint.public_key_document(c)},200
            except ValueError as exc:
                return {"error":str(exc)},503

        if parsed.path=="/api/evidence-checkpoint/issuer":
            issuer_id=(q.get("issuer_id") or [""])[0][:120] or None
            return {"data":evidence_checkpoint.issuer_document(c,issuer_id)},200

        if parsed.path=="/api/evidence-checkpoint/status-list":
            issuer_id=(q.get("issuer_id") or [""])[0][:120] or None
            return {"data":evidence_checkpoint.status_list(c,issuer_id)},200

        if parsed.path=="/api/evidence-checkpoint/checkpoint":
            checkpoint_sha=(q.get("sha256") or [""])[0][:64]
            try:
                return {"data":evidence_checkpoint.checkpoint_document(c,checkpoint_sha)},200
            except ValueError as exc:
                return {"error":str(exc)},404 if str(exc)=="checkpoint_not_found" else 422

        if parsed.path=="/api/evidence-interchange/reference":
            return {"data":evidence_interchange.reference_package()},200

        if parsed.path=="/api/evidence-interchange/package":
            package_id=(q.get("id") or [""])[0][:100]
            if not package_id:
                return {"error":"package_id_required"},422
            try:
                return {"data":evidence_interchange.package_document(c,package_id)},200
            except ValueError as exc:
                return {"error":str(exc)},404 if str(exc)=="evidence_package_not_found" else 422

        if parsed.path.startswith("/trust/") and parsed.path.endswith("/did.json"):
            from urllib.parse import unquote
            organization_id=unquote(parsed.path[len("/trust/"):-len("/did.json")]).strip("/")
            if not organization_id:
                return {"error":"organization_id_required"},422
            try:
                return {"data":federated_trust.did_document(c,organization_id)},200
            except ValueError as exc:
                return {"error":str(exc)},404

        if parsed.path.startswith("/trust/") and parsed.path.endswith("/jwks.json"):
            from urllib.parse import unquote
            organization_id=unquote(parsed.path[len("/trust/"):-len("/jwks.json")]).strip("/")
            if not organization_id:
                return {"error":"organization_id_required"},422
            try:
                return federated_trust.jwks_document(c,organization_id),200
            except ValueError as exc:
                return {"error":str(exc)},404

        if parsed.path=="/.well-known/promomed-federation.json":
            return federation_interop.discovery_manifest(c),200

        if parsed.path=="/api/federation/profile":
            return {"data":federation_interop.public_profile(c)},200

        if parsed.path=="/api/federation/discovery":
            organization_id=(q.get("organization_id") or [""])[0][:100]
            if not organization_id:
                return {"error":"organization_id_required"},422
            try:
                return {
                    "data":{
                        "profile":federation_interop.public_profile(c),
                        "organizationId":organization_id,
                        "anchors":federation_interop.anchor_directory(c,organization_id),
                        "did":federated_trust.did_document(c,organization_id),
                        "jwks":federated_trust.jwks_document(c,organization_id),
                    }
                },200
            except ValueError as exc:
                return {"error":str(exc)},404

        if parsed.path=="/api/federation/discovery-bundle":
            bundle_id=(q.get("id") or [""])[0][:160]
            if not bundle_id:
                return {"error":"bundle_id_required"},422
            try:
                return {"data":federation_interop.discovery_bundle_document(c,bundle_id)},200
            except ValueError as exc:
                return {"error":str(exc)},404

        if parsed.path=="/api/federation/receipt":
            receipt_id=(q.get("id") or [""])[0][:160]
            if not receipt_id:
                return {"error":"receipt_id_required"},422
            try:
                return {"data":federated_trust.signed_receipt_document(c,receipt_id)},200
            except ValueError as exc:
                return {"error":str(exc)},404

        if parsed.path=="/api/institutional-data-room":
            if role not in ("governance","editor","sales"):
                return {"error":"forbidden"},403
            organization_id=(q.get("organization_id") or [""])[0][:100]
            if not organization_id:
                return {"error":"organization_id_required"},422
            try:
                return {"data":institutional_data_room.snapshot(c,organization_id)},200
            except ValueError as exc:
                return {"error":str(exc)},404 if str(exc)=="organization_not_found" else 422

        if parsed.path=="/api/institutional-onboarding-room":
            if role not in ("governance","editor","sales"):
                return {"error":"forbidden"},403
            organization_id=(q.get("organization_id") or [""])[0][:100]
            if not organization_id:
                return {"error":"organization_id_required"},422
            try:
                return {"data":institutional_onboarding.snapshot(c,organization_id)},200
            except ValueError as exc:
                return {"error":str(exc)},404 if str(exc)=="organization_not_found" else 422

        if parsed.path=="/api/institutional-pilot-readiness":
            if role not in ("governance","editor","sales"):
                return {"error":"forbidden"},403
            organization_id=(q.get("organization_id") or [""])[0][:100]
            if not organization_id:
                return {"error":"organization_id_required"},422
            try:
                return {"data":pilot_workspace.snapshot(c,organization_id)},200
            except ValueError as exc:
                return {"error":str(exc)},404 if str(exc)=="organization_not_found" else 422

        if parsed.path=="/api/federation":
            if role not in ("governance","editor","sales"):
                return {"error":"forbidden"},403
            organization_id=(q.get("organization_id") or [""])[0][:100] or None
            try:
                return {"data":federated_trust.federation_snapshot(c,organization_id)},200
            except ValueError as exc:
                return {"error":str(exc)},404

        if parsed.path=="/api/trust/snapshot":
            snapshot_id=(q.get("id") or [""])[0][:120]
            if not snapshot_id:
                return {"error":"snapshot_id_required"},422
            try:
                return {"data":trust_bundle.snapshot_document(c,snapshot_id)},200
            except ValueError as exc:
                return {"error":str(exc)},404

        if parsed.path=="/api/trust/bundle":
            bundle_id=(q.get("id") or [""])[0][:120]
            if not bundle_id:
                return {"error":"bundle_id_required"},422
            try:
                return {"data":trust_bundle.bundle_document(c,bundle_id)},200
            except ValueError as exc:
                return {"error":str(exc)},404

        if parsed.path=="/api/trust-network":
            if role not in ("governance","editor","sales"):
                return {"error":"forbidden"},403
            organization_id=(q.get("organization_id") or [""])[0][:100] or None
            try:
                return {"data":trust_bundle.trust_snapshot(c,organization_id)},200
            except ValueError as exc:
                return {"error":str(exc)},404

        if parsed.path=="/api/syndication/delivery-runtime":
            if role not in ("governance","editor","sales"):
                return {"error":"forbidden"},403
            organization_id=(q.get("organization_id") or [""])[0][:100] or None
            try:
                return {"data":delivery_protocol.runtime_snapshot(c,organization_id)},200
            except ValueError as exc:
                return {"error":str(exc)},404

        if parsed.path=="/api/syndication/certification":
            organization_id=(q.get("organization_id") or [""])[0][:100]
            if not organization_id:
                return {"error":"organization_id_required"},422
            try:
                return {"data":syndication_network.public_certification(c,organization_id)},200
            except ValueError as exc:
                return {"error":str(exc)},404

        if parsed.path=="/api/external-contribution/receipt":
            contribution_id=(q.get("contribution_id") or [""])[0][:120]
            if not contribution_id:
                return {"error":"contribution_id_required"},422
            try:
                return {"data":syndication_network.contribution_receipt(c,contribution_id)},200
            except ValueError as exc:
                return {"error":str(exc)},404

        if parsed.path=="/api/syndication-network":
            if role not in ("governance","editor","sales","reviewer"):
                return {"error":"forbidden"},403
            organization_id=(q.get("organization_id") or [""])[0][:100] or None
            return {"data":syndication_network.network_snapshot(c,organization_id)},200

        if parsed.path=="/api/institutional-network":
            if role not in ("governance","editor","sales"):
                return {"error":"forbidden"},403
            organization_id=(q.get("organization_id") or [""])[0][:100] or None
            try:
                return {"data":evidence_interchange.institutional_snapshot(c,organization_id)},200
            except ValueError as exc:
                return {"error":str(exc)},404

        if parsed.path in ("/api/evidence-seal","/api/evidence-bundle"):
            kind=(q.get("artifact_kind") or [""])[0][:30]
            ref=(q.get("artifact_ref") or [""])[0][:80]
            if not kind or not ref:
                return {"error":"artifact_required"},422
            data=evidence_seal.build(c,artifact_kind=kind,artifact_ref=ref) if parsed.path=="/api/evidence-seal" else evidence_seal.portable_bundle(c,artifact_kind=kind,artifact_ref=ref)
            return {"data":data},200

        if parsed.path=="/api/transcript-intelligence":
            item=(q.get("item_id") or [""])[0][:40] or None
            return transcript_intelligence.snapshot(c,item_id=item,editor=role=="editor"),200

        if parsed.path=="/api/evidence-coverage":
            if role!="editor":
                return {"error":"forbidden"},403
            return evidence_graph.coverage(c),200

        if parsed.path=="/api/change-impact":
            if role!="editor":
                return {"error":"forbidden"},403
            return change_impact.snapshot(c,(q.get("event_id") or [""])[0][:180] or None),200

        if parsed.path=="/api/evidence-monitor":
            if role not in ("editor","reviewer","governance"):
                return {"error":"forbidden"},403
            return evidence_monitor.snapshot(c),200

        if parsed.path=="/api/reviewer-authority":
            if role not in ("editor","reviewer","governance"):
                return {"error":"forbidden"},403
            return reviewer_authority.snapshot(c),200

        return evidence_graph.snapshot(
            c,
            artifact_kind=(q.get("artifact_kind") or [""])[0][:30] or None,
            artifact_ref=(q.get("artifact_ref") or [""])[0][:80] or None,
            claim_id=(q.get("claim_id") or [""])[0][:80] or None,
        ),200
    finally:
        c.close()
