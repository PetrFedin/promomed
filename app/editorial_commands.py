import time

from app.commanding import error, ok
from app.core import audit
from app import transcript_intelligence, evidence_graph, change_impact, evidence_monitor

ROUTES = {"/api/question", "/api/cms", "/api/transcript-takeaway-review", "/api/evidence-claim-correct", "/api/evidence-claim-retract", "/api/change-impact/create-demo", "/api/change-impact/resolve-demo", "/api/evidence-monitor/register", "/api/evidence-monitor/demo-change", "/api/evidence-monitor/fetch-live", "/api/evidence-monitor/review", "/api/evidence-monitor/admit"}


def handle_command(c, route, role, email, data):
    if route not in ROUTES:
        return None

    if route == "/api/question":
        if role != "participant":
            return error("forbidden", 403)
        text = str(data.get("text", "Как отличать корреляцию от причинности?"))[:500]
        c.execute("INSERT INTO questions(text,status,ts) VALUES(?,'review',?)", (text, int(time.time())))
        audit(c, "question_submitted", email, {})
        return ok()

    if route.startswith("/api/evidence-monitor/"):
        if role != "editor":
            return error("forbidden", 403)
        if route == "/api/evidence-monitor/register":
            provider=str(data.get("provider","crossref"))[:20].lower()
            external_id=str(data.get("external_id",""))[:180]
            try:
                target_id=evidence_monitor.ensure_target(c,provider,external_id,email,1)
            except ValueError as e:
                return error(str(e),422)
            audit(c,"evidence_watch_registered",email,{"target_id":target_id,"provider":provider})
            return ok()
        if route == "/api/evidence-monitor/demo-change":
            result=evidence_monitor.ingest_payload(
                c,"crossref","10.5555/promomed.demo.metabolic",
                evidence_monitor.DEMO_CROSSREF_RETRACTED,email,1
            )
            audit(c,"evidence_provider_snapshot",email,{"target_id":result["target_id"],"change_type":result["change_type"],"duplicate":result["duplicate"]})
            return ok()
        if route == "/api/evidence-monitor/fetch-live":
            provider=str(data.get("provider",""))[:20].lower()
            external_id=str(data.get("external_id",""))[:180]
            try:
                result=evidence_monitor.fetch_and_ingest(c,provider,external_id,email,email=email)
            except ValueError as e:
                return error(str(e),502 if str(e)=="provider_fetch_failed" else 422)
            audit(c,"evidence_provider_fetch",email,{"target_id":result["target_id"],"change_type":result["change_type"],"duplicate":result["duplicate"]})
            return ok()
        candidate_id=str(data.get("candidate_id",""))[:260]
        if not candidate_id:
            return error("candidate_id_required",422)
        if route == "/api/evidence-monitor/review":
            review_role=str(data.get("review_role",""))[:30]
            try:
                evidence_monitor.review_candidate(c,candidate_id,review_role,email,str(data.get("decision","accept_demo")),str(data.get("note","")))
            except ValueError as e:
                return error(str(e),409)
            audit(c,"evidence_admission_review",email,{"candidate_id":candidate_id,"review_role":review_role})
            return ok()
        try:
            admitted=evidence_monitor.admit_candidate(c,candidate_id,email)
        except ValueError as e:
            return error(str(e),409)
        audit(c,"evidence_admitted",email,{"candidate_id":candidate_id,"source_id":admitted["source_id"],"change_event_id":admitted["change_event_id"]})
        return ok()

    if route in ("/api/change-impact/create-demo", "/api/change-impact/resolve-demo"):
        if role != "editor":
            return error("forbidden", 403)
        if route == "/api/change-impact/create-demo":
            source_id = str(data.get("source_id", "ES01"))[:80].strip()
            event_type = str(data.get("event_type", "source_retracted"))[:60].strip()
            summary = str(data.get("summary", "DEMO: source status changed and dependent knowledge must be re-reviewed."))[:600]
            try:
                event_id = change_impact.analyze_source_change(c, source_id, event_type, summary, email)
            except ValueError as e:
                return error(str(e), 404 if str(e) == "source_not_found" else 422)
            audit(c, "knowledge_change_detected", email, {"event_id": event_id, "source_id": source_id, "event_type": event_type})
            return ok()
        event_id = str(data.get("event_id", ""))[:180].strip()
        if not event_id:
            return error("event_id_required", 422)
        try:
            change_impact.resolve_case(c, event_id, str(data.get("resolution", "Reviewed in demo.")), email, bool(data.get("release_holds")))
        except ValueError as e:
            return error(str(e), 409)
        audit(c, "knowledge_change_resolved", email, {"event_id": event_id, "release_holds": bool(data.get("release_holds"))})
        return ok()

    if route in ("/api/evidence-claim-correct", "/api/evidence-claim-retract"):
        if role != "editor":
            return error("forbidden", 403)
        claim_id = str(data.get("claim_id", ""))[:80].strip()
        if not claim_id:
            return error("claim_id_required", 422)
        try:
            if route == "/api/evidence-claim-correct":
                new_text = str(data.get("claim_text", "")).strip()
                if not new_text:
                    return error("claim_text_required", 422)
                new_id = evidence_graph.correct_demo_claim(c, claim_id, new_text, email)
                audit(c, "evidence_claim_corrected", email, {"claim_id": claim_id, "new_claim_id": new_id})
            else:
                evidence_graph.retract_demo_claim(c, claim_id, str(data.get("note", "")), email)
                audit(c, "evidence_claim_retracted", email, {"claim_id": claim_id})
        except ValueError as e:
            return error(str(e), 404 if str(e) == "claim_not_found" else 409)
        return ok()

    if route == "/api/transcript-takeaway-review":
        if role != "editor":
            return error("forbidden", 403)
        takeaway_id = str(data.get("takeaway_id", ""))[:80].strip()
        action = str(data.get("action", "approve_demo"))
        try:
            transcript_intelligence.review_takeaway(c, takeaway_id, action, email)
        except ValueError as e:
            return error(str(e), 404 if str(e) == "takeaway_not_found" else 400)
        audit(c, "transcript_takeaway_reviewed", email, {"takeaway_id": takeaway_id, "action": action})
        return ok()

    if role != "editor":
        return error("forbidden", 403)
    status = str(data.get("status", "approved"))
    c.execute(
        "UPDATE cms SET status=?,version=version+1,updated=? WHERE id='A-014'",
        (status, int(time.time())),
    )
    audit(c, "cms_status", email, {"status": status})
    return ok()
