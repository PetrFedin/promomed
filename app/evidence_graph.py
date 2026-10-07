import time


DEMO_SOURCES = [
    ("ES01","publication_demo","DEMO · Обзор доказательств по метаболическому здоровью","СОСТОЯНИЕ Editorial","demo://publication/metabolic-evidence","2026-09-15","active","Демонстрационный источник для MVP; не реальная научная публикация."),
    ("ES02","transcript","P21 · transcript evidence","СОСТОЯНИЕ Studio","demo://replay/P21","2026-10-06","active","Источник — демонстрационная расшифровка Studio/replay."),
    ("ES03","publication_demo","DEMO · Методика чтения исследований","СОСТОЯНИЕ Editorial","demo://publication/research-literacy","2026-09-20","active","Демонстрационный источник для проверки citation/version workflow."),
]

DEMO_CLAIMS = [
    ("CL01","content","CT01","Интерпретация данных о метаболическом здоровье требует учитывать дизайн исследования и клинический контекст.","Метаболическое здоровье","reviewed_demo",1,"editor@demo.ru",None,""),
    ("CL02","content","CT01","Один результат исследования нельзя автоматически переносить на любого конкретного человека.","Метаболическое здоровье","reviewed_demo",1,"editor@demo.ru",None,""),
    ("CL03","content","CT02","Громкий заголовок сам по себе не показывает силу доказательств.","Научная грамотность","superseded_demo",1,"editor@demo.ru",None,"Формулировка уточнена в CL04."),
    ("CL04","content","CT02","Оценка силы доказательств требует проверки дизайна, источника и границ применимости вывода.","Научная грамотность","reviewed_demo",2,"editor@demo.ru","CL03","Уточнена формулировка и добавлена явная граница применимости."),
    ("CL05","content","CT07","Доверие к health-бренду требует прозрачного разделения редакционного, корпоративного и доказательного контекста.","Бренд и доверие","reviewed_demo",1,"editor@demo.ru",None,"DEMO gap: source/citation/graph trace ещё не приложены."),
]

DEMO_CITATIONS = [
    ("EC01","CL01","ES01","section: methodology","", "supports","active"),
    ("EC02","CL01","ES02","00:42-01:36","", "supports","active"),
    ("EC03","CL02","ES02","01:36-02:34","", "supports","active"),
    ("EC04","CL03","ES03","section: headlines","", "supports","superseded"),
    ("EC05","CL04","ES03","section: evidence limits","", "supports","active"),
]

DEMO_LINKS = [
    ("EL01","CL01","transcript","TS-P21-02","supported_by_segment",42,96),
    ("EL02","CL01","expert","SP07","review_context",None,None),
    ("EL03","CL01","event","P21","discussed_at",None,None),
    ("EL04","CL01","replay","P21","source_replay",42,96),
    ("EL05","CL02","transcript","TS-P21-03","supported_by_segment",96,154),
    ("EL06","CL02","expert","SP06","speaker_context",None,None),
    ("EL07","CL02","event","P21","discussed_at",None,None),
    ("EL08","CL02","replay","P21","source_replay",96,154),
    ("EL09","CL04","expert","SP01","review_context",None,None),
    ("EL10","CL04","event","P05","related_event",None,None),
    ("EL11","CL04","replay","P05","related_replay",0,240),
]


def seed_demo(c):
    now=int(time.time())
    for row in DEMO_SOURCES:
        c.execute(
            "INSERT OR IGNORE INTO evidence_sources(id,source_kind,title,publisher,source_ref,published_at,status,disclosure,demo_only) VALUES(?,?,?,?,?,?,?,?,1)",
            row,
        )
    for row in DEMO_CLAIMS:
        claim_id,artifact_kind,artifact_ref,claim_text,topic,status,version,reviewer,supersedes,correction=row
        c.execute(
            "INSERT OR IGNORE INTO evidence_claims(id,artifact_kind,artifact_ref,claim_text,topic,status,version,reviewer,reviewed_at,supersedes_claim_id,correction_note,demo_only) VALUES(?,?,?,?,?,?,?,?,?,?,?,1)",
            (claim_id,artifact_kind,artifact_ref,claim_text,topic,status,version,reviewer,now if reviewer else None,supersedes,correction),
        )
    for row in DEMO_CITATIONS:
        c.execute(
            "INSERT OR IGNORE INTO evidence_citations(id,claim_id,source_id,locator,quote_excerpt,support_type,status,demo_only) VALUES(?,?,?,?,?,?,?,1)",
            row,
        )
    for row in DEMO_LINKS:
        c.execute(
            "INSERT OR IGNORE INTO evidence_links(id,claim_id,target_kind,target_ref,relation,start_sec,end_sec,demo_only) VALUES(?,?,?,?,?,?,?,1)",
            row,
        )


def _sources(c):
    return {r["id"]:dict(r) for r in c.execute("SELECT id,source_kind,title,publisher,source_ref,published_at,status,disclosure FROM evidence_sources")}


def _claims(c,artifact_kind=None,artifact_ref=None):
    if artifact_kind and artifact_ref:
        rows=c.execute(
            "SELECT id,artifact_kind,artifact_ref,claim_text,topic,status,version,reviewer,reviewed_at,supersedes_claim_id,correction_note FROM evidence_claims WHERE artifact_kind=? AND artifact_ref=? ORDER BY version,id",
            (artifact_kind,artifact_ref),
        )
    else:
        rows=c.execute(
            "SELECT id,artifact_kind,artifact_ref,claim_text,topic,status,version,reviewer,reviewed_at,supersedes_claim_id,correction_note FROM evidence_claims ORDER BY artifact_kind,artifact_ref,version,id"
        )
    return [dict(r) for r in rows]


def _citations(c,claim_id):
    return [dict(r) for r in c.execute(
        "SELECT e.id,e.claim_id,e.source_id,e.locator,e.quote_excerpt,e.support_type,e.status,s.status source_status,s.source_kind,s.title source_title,s.publisher,s.source_ref,s.published_at,s.disclosure FROM evidence_citations e JOIN evidence_sources s ON s.id=e.source_id WHERE e.claim_id=? ORDER BY e.id",
        (claim_id,),
    )]


def _links(c,claim_id):
    return [dict(r) for r in c.execute(
        "SELECT id,claim_id,target_kind,target_ref,relation,start_sec,end_sec FROM evidence_links WHERE claim_id=? ORDER BY target_kind,id",
        (claim_id,),
    )]


def _trust_status(claim,citations,links):
    referenced_citations=[x for x in citations if x["status"]=="active"]
    active_citations=[x for x in referenced_citations if x.get("source_status")=="active"]
    invalidated_citations=[x for x in referenced_citations if x.get("source_status")!="active"]
    has_reviewer=bool(claim.get("reviewer") and claim.get("reviewed_at"))
    has_source=bool(active_citations)
    has_locator=bool(active_citations and all(str(x.get("locator") or "").strip() for x in active_citations))
    has_trace=bool(links)
    claim_status=str(claim.get("status") or "")
    superseded=claim_status.startswith("superseded")
    retracted=claim_status.startswith("retracted")
    reviewed=claim_status in ("reviewed","reviewed_demo","review_required","review_required_demo")
    trusted=reviewed and has_reviewer and has_source and has_locator and has_trace and not invalidated_citations and not superseded and not retracted
    if retracted:
        status="RETRACTED"
    elif superseded:
        status="SUPERSEDED"
    elif trusted:
        status="VERIFIED_DEMO"
    elif reviewed:
        status="INCOMPLETE_EVIDENCE"
    else:
        status="DRAFT"
    return {
        "status":status,
        "trusted":trusted,
        "reviewed":reviewed,
        "has_reviewer":has_reviewer,
        "has_active_source":has_source,
        "has_exact_locator":has_locator,
        "has_graph_trace":has_trace,
        "has_invalidated_citation":bool(invalidated_citations),
        "superseded":superseded,
        "retracted":retracted,
    }


def snapshot(c,artifact_kind=None,artifact_ref=None,claim_id=None):
    claims=_claims(c,artifact_kind,artifact_ref)
    if claim_id:
        claims=[x for x in claims if x["id"]==claim_id]
    enriched=[]
    for claim in claims:
        citations=_citations(c,claim["id"])
        links=_links(c,claim["id"])
        enriched.append({
            **claim,
            "citations":citations,
            "links":links,
            "trust":_trust_status(claim,citations,links),
        })
    active=[x for x in enriched if x["trust"]["trusted"]]
    superseded=[x for x in enriched if x["trust"]["superseded"]]
    return {
        "version":"claim-evidence-graph-v1",
        "artifact":{"kind":artifact_kind,"ref":artifact_ref},
        "claims":enriched,
        "summary":{
            "claims":len(enriched),
            "trusted":len(active),
            "superseded":len(superseded),
            "trust_complete":bool(enriched) and len(active)+len(superseded)==len(enriched),
        },
        "trust_rule":"A current claim is trusted only when reviewed, linked to an active source with an exact locator, and connected to at least one graph node.",
        "version_rule":"Superseded/corrected claims remain visible in history; corrections do not erase prior versions.",
        "truth_boundary":{
            "demo_sources":True,
            "external_publication_verified":False,
            "machine_checkable_graph":True,
            "medical_advice":False,
        },
    }


def correct_demo_claim(c,claim_id,new_claim_text,reviewer):
    old=c.execute(
        "SELECT id,artifact_kind,artifact_ref,topic,version,status FROM evidence_claims WHERE id=?",
        (claim_id,),
    ).fetchone()
    if not old:
        raise ValueError("claim_not_found")
    if old["status"] not in ("reviewed_demo","reviewed","review_required_demo"):
        raise ValueError("claim_not_current")
    now=int(time.time())
    new_id=f"{claim_id}-V{int(old['version'])+1}"
    c.execute(
        "UPDATE evidence_claims SET status='superseded_demo',correction_note=? WHERE id=?",
        (f"Superseded by {new_id}",claim_id),
    )
    c.execute(
        "INSERT INTO evidence_claims(id,artifact_kind,artifact_ref,claim_text,topic,status,version,reviewer,reviewed_at,supersedes_claim_id,correction_note,demo_only) VALUES(?,?,?,?,?,'reviewed_demo',?,?,?,?,?,1)",
        (new_id,old["artifact_kind"],old["artifact_ref"],new_claim_text[:800],old["topic"],int(old["version"])+1,reviewer,now,claim_id,"Demo correction created by editor."),
    )
    for citation in _citations(c,claim_id):
        if citation["status"]!="active":
            continue
        c.execute(
            "INSERT INTO evidence_citations(id,claim_id,source_id,locator,quote_excerpt,support_type,status,demo_only) VALUES(?,?,?,?,?,?,?,1)",
            (f"{citation['id']}-{new_id}",new_id,citation["source_id"],citation["locator"],citation["quote_excerpt"],citation["support_type"],"active"),
        )
    for link in _links(c,claim_id):
        c.execute(
            "INSERT INTO evidence_links(id,claim_id,target_kind,target_ref,relation,start_sec,end_sec,demo_only) VALUES(?,?,?,?,?,?,?,1)",
            (f"{link['id']}-{new_id}",new_id,link["target_kind"],link["target_ref"],link["relation"],link["start_sec"],link["end_sec"]),
        )
    return new_id


def retract_demo_claim(c,claim_id,note,reviewer):
    row=c.execute("SELECT id,status FROM evidence_claims WHERE id=?",(claim_id,)).fetchone()
    if not row:
        raise ValueError("claim_not_found")
    if row["status"] not in ("reviewed_demo","reviewed","review_required_demo"):
        raise ValueError("claim_not_current")
    c.execute(
        "UPDATE evidence_claims SET status='retracted_demo',reviewer=?,reviewed_at=?,correction_note=? WHERE id=?",
        (reviewer,int(time.time()),str(note or "Retracted in demo review.")[:500],claim_id),
    )


def coverage(c):
    claims=_claims(c)
    rows=[]
    for claim in claims:
        citations=_citations(c,claim["id"])
        links=_links(c,claim["id"])
        trust=_trust_status(claim,citations,links)
        gaps=[]
        if not trust["has_reviewer"]: gaps.append("reviewer_missing")
        if not trust["has_active_source"]: gaps.append("active_source_missing")
        if not trust["has_exact_locator"]: gaps.append("exact_locator_missing")
        if not trust["has_graph_trace"]: gaps.append("graph_trace_missing")
        if trust["superseded"]: gaps.append("superseded")
        if trust["retracted"]: gaps.append("retracted")
        rows.append({
            "claim_id":claim["id"],
            "artifact_kind":claim["artifact_kind"],
            "artifact_ref":claim["artifact_ref"],
            "claim_text":claim["claim_text"],
            "status":trust["status"],
            "trusted":trust["trusted"],
            "gaps":gaps,
            "reviewer":claim.get("reviewer"),
        })
    current=[x for x in rows if x["status"] not in ("SUPERSEDED","RETRACTED")]
    trusted=sum(1 for x in current if x["trusted"])
    return {
        "version":"evidence-coverage-v1",
        "summary":{
            "current_claims":len(current),
            "trusted_current_claims":trusted,
            "coverage_pct":round((trusted/len(current)*100.0),1) if current else 0.0,
            "open_gaps":sum(len(x["gaps"]) for x in current),
            "historical_versions":sum(1 for x in rows if x["status"] in ("SUPERSEDED","RETRACTED")),
        },
        "claims":rows,
        "publication_gate":"Current claims with evidence gaps must not be presented as VERIFIED.",
    }
