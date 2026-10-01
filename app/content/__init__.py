from app.domain import audit, dump, hash_text, now, uid

STATES = (
    "draft","editorial_review","medical_review","compliance_review",
    "approved","scheduled","published","corrected","retracted"
)
TRANSITIONS = {
    "draft": {"editorial_review"},
    "editorial_review": {"medical_review","draft"},
    "medical_review": {"compliance_review","editorial_review"},
    "compliance_review": {"approved","medical_review"},
    "approved": {"scheduled","published"},
    "scheduled": {"published","approved"},
    "published": {"corrected","retracted"},
    "corrected": {"published","retracted"},
    "retracted": set(),
}

def create_publication(c, data, actor):
    key = str(data.get("publication_key") or uid("publication"))[:80]
    version = int(data.get("version") or 1)
    pid = f"{key}:v{version}"
    title = str(data.get("title") or "").strip()[:240]
    if not title:
        raise ValueError("title_required")
    body = str(data.get("body") or "")
    disclosure = str(data.get("disclosure") or "")
    ts = now()
    c.execute(
        """INSERT INTO publication_versions(
            id,publication_key,version,source_type,source_ref,title,body,author,disclosure,state,
            snapshot_hash,scheduled_at,published_at,corrected_at,created_at,updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,'draft',NULL,NULL,NULL,NULL,?,?)""",
        (pid,key,version,str(data.get("source_type") or "native"),str(data.get("source_ref") or ""),
         title,body,str(data.get("author") or actor),disclosure,ts,ts)
    )
    audit(c,"publication_created",actor,{"publication_id":pid,"version":version})
    return get_publication(c,pid)

def get_publication(c, pid):
    row=c.execute("SELECT * FROM publication_versions WHERE id=?",(pid,)).fetchone()
    return dict(row) if row else None

def list_publications(c, public_only=False):
    if public_only:
        rows=c.execute("SELECT * FROM publication_versions WHERE state IN ('published','corrected') ORDER BY published_at DESC,updated_at DESC").fetchall()
    else:
        rows=c.execute("SELECT * FROM publication_versions ORDER BY updated_at DESC").fetchall()
    return [dict(r) for r in rows]

def transition(c, pid, target, actor, review_kind=None, notes=""):
    row=get_publication(c,pid)
    if not row:
        raise LookupError("publication_not_found")
    target=str(target)
    if target not in TRANSITIONS.get(row["state"],set()):
        raise ValueError("invalid_transition")
    ts=now()
    snapshot_hash=row.get("snapshot_hash")
    published_at=row.get("published_at")
    corrected_at=row.get("corrected_at")
    if target in ("approved","published","corrected"):
        snapshot_hash=hash_text(dump({
            "publication_key":row["publication_key"],"version":row["version"],"title":row["title"],
            "body":row["body"],"author":row["author"],"disclosure":row["disclosure"],"state":target
        }))
    if target=="published": published_at=ts
    if target=="corrected": corrected_at=ts
    c.execute(
        "UPDATE publication_versions SET state=?,snapshot_hash=?,published_at=?,corrected_at=?,updated_at=? WHERE id=?",
        (target,snapshot_hash,published_at,corrected_at,ts,pid)
    )
    if review_kind:
        c.execute(
            "INSERT INTO editorial_reviews(id,publication_id,review_kind,reviewer,decision,notes,created_at) VALUES(?,?,?,?,?,?,?)",
            (uid("review"),pid,str(review_kind),actor,target,str(notes or ""),ts)
        )
    audit(c,"publication_transition",actor,{"publication_id":pid,"from":row["state"],"to":target})
    return get_publication(c,pid)

def import_snapshot(c, payload, actor="provider"):
    provider=str(payload.get("provider") or "directus")
    external_id=str(payload.get("external_id") or "").strip()
    if not external_id:
        raise ValueError("external_id_required")
    version=int(payload.get("version") or 1)
    key=f"{provider}:{external_id}"
    existing=c.execute("SELECT id FROM publication_versions WHERE publication_key=? AND version=?",(key,version)).fetchone()
    if existing:
        return get_publication(c,existing["id"])
    data=dict(payload)
    data["publication_key"]=key
    data["source_type"]=provider
    data["source_ref"]=external_id
    pub=create_publication(c,data,actor)
    target=str(payload.get("state") or "draft")
    review_chain=payload.get("review_chain") or []
    if target in ("approved","scheduled","published"):
        required=("editorial","medical","compliance")
        kinds={str(x.get("kind") or "") for x in review_chain if isinstance(x,dict)}
        missing=[x for x in required if x not in kinds]
        if missing:
            raise ValueError("review_chain_required:"+",".join(missing))
        pub=transition(c,pub["id"],"editorial_review",actor,"editorial","external reviewed snapshot")
        pub=transition(c,pub["id"],"medical_review",actor,"medical","external reviewed snapshot")
        pub=transition(c,pub["id"],"compliance_review",actor,"compliance","external reviewed snapshot")
        pub=transition(c,pub["id"],"approved",actor,"compliance","review chain complete")
        if target=="scheduled":
            pub=transition(c,pub["id"],"scheduled",actor)
        elif target=="published":
            pub=transition(c,pub["id"],"published",actor)
    return pub

def ensure_legacy_demo_publications(c):
    rows=c.execute("SELECT id,title,dek,author,reviewer,partner,status FROM content_catalog ORDER BY id").fetchall()
    created=0
    for row in rows:
        key="legacy_demo:"+row["id"]
        existing=c.execute("SELECT id FROM publication_versions WHERE publication_key=? AND version=1",(key,)).fetchone()
        if existing:
            continue
        pub=create_publication(c,{
            "publication_key":key,
            "version":1,
            "source_type":"legacy_demo",
            "source_ref":row["id"],
            "title":row["title"],
            "body":row["dek"] or "",
            "author":row["author"] or "СОСТОЯНИЕ · demo",
            "disclosure":"DEMO migration snapshot. Не является подтверждением фактического medical/legal review.",
        },"demo-migration")
        for target,kind in (
            ("editorial_review","editorial"),
            ("medical_review","medical"),
            ("compliance_review","compliance"),
            ("approved","compliance"),
            ("published",None),
        ):
            pub=transition(
                c,pub["id"],target,"demo-migration",kind,
                "Illustrative demo approval state; production publication requires named authorised reviewers."
            )
        created+=1
    return created
