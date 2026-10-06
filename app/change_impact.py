import time

from app import evidence_graph


SEVERITY_ORDER={"low":1,"medium":2,"high":3,"critical":4}
EVENT_SEVERITY={
    "source_updated":"medium",
    "new_systematic_review":"high",
    "source_corrected":"high",
    "source_retracted":"critical",
    "medical_status_changed":"critical",
    "editorial_status_changed":"high",
}
SLA_SECONDS={"low":7*86400,"medium":3*86400,"high":24*3600,"critical":4*3600}


def _owner_for(kind):
    if kind in ("content","takeaway","learning","recommendation"):
        return "Editorial Director"
    if kind in ("product","partner"):
        return "Medical / Legal Review"
    if kind in ("transcript","replay","event","expert"):
        return "Studio / Programme Editor"
    return "Knowledge Governance"


def _severity(base,kind):
    score=SEVERITY_ORDER.get(base,2)
    if kind in ("product","recommendation") and score>=3:
        score=min(4,score+1)
    return {v:k for k,v in SEVERITY_ORDER.items()}[score]


def _audience_count(c,kind,ref,topic=""):
    if kind=="content":
        try:
            return int(c.execute("SELECT COUNT(*) n FROM discovery_saves WHERE target_kind='content' AND target_ref=?",(ref,)).fetchone()["n"])
        except Exception:
            return 0
    if kind=="learning":
        try:
            return int(c.execute("SELECT COUNT(*) n FROM learning_enrollments WHERE track_id=? AND status IN ('active','completed')",(ref,)).fetchone()["n"])
        except Exception:
            return 0
    if kind=="recommendation":
        try:
            return int(c.execute("SELECT COUNT(DISTINCT email) n FROM discovery_saves WHERE topic LIKE ?",(f"%{topic}%",)).fetchone()["n"])
        except Exception:
            return 0
    return 0


def _related_targets(c,claim):
    topic=str(claim.get("topic") or "")
    targets={(claim["artifact_kind"],claim["artifact_ref"],"claim_artifact")}

    links=evidence_graph._links(c,claim["id"])
    related_items=set()
    for link in links:
        targets.add((link["target_kind"],link["target_ref"],link["relation"]))
        if link["target_kind"] in ("event","replay"):
            related_items.add(link["target_ref"])
        if link["target_kind"]=="transcript":
            seg=c.execute("SELECT item_id,start_sec,end_sec FROM transcript_segments WHERE id=?",(link["target_ref"],)).fetchone()
            if seg:
                related_items.add(seg["item_id"])
                for take in c.execute(
                    "SELECT id FROM generated_takeaways WHERE item_id=? AND status IN ('approved','approved_demo') AND segment_start_sec < ? AND segment_end_sec > ?",
                    (seg["item_id"],seg["end_sec"],seg["start_sec"]),
                ):
                    targets.add(("takeaway",take["id"],"derived_from_impacted_segment"))
    for item_id in related_items:
        for ep in c.execute("SELECT id FROM studio_episodes WHERE item_id=?",(item_id,)):
            targets.add(("studio",ep["id"],"programme_dependency"))

    # Learning tracks with matching topic become review targets.
    if topic:
        for row in c.execute("SELECT id,topic FROM learning_tracks"):
            t=str(row["topic"] or "")
            if topic.lower() in t.lower() or t.lower() in topic.lower():
                targets.add(("learning",row["id"],"topic_dependency"))

        for row in c.execute("SELECT id,theme FROM product_catalog"):
            t=str(row["theme"] or "")
            if topic.lower() in t.lower() or t.lower() in topic.lower():
                targets.add(("product",row["id"],"topic_dependency"))

        for row in c.execute("SELECT id,category FROM partners"):
            t=str(row["category"] or "")
            if t and (t.lower() in topic.lower() or topic.lower() in t.lower()):
                targets.add(("partner",row["id"],"topic_dependency"))

        # Recommendation projection is represented as a derived target, not a writable user record.
        targets.add(("recommendation",f"topic:{topic}","personalization_dependency"))

    return sorted(targets)


def analyze_source_change(c,source_id,event_type,summary,actor):
    source=c.execute("SELECT id,status FROM evidence_sources WHERE id=?",(source_id,)).fetchone()
    if not source:
        raise ValueError("source_not_found")
    if event_type not in EVENT_SEVERITY:
        raise ValueError("unsupported_event_type")

    now=int(time.time())
    event_id=f"chg:{source_id}:{event_type}:{time.time_ns()}"
    base=EVENT_SEVERITY[event_type]
    if event_type in ("source_updated","source_corrected","source_retracted"):
        c.execute("UPDATE evidence_sources SET status=? WHERE id=?", (event_type+"_demo",source_id))
    c.execute(
        "INSERT INTO knowledge_change_events(id,source_id,event_type,summary,severity_hint,status,detected_at,created_by,demo_only) VALUES(?,?,?,?,?,'open',?,?,1)",
        (event_id,source_id,event_type,str(summary or "")[:600],base,now,actor),
    )

    claim_rows=[dict(r) for r in c.execute(
        "SELECT DISTINCT cl.id,cl.artifact_kind,cl.artifact_ref,cl.claim_text,cl.topic,cl.status,cl.version,cl.reviewer,cl.reviewed_at,cl.supersedes_claim_id,cl.correction_note "
        "FROM evidence_claims cl JOIN evidence_citations ec ON ec.claim_id=cl.id "
        "WHERE ec.source_id=? AND ec.status='active'",
        (source_id,),
    )]
    for claim in claim_rows:
        if claim["status"] in ("reviewed","reviewed_demo"):
            c.execute("UPDATE evidence_claims SET status='review_required_demo',correction_note=? WHERE id=?",
                      (f"Evidence source {source_id} changed: {event_type}",claim["id"]))
            claim["status"]="review_required_demo"

    impact_count=0
    hold_artifacts=set()
    max_severity=base
    for claim in claim_rows:
        # Historical claims remain traceable but do not generate new publication holds.
        if str(claim["status"]).startswith(("superseded","retracted")):
            continue
        for kind,ref,reason in _related_targets(c,claim):
            sev=_severity(base,kind)
            max_severity=max((max_severity,sev),key=lambda x:SEVERITY_ORDER[x])
            deadline=now+SLA_SECONDS[sev]
            iid=f"{event_id}:{claim['id']}:{kind}:{ref}"
            audience=_audience_count(c,kind,ref,claim.get("topic") or "")
            c.execute(
                "INSERT OR IGNORE INTO knowledge_impacts(id,event_id,claim_id,target_kind,target_ref,impact_reason,severity,owner,deadline_at,status,audience_count,demo_only) "
                "VALUES(?,?,?,?,?,?,?,?,?,'review_required',?,1)",
                (iid,event_id,claim["id"],kind,ref,reason,sev,_owner_for(kind),deadline,audience),
            )
            impact_count+=1
            if sev in ("high","critical") and kind in ("content","takeaway","learning","product","partner","recommendation"):
                hold_artifacts.add((kind,ref,sev,claim["id"]))

    for kind,ref,sev,claim_id in hold_artifacts:
        hid=f"hold:{event_id}:{kind}:{ref}"
        c.execute(
            "INSERT OR IGNORE INTO publication_holds(id,event_id,artifact_kind,artifact_ref,reason,status,placed_at,placed_by,demo_only) "
            "VALUES(?,?,?,?,?,'active',?,?,1)",
            (hid,event_id,kind,ref,f"{event_type} affects claim {claim_id}",now,"Change Impact Engine"),
        )

    case_id=f"review:{event_id}"
    deadline=now+SLA_SECONDS[max_severity]
    c.execute(
        "INSERT INTO knowledge_review_cases(id,event_id,owner,severity,status,deadline_at,resolution,demo_only) VALUES(?,?,?,?,'open',?,'',1)",
        (case_id,event_id,"Knowledge Governance",max_severity,deadline),
    )
    return event_id


def _rows(c,table,where="",params=()):
    try:
        return [dict(r) for r in c.execute(f"SELECT * FROM {table} {where}",params)]
    except Exception:
        return []


def snapshot(c,event_id=None):
    ew="WHERE id=?" if event_id else ""
    events=_rows(c,"knowledge_change_events",ew,(event_id,) if event_id else ())
    impacts=_rows(c,"knowledge_impacts","WHERE event_id=? ORDER BY severity DESC,target_kind,target_ref",(event_id,)) if event_id else _rows(c,"knowledge_impacts","ORDER BY deadline_at,severity DESC")
    holds=_rows(c,"publication_holds","WHERE event_id=? ORDER BY artifact_kind,artifact_ref",(event_id,)) if event_id else _rows(c,"publication_holds","ORDER BY placed_at DESC")
    cases=_rows(c,"knowledge_review_cases","WHERE event_id=? ORDER BY deadline_at",(event_id,)) if event_id else _rows(c,"knowledge_review_cases","ORDER BY deadline_at")

    active_holds=[x for x in holds if x["status"]=="active"]
    open_impacts=[x for x in impacts if x["status"]=="review_required"]
    sev_counts={k:sum(1 for x in open_impacts if x["severity"]==k) for k in SEVERITY_ORDER}
    target_counts={}
    for x in open_impacts:
        target_counts[x["target_kind"]]=target_counts.get(x["target_kind"],0)+1

    return {
        "version":"knowledge-change-impact-v1",
        "events":events,
        "impacts":impacts,
        "publication_holds":holds,
        "review_cases":cases,
        "summary":{
            "open_events":sum(1 for x in events if x["status"]=="open"),
            "open_impacts":len(open_impacts),
            "active_holds":len(active_holds),
            "severity_counts":sev_counts,
            "target_counts":target_counts,
            "audience_at_risk":sum(int(x.get("audience_count") or 0) for x in open_impacts),
        },
        "control_rules":[
            "Critical/high source changes create publication holds on affected public-facing assets.",
            "Publication holds do not delete content; they remove trusted/current publication eligibility until reviewed.",
            "Only an authorized editor/governance resolution may release a hold.",
            "Historical superseded/retracted claims remain visible but do not create fresh holds.",
        ],
        "truth_boundary":{
            "demo_change_events":True,
            "external_source_monitoring":False,
            "automatic_hold":True,
            "automatic_hold_release":False,
            "automatic_medical_rewrite":False,
        },
    }


def _event_claims_release_ready(c,event_id):
    claim_ids={r["claim_id"] for r in c.execute("SELECT DISTINCT claim_id FROM knowledge_impacts WHERE event_id=?",(event_id,))}
    for claim_id in claim_ids:
        d=evidence_graph.snapshot(c,claim_id=claim_id)
        if not d["claims"]:
            return False
        claim=d["claims"][0]
        if claim["trust"]["trusted"] or claim["trust"]["superseded"] or claim["trust"]["retracted"]:
            continue
        return False
    return True


def resolve_case(c,event_id,resolution,actor,release_holds=False):
    case=c.execute("SELECT id,status FROM knowledge_review_cases WHERE event_id=? AND status='open'",(event_id,)).fetchone()
    if not case:
        raise ValueError("open_review_case_not_found")
    if release_holds and not _event_claims_release_ready(c,event_id):
        raise ValueError("evidence_remediation_required")
    now=int(time.time())
    c.execute(
        "UPDATE knowledge_review_cases SET status='resolved',resolution=?,resolved_by=?,resolved_at=? WHERE id=?",
        (str(resolution or "")[:800],actor,now,case["id"]),
    )
    c.execute("UPDATE knowledge_impacts SET status='reviewed' WHERE event_id=? AND status='review_required'",(event_id,))
    c.execute("UPDATE knowledge_change_events SET status='reviewed' WHERE id=?",(event_id,))
    if release_holds:
        c.execute(
            "UPDATE publication_holds SET status='released',released_at=?,released_by=? WHERE event_id=? AND status='active'",
            (now,actor,event_id),
        )


def is_held(c,artifact_kind,artifact_ref):
    try:
        return bool(c.execute(
            "SELECT 1 FROM publication_holds WHERE artifact_kind=? AND artifact_ref=? AND status='active' LIMIT 1",
            (artifact_kind,artifact_ref),
        ).fetchone())
    except Exception:
        return False
