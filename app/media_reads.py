from urllib.parse import parse_qs, urlparse

from app import db, transcript_intelligence, evidence_graph, change_impact


def serve(raw_path, role):
    parsed=urlparse(raw_path)
    if parsed.path not in ("/api/transcript-intelligence","/api/evidence-graph","/api/evidence-coverage","/api/change-impact"):
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
        if parsed.path=="/api/change-impact":
            if role!="editor":
                return {"error":"forbidden"},403
            return change_impact.snapshot(c,(q.get("event_id") or [""])[0][:180] or None),200
        return evidence_graph.snapshot(
            c,
            artifact_kind=(q.get("artifact_kind") or [""])[0][:30] or None,
            artifact_ref=(q.get("artifact_ref") or [""])[0][:80] or None,
            claim_id=(q.get("claim_id") or [""])[0][:80] or None,
        ),200
    finally:
        c.close()
