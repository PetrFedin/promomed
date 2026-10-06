import hashlib
import json
import re
import time
import urllib.parse
import urllib.request

from app import change_impact, reviewer_authority


REVIEW_ROLES=("editorial","scientific")
POLL_INTERVAL_SECONDS=6*60*60
BASE_BACKOFF_SECONDS=60
MAX_PROVIDER_ATTEMPTS=5
CHANGE_SEVERITY={
    "new_source":"medium",
    "source_updated":"medium",
    "source_corrected":"high",
    "source_retracted":"critical",
}
CHANGE_TO_IMPACT={
    "source_updated":"source_updated",
    "source_corrected":"source_corrected",
    "source_retracted":"source_retracted",
}


def canonical_external_id(provider,value):
    provider=str(provider or "").strip().lower()
    raw=str(value or "").strip()
    if provider=="crossref":
        v=raw.lower()
        for prefix in ("https://doi.org/","http://doi.org/","doi:"):
            if v.startswith(prefix):
                v=v[len(prefix):]
        if not v.startswith("10.") or "/" not in v:
            raise ValueError("invalid_doi")
        return v
    if provider=="pubmed":
        v=re.sub(r"\D","",raw)
        if not v:
            raise ValueError("invalid_pmid")
        return v
    raise ValueError("unsupported_provider")


def canonical_key(provider,external_id):
    return f"{provider.lower()}:{canonical_external_id(provider,external_id)}"


def _sha(payload):
    canonical=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest(),canonical


def normalize_crossref(payload,external_id):
    msg=payload.get("message",payload) if isinstance(payload,dict) else {}
    doi=canonical_external_id("crossref",msg.get("DOI") or external_id)
    title=msg.get("title") or []
    title=title[0] if isinstance(title,list) and title else str(title or "")
    publisher=str(msg.get("publisher") or "")
    published=""
    issued=msg.get("issued") or msg.get("published") or {}
    parts=issued.get("date-parts") if isinstance(issued,dict) else None
    if isinstance(parts,list) and parts and isinstance(parts[0],list):
        published="-".join(str(x) for x in parts[0])
    updates=msg.get("update-to") or msg.get("update_to") or []
    if isinstance(updates,dict):
        updates=[updates]
    update_types=[str(x.get("type") or "").lower() for x in updates if isinstance(x,dict)]
    status="active"
    if any("retract" in x or "withdraw" in x for x in update_types):
        status="retracted"
    elif any("correct" in x or "errat" in x for x in update_types):
        status="corrected"
    return {
        "provider":"crossref",
        "external_id":doi,
        "canonical_key":f"doi:{doi}",
        "title":title,
        "publisher":publisher,
        "published_at":published,
        "source_ref":f"https://doi.org/{doi}",
        "provider_status":status,
        "version_marker":"|".join(sorted(update_types)),
        "update_types":sorted(update_types),
    }


def normalize_pubmed(payload,external_id):
    pmid=canonical_external_id("pubmed",external_id)
    result=payload.get("result",payload) if isinstance(payload,dict) else {}
    rec=result.get(pmid,result) if isinstance(result,dict) else {}
    title=str(rec.get("title") or "")
    pubdate=str(rec.get("pubdate") or rec.get("sortpubdate") or "")
    source=str(rec.get("source") or rec.get("fulljournalname") or "")
    pubtypes=rec.get("pubtype") or rec.get("pubtypes") or []
    if isinstance(pubtypes,str):
        pubtypes=[pubtypes]
    types=[str(x).lower() for x in pubtypes]
    status="active"
    if any("retracted publication" in x for x in types):
        status="retracted"
    elif any("retraction of publication" in x or "published erratum" in x or "corrected" in x for x in types):
        status="corrected"
    return {
        "provider":"pubmed",
        "external_id":pmid,
        "canonical_key":f"pmid:{pmid}",
        "title":title,
        "publisher":source,
        "published_at":pubdate,
        "source_ref":f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "provider_status":status,
        "version_marker":"|".join(sorted(types)),
        "publication_types":sorted(types),
    }


def normalize(provider,payload,external_id):
    p=str(provider or "").lower()
    if p=="crossref":
        return normalize_crossref(payload,external_id)
    if p=="pubmed":
        return normalize_pubmed(payload,external_id)
    raise ValueError("unsupported_provider")


def fetch_live(provider,external_id,tool="promomed-sostoyanie",email=""):
    provider=str(provider or "").lower()
    ext=canonical_external_id(provider,external_id)
    headers={"User-Agent":f"{tool}/1.0 ({email or 'evidence-monitor'})","Accept":"application/json"}
    if provider=="crossref":
        url="https://api.crossref.org/works/"+urllib.parse.quote(ext,safe="")
    elif provider=="pubmed":
        params={"db":"pubmed","id":ext,"retmode":"json","tool":tool}
        if email:
            params["email"]=email
        url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?"+urllib.parse.urlencode(params)
    else:
        raise ValueError("unsupported_provider")
    req=urllib.request.Request(url,headers=headers,method="GET")
    with urllib.request.urlopen(req,timeout=8) as resp:
        if int(getattr(resp,"status",200))!=200:
            raise ValueError("provider_http_error")
        return json.loads(resp.read().decode("utf-8"))


def ensure_target(c,provider,external_id,actor,demo_only=1):
    provider=str(provider or "").lower()
    ext=canonical_external_id(provider,external_id)
    key=canonical_key(provider,ext)
    target_id=f"watch:{provider}:{ext}"
    now=int(time.time())
    c.execute(
        "INSERT INTO evidence_watch_targets(id,provider,external_id,canonical_key,status,created_by,created_at,demo_only) "
        "VALUES(?,?,?,?,'active',?,?,?) ON CONFLICT(provider,external_id) DO NOTHING",
        (target_id,provider,ext,key,actor,now,int(bool(demo_only))),
    )
    _ensure_monitor_job(c,target_id,now=now,demo_only=demo_only)
    return target_id


def _ensure_monitor_job(c,target_id,now=None,interval_seconds=POLL_INTERVAL_SECONDS,demo_only=1):
    now=int(time.time()) if now is None else int(now)
    c.execute(
        "INSERT INTO evidence_monitor_jobs(target_id,status,next_run_at,attempt_count,max_attempts,interval_seconds,last_error,updated_at,demo_only) "
        "VALUES(?,'queued',?,0,?,?, '',?,?) ON CONFLICT(target_id) DO NOTHING",
        (target_id,now,int(MAX_PROVIDER_ATTEMPTS),int(interval_seconds),now,int(bool(demo_only))),
    )


def ensure_all_monitor_jobs(c,now=None):
    now=int(time.time()) if now is None else int(now)
    missing=list(c.execute(
        "SELECT w.id,w.demo_only FROM evidence_watch_targets w "
        "LEFT JOIN evidence_monitor_jobs j ON j.target_id=w.id "
        "WHERE w.status='active' AND j.target_id IS NULL ORDER BY w.id"
    ))
    for row in missing:
        _ensure_monitor_job(c,row["id"],now=now,demo_only=row["demo_only"])
    return len(missing)


def _retry_delay(attempt):
    attempt=max(1,int(attempt))
    return min(POLL_INTERVAL_SECONDS,BASE_BACKOFF_SECONDS*(2**(attempt-1)))


def run_due_jobs(c,actor="evidence-monitor-worker",now=None,limit=20,tool="promomed-sostoyanie",email=""):
    now=int(time.time()) if now is None else int(now)
    ensure_all_monitor_jobs(c,now=now)
    rows=list(c.execute(
        "SELECT j.target_id,j.attempt_count,j.max_attempts,j.interval_seconds,w.provider,w.external_id "
        "FROM evidence_monitor_jobs j JOIN evidence_watch_targets w ON w.id=j.target_id "
        "WHERE w.status='active' AND j.status IN ('queued','retry') AND j.next_run_at<=? "
        "ORDER BY j.next_run_at,j.target_id LIMIT ?",
        (now,int(limit)),
    ))
    results=[]
    for row in rows:
        attempt=int(row["attempt_count"] or 0)+1
        c.execute(
            "UPDATE evidence_monitor_jobs SET status='running',attempt_count=?,last_started_at=?,updated_at=? WHERE target_id=?",
            (attempt,now,now,row["target_id"]),
        )
        try:
            result=fetch_and_ingest(c,row["provider"],row["external_id"],actor,tool=tool,email=email)
        except ValueError as exc:
            dead=attempt>=int(row["max_attempts"] or MAX_PROVIDER_ATTEMPTS)
            status="dead" if dead else "retry"
            next_run=now if dead else now+_retry_delay(attempt)
            c.execute(
                "UPDATE evidence_monitor_jobs SET status=?,next_run_at=?,last_error=?,last_finished_at=?,updated_at=? WHERE target_id=?",
                (status,next_run,str(exc)[:500],now,now,row["target_id"]),
            )
            results.append({"target_id":row["target_id"],"status":status,"attempt":attempt,"next_run_at":next_run})
            continue
        next_run=now+int(row["interval_seconds"] or POLL_INTERVAL_SECONDS)
        c.execute(
            "UPDATE evidence_monitor_jobs SET status='queued',next_run_at=?,attempt_count=0,last_error='',last_finished_at=?,updated_at=? WHERE target_id=?",
            (next_run,now,now,row["target_id"]),
        )
        results.append({"target_id":row["target_id"],"status":"ok","attempt":attempt,"next_run_at":next_run,"change_type":result.get("change_type"),"duplicate":bool(result.get("duplicate"))})
    return {"processed":len(results),"results":results}


def requeue_dead_job(c,target_id,now=None):
    now=int(time.time()) if now is None else int(now)
    row=c.execute("SELECT target_id,status FROM evidence_monitor_jobs WHERE target_id=?",(target_id,)).fetchone()
    if not row:
        raise ValueError("monitor_job_not_found")
    if row["status"]!="dead":
        raise ValueError("monitor_job_not_dead")
    c.execute(
        "UPDATE evidence_monitor_jobs SET status='queued',next_run_at=?,attempt_count=0,last_error='',updated_at=? WHERE target_id=?",
        (now,now,target_id),
    )


def _current_snapshot(c,target_id):
    return c.execute(
        "SELECT id,normalized_json,payload_hash,provider_status,version_marker,fetched_at FROM evidence_provider_snapshots WHERE target_id=? AND is_current=1 ORDER BY fetched_at DESC,id DESC LIMIT 1",
        (target_id,),
    ).fetchone()


def classify_change(previous,normalized):
    if previous is None:
        return "new_source","First admitted provider snapshot."
    if previous["payload_hash"]==_sha(normalized)[0]:
        return None,"No normalized metadata change."
    old_status=str(previous["provider_status"] or "")
    new_status=str(normalized.get("provider_status") or "")
    if new_status=="retracted" and old_status!="retracted":
        return "source_retracted","Provider metadata now signals retraction/withdrawal."
    if new_status=="corrected" and old_status!="corrected":
        return "source_corrected","Provider metadata now signals correction/erratum."
    return "source_updated","Normalized provider metadata changed."


def ingest_payload(c,provider,external_id,payload,actor,demo_only=1):
    target_id=ensure_target(c,provider,external_id,actor,demo_only)
    normalized=normalize(provider,payload,external_id)
    digest,canonical_json=_sha(normalized)
    previous=_current_snapshot(c,target_id)
    if previous and previous["payload_hash"]==digest:
        return {"target_id":target_id,"snapshot_id":previous["id"],"candidate_id":None,"duplicate":True,"change_type":None}

    now=int(time.time())
    snapshot_id=f"snap:{target_id}:{digest[:16]}"
    c.execute("UPDATE evidence_provider_snapshots SET is_current=0 WHERE target_id=?",(target_id,))
    c.execute(
        "INSERT INTO evidence_provider_snapshots(id,target_id,provider,external_id,normalized_json,payload_hash,provider_status,version_marker,fetched_at,is_current,demo_only) "
        "VALUES(?,?,?,?,?,?,?,?,?,1,?)",
        (snapshot_id,target_id,normalized["provider"],normalized["external_id"],canonical_json,digest,normalized["provider_status"],normalized.get("version_marker") or "",now,int(bool(demo_only))),
    )
    change_type,reason=classify_change(previous,normalized)
    candidate_id=None
    if change_type:
        severity=CHANGE_SEVERITY[change_type]
        candidate_id=f"candidate:{snapshot_id}:{change_type}"
        c.execute(
            "INSERT INTO evidence_admission_candidates(id,target_id,snapshot_id,change_type,severity,reason,status,created_at,demo_only) "
            "VALUES(?,?,?,?,?,?,'pending_review',?,?) ON CONFLICT(target_id,snapshot_id,change_type) DO NOTHING",
            (candidate_id,target_id,snapshot_id,change_type,severity,reason,now,int(bool(demo_only))),
        )
        for role in REVIEW_ROLES:
            c.execute(
                "INSERT INTO evidence_admission_reviews(id,candidate_id,review_role,status,note,demo_only) "
                "VALUES(?,?,?,'awaiting','',?) ON CONFLICT(candidate_id,review_role) DO NOTHING",
                (f"{candidate_id}:{role}",candidate_id,role,int(bool(demo_only))),
            )
    return {"target_id":target_id,"snapshot_id":snapshot_id,"candidate_id":candidate_id,"duplicate":False,"change_type":change_type}


def review_candidate(c,candidate_id,review_role,actor,decision="accept_demo",note=""):
    if review_role not in REVIEW_ROLES:
        raise ValueError("unsupported_review_role")
    candidate=c.execute("SELECT id,status,demo_only FROM evidence_admission_candidates WHERE id=?",(candidate_id,)).fetchone()
    if not candidate:
        raise ValueError("candidate_not_found")
    if candidate["status"] not in ("pending_review","review_ready"):
        raise ValueError("candidate_not_reviewable")
    is_demo=bool(candidate["demo_only"])
    if review_role=="scientific" and not is_demo:
        raise ValueError("scientific_review_authority_required")
    accepted=decision in ("accept","accept_demo")
    if review_role=="editorial":
        status=("accepted_demo" if is_demo else "accepted_editorial") if accepted else ("rejected_demo" if is_demo else "rejected_editorial")
    else:
        status="accepted_demo" if accepted else "rejected_demo"
    c.execute(
        "UPDATE evidence_admission_reviews SET status=?,reviewer=?,reviewed_at=?,note=? WHERE candidate_id=? AND review_role=?",
        (status,actor,time.time_ns(),str(note or "")[:500],candidate_id,review_role),
    )
    rows={x["review_role"]:x["status"] for x in c.execute("SELECT review_role,status FROM evidence_admission_reviews WHERE candidate_id=?",(candidate_id,))}
    if any(str(x).startswith("rejected") for x in rows.values()):
        c.execute("UPDATE evidence_admission_candidates SET status=? WHERE id=?",("rejected_demo" if is_demo else "rejected_review",candidate_id))
    else:
        editorial_ok=rows.get("editorial") in ("accepted_demo","accepted_editorial")
        scientific_ok=rows.get("scientific") in ("accepted_demo","accepted_authority")
        if editorial_ok and scientific_ok:
            c.execute("UPDATE evidence_admission_candidates SET status='review_ready' WHERE id=?",(candidate_id,))


def _source_id_for_target(target_id):
    return "EXT-"+hashlib.sha256(target_id.encode("utf-8")).hexdigest()[:12].upper()


def admit_candidate(c,candidate_id,actor):
    row=c.execute(
        "SELECT ac.id,ac.target_id,ac.snapshot_id,ac.change_type,ac.severity,ac.status,ac.demo_only,wt.provider,wt.external_id,wt.source_id,s.normalized_json "
        "FROM evidence_admission_candidates ac JOIN evidence_watch_targets wt ON wt.id=ac.target_id "
        "JOIN evidence_provider_snapshots s ON s.id=ac.snapshot_id WHERE ac.id=?",
        (candidate_id,),
    ).fetchone()
    if not row:
        raise ValueError("candidate_not_found")
    if row["status"]!="review_ready":
        raise ValueError("candidate_reviews_required")
    is_demo=bool(row["demo_only"])
    reviews=list(c.execute("SELECT review_role,status,reviewer FROM evidence_admission_reviews WHERE candidate_id=?",(candidate_id,)))
    review_by_role={x["review_role"]:x for x in reviews}
    if not is_demo:
        account=c.execute("SELECT role,status FROM accounts WHERE email=?",(actor.lower(),)).fetchone()
        if not account or account["role"]!="governance" or account["status"]!="active":
            raise ValueError("governance_admission_required")
        editorial=review_by_role.get("editorial")
        scientific=review_by_role.get("scientific")
        if not editorial or editorial["status"]!="accepted_editorial":
            raise ValueError("editorial_review_required")
        if not scientific or scientific["status"]!="accepted_authority":
            raise ValueError("scientific_authority_review_required")
        reviewers={str(editorial["reviewer"] or "").lower(),str(scientific["reviewer"] or "").lower()}
        if "" in reviewers or len(reviewers)!=2 or actor.lower() in reviewers:
            raise ValueError("separation_of_duties_violation")

    normalized=json.loads(row["normalized_json"])
    source_id=row["source_id"] or _source_id_for_target(row["target_id"])
    now=int(time.time())
    existing=c.execute("SELECT id FROM evidence_sources WHERE id=?",(source_id,)).fetchone()
    disclosure=(
        f"External metadata admitted from {row['provider']} after governed editorial + independent scientific review."
        if not is_demo else
        f"External metadata admitted from {row['provider']} after editorial + scientific demo review."
    )
    if existing:
        c.execute(
            "UPDATE evidence_sources SET title=?,publisher=?,source_ref=?,published_at=?,status='active',disclosure=?,demo_only=? WHERE id=?",
            (normalized.get("title") or "",normalized.get("publisher") or "",normalized.get("source_ref") or "",normalized.get("published_at") or "",disclosure,int(is_demo),source_id),
        )
    else:
        c.execute(
            "INSERT INTO evidence_sources(id,source_kind,title,publisher,source_ref,published_at,status,disclosure,demo_only) VALUES(?,?,?,?,?,?,'active',?,?)",
            (source_id,f"external_{row['provider']}",normalized.get("title") or "",normalized.get("publisher") or "",normalized.get("source_ref") or "",normalized.get("published_at") or "",disclosure,int(is_demo)),
        )
    c.execute("UPDATE evidence_watch_targets SET source_id=? WHERE id=?",(source_id,row["target_id"]))

    event_id=None
    if row["change_type"] in CHANGE_TO_IMPACT and existing:
        event_id=change_impact.analyze_source_change(
            c,source_id,CHANGE_TO_IMPACT[row["change_type"]],
            f"Admitted external evidence change from {row['provider']} {row['external_id']}: {row['change_type']}",
            actor,
        )
    status="admitted_demo" if is_demo else "admitted"
    c.execute(
        "UPDATE evidence_admission_candidates SET status=?,admitted_at=?,admitted_by=?,admitted_source_id=?,change_event_id=? WHERE id=?",
        (status,now,actor,source_id,event_id,candidate_id),
    )
    if not is_demo:
        reviewer_authority.record_governance_admission(c,candidate_id,actor,source_id,event_id)
    return {"source_id":source_id,"change_event_id":event_id}


def record_provider_error(c,provider,external_id,error,actor="system"):
    provider=str(provider or "").lower()
    try:
        ext=canonical_external_id(provider,external_id)
        target_id=ensure_target(c,provider,ext,actor,1)
    except Exception:
        ext=str(external_id or "")[:160]
        target_id=None
    now=int(time.time())
    raw=f"{provider}|{ext}|{type(error).__name__}|{now}|{time.time_ns()}"
    error_id="provider-error:"+hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
    c.execute(
        "INSERT INTO evidence_provider_errors(id,target_id,provider,external_id,error_type,error_message,occurred_at,demo_only) VALUES(?,?,?,?,?,?,?,1)",
        (error_id,target_id,provider,ext,type(error).__name__,str(error)[:500],now),
    )
    return error_id


def fetch_and_ingest(c,provider,external_id,actor,tool="promomed-sostoyanie",email=""):
    try:
        payload=fetch_live(provider,external_id,tool=tool,email=email)
    except Exception as e:
        record_provider_error(c,provider,external_id,e,actor)
        raise ValueError("provider_fetch_failed")
    return ingest_payload(c,provider,external_id,payload,actor,demo_only=0)


def snapshot(c):
    targets=[dict(r) for r in c.execute("SELECT id,provider,external_id,canonical_key,source_id,status,created_by,created_at FROM evidence_watch_targets ORDER BY created_at,id")]
    snapshots=[dict(r) for r in c.execute("SELECT id,target_id,provider,external_id,payload_hash,provider_status,version_marker,fetched_at,is_current FROM evidence_provider_snapshots ORDER BY fetched_at DESC,id DESC LIMIT 50")]
    candidates=[dict(r) for r in c.execute("SELECT id,target_id,snapshot_id,change_type,severity,reason,status,created_at,admitted_at,admitted_by,admitted_source_id,change_event_id FROM evidence_admission_candidates ORDER BY created_at DESC,id DESC LIMIT 50")]
    reviews=[dict(r) for r in c.execute("SELECT candidate_id,review_role,status,reviewer,reviewed_at,note FROM evidence_admission_reviews ORDER BY candidate_id,review_role")]
    try:
        errors=[dict(r) for r in c.execute("SELECT id,target_id,provider,external_id,error_type,error_message,occurred_at,resolved_at FROM evidence_provider_errors ORDER BY occurred_at DESC,id DESC LIMIT 30")]
    except Exception:
        errors=[]
    try:
        jobs=[dict(r) for r in c.execute("SELECT target_id,status,next_run_at,attempt_count,max_attempts,interval_seconds,last_error,last_started_at,last_finished_at,updated_at FROM evidence_monitor_jobs ORDER BY next_run_at,target_id")]
    except Exception:
        jobs=[]
    return {
        "version":"external-evidence-admission-v1",
        "targets":targets,
        "snapshots":snapshots,
        "candidates":candidates,
        "reviews":reviews,
        "provider_errors":errors,
        "monitor_jobs":jobs,
        "summary":{
            "watch_targets":len(targets),
            "current_snapshots":sum(1 for x in snapshots if int(x["is_current"])),
            "pending_candidates":sum(1 for x in candidates if x["status"] in ("pending_review","review_ready")),
            "admitted_candidates":sum(1 for x in candidates if x["status"]=="admitted_demo"),
            "provider_errors":sum(1 for x in errors if not x.get("resolved_at")),
            "monitor_jobs":len(jobs),
            "dead_letter_jobs":sum(1 for x in jobs if x["status"]=="dead"),
        },
        "admission_rule":"External provider metadata is a signal. Evidence Graph and Change Impact update only after governed admission.",
        "truth_boundary":{
            "live_provider_adapter_present":True,
            "continuous_monitoring":False,
            "scheduled_worker_present":True,
            "durable_retry_backoff":True,
            "dead_letter_queue":True,
            "independent_scientific_reviewer":False,
            "automatic_medical_truth":False,
            "automatic_claim_rewrite":False,
        },
    }


DEMO_CROSSREF_BASE={
    "message":{
        "DOI":"10.5555/promomed.demo.metabolic",
        "title":["DEMO external evidence: metabolic health review"],
        "publisher":"Demo Journal",
        "issued":{"date-parts":[[2026,9,1]]},
        "update-to":[],
    }
}
DEMO_CROSSREF_RETRACTED={
    "message":{
        "DOI":"10.5555/promomed.demo.metabolic",
        "title":["DEMO external evidence: metabolic health review"],
        "publisher":"Demo Journal",
        "issued":{"date-parts":[[2026,9,1]]},
        "update-to":[{"type":"retraction","updated":{"date-parts":[[2026,10,6]]}}],
    }
}


def seed_demo(c,actor="system@demo"):
    target_id=ensure_target(c,"crossref","10.5555/promomed.demo.metabolic",actor,1)
    if not _current_snapshot(c,target_id):
        result=ingest_payload(c,"crossref","10.5555/promomed.demo.metabolic",DEMO_CROSSREF_BASE,actor,1)
        if result["candidate_id"]:
            # Baseline candidate is deliberately admitted in seed so monitoring starts from a known current source.
            for role in REVIEW_ROLES:
                review_candidate(c,result["candidate_id"],role,actor,"accept_demo","Seed baseline admission.")
            admit_candidate(c,result["candidate_id"],actor)
    target=c.execute("SELECT source_id FROM evidence_watch_targets WHERE id=?",(target_id,)).fetchone()
    if target and target["source_id"]:
        c.execute(
            "INSERT OR IGNORE INTO evidence_citations(id,claim_id,source_id,locator,quote_excerpt,support_type,status,demo_only) "
            "VALUES('EC-EXT-CL01','CL01',?,'provider-metadata:baseline','','supports','active',1)",
            (target["source_id"],),
        )
