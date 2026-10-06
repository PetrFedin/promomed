import hashlib
import json

from app import evidence_graph


SEAL_VERSION = "promomed-evidence-seal-v2"


def _canonical_sha256(value):
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build(c, *, artifact_kind, artifact_ref):
    if not artifact_kind or not artifact_ref:
        raise ValueError("artifact_required")

    graph = evidence_graph.snapshot(
        c,
        artifact_kind=artifact_kind,
        artifact_ref=artifact_ref,
    )
    claims = graph.get("claims") or []
    current = [
        claim
        for claim in claims
        if (claim.get("trust") or {}).get("status") not in ("SUPERSEDED", "RETRACTED")
    ]
    trusted = [claim for claim in current if (claim.get("trust") or {}).get("trusted")]

    if not current:
        state = "NO_CURRENT_CLAIMS"
    elif len(trusted) != len(current):
        state = "INCOMPLETE"
    elif graph.get("truth_boundary", {}).get("external_publication_verified"):
        state = "VERIFIED_PROCESS"
    else:
        state = "VERIFIED_DEMO_PROCESS"

    canonical = {
        "sealVersion": SEAL_VERSION,
        "artifact": {"kind": artifact_kind, "ref": artifact_ref},
        "claimGraphVersion": graph.get("version"),
        "state": state,
        "counts": {
            "currentClaims": len(current),
            "trustedCurrentClaims": len(trusted),
            "historicalClaims": len(claims) - len(current),
        },
        "currentClaims": [
            {
                "id": claim.get("id"),
                "version": claim.get("version"),
                "status": (claim.get("trust") or {}).get("status"),
                "trusted": bool((claim.get("trust") or {}).get("trusted")),
                "reviewer": claim.get("reviewer"),
                "reviewedAt": claim.get("reviewed_at"),
                "citations": [
                    {
                        "id": citation.get("id"),
                        "sourceId": citation.get("source_id"),
                        "status": citation.get("status"),
                        "locator": citation.get("locator"),
                        "supportType": citation.get("support_type"),
                        "sourceRef": citation.get("source_ref"),
                        "disclosure": citation.get("disclosure"),
                    }
                    for citation in claim.get("citations") or []
                ],
                "links": [
                    {
                        "id": link.get("id"),
                        "targetKind": link.get("target_kind"),
                        "targetRef": link.get("target_ref"),
                        "relation": link.get("relation"),
                        "startSec": link.get("start_sec"),
                        "endSec": link.get("end_sec"),
                    }
                    for link in claim.get("links") or []
                ],
            }
            for claim in current
        ],
        "truthBoundary": graph.get("truth_boundary") or {},
        "rules": {
            "gate": "Every current claim must satisfy the canonical Claim Evidence Graph trust rule.",
            "demoBoundary": "VERIFIED_DEMO_PROCESS proves workflow provenance over demo sources; it is not medical efficacy certification.",
            "mutableScoreUsed": False,
        },
    }
    return {
        **canonical,
        "evidencePackageSha256": _canonical_sha256(canonical),
        "validForProcess": state in ("VERIFIED_DEMO_PROCESS", "VERIFIED_PROCESS"),
        "medicalEfficacyCertified": False,
    }
