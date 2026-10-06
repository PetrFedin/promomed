from urllib.parse import parse_qs, urlparse

from app import db, transcript_intelligence, evidence_graph, evidence_seal


def serve(raw_path, role):
    parsed=urlparse(raw_path)
    if parsed.path not in ("/api/transcript-intelligence","/api/evidence-graph","/api/evidence-coverage","/api/evidence-seal","/api/evidence-bundle"):
        return None
    q=parse_qs(parsed.query)
    c=db.connect()
    try:
        if parsed.path=="/api/transcript-intelligence":
            item=(q.get("item_id") or [""])[0][:40] or None
            return transcript_intelligence.snapshot(c,item_id=item,editor=role=="editor"),200
        if parsed.path=="/api/evidence-coverage":
            if role!="editor":
                return {"error":"forbidden"},403
            return evidence_graph.coverage(c),200
        if parsed.path=="/api/evidence-seal":
            artifact_kind=(q.get("artifact_kind") or [""])[0][:30]
            artifact_ref=(q.get("artifact_ref") or [""])[0][:80]
            if not artifact_kind or not artifact_ref:
                return {"error":"artifact_required"},422
            return evidence_seal.build(c,artifact_kind=artifact_kind,artifact_ref=artifact_ref),200
        if parsed.path=="/api/evidence-bundle":
            artifact_kind=(q.get("artifact_kind") or [""])[0][:30]
            artifact_ref=(q.get("artifact_ref") or [""])[0][:80]
            if not artifact_kind or not artifact_ref:
                return {"error":"artifact_required"},422
            return evidence_seal.portable_bundle(c,artifact_kind=artifact_kind,artifact_ref=artifact_ref),200
        return evidence_graph.snapshot(
            c,
            artifact_kind=(q.get("artifact_kind") or [""])[0][:30] or None,
            artifact_ref=(q.get("artifact_ref") or [""])[0][:80] or None,
            claim_id=(q.get("claim_id") or [""])[0][:80] or None,
        ),200
    finally:
        c.close()
