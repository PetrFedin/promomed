from urllib.parse import parse_qs, urlparse

from app import db, transcript_intelligence, evidence_graph, change_impact, evidence_monitor, reviewer_authority, evidence_seal, evidence_checkpoint


def serve(raw_path, role):
    parsed=urlparse(raw_path)
    if parsed.path not in ("/api/transcript-intelligence","/api/evidence-graph","/api/evidence-coverage","/api/change-impact","/api/evidence-monitor","/api/reviewer-authority","/api/evidence-seal","/api/evidence-bundle","/api/evidence-checkpoint/public-key"):
        return None
    q=parse_qs(parsed.query)
    if parsed.path=="/api/evidence-checkpoint/public-key":
        try:
            return {"data":evidence_checkpoint.public_key_document()},200
        except ValueError as exc:
            return {"error":str(exc)},503
    c=db.connect()
    try:
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
