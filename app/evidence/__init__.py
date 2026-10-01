from app.domain import audit, dump, now, uid

def add_source(c,data,actor):
    sid=str(data.get("id") or uid("source"))[:100]
    title=str(data.get("title") or "").strip()[:300]
    if not title: raise ValueError("title_required")
    c.execute(
        """INSERT INTO evidence_sources(id,kind,title,authors,identifier,url,published_date,imported_from,metadata_json,review_status,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
           kind=excluded.kind,title=excluded.title,authors=excluded.authors,identifier=excluded.identifier,url=excluded.url,
           published_date=excluded.published_date,metadata_json=excluded.metadata_json,review_status=excluded.review_status""",
        (sid,str(data.get("kind") or "publication"),title,str(data.get("authors") or ""),str(data.get("identifier") or ""),
         str(data.get("url") or ""),str(data.get("published_date") or ""),str(data.get("imported_from") or "native"),
         dump(data.get("metadata") or {}),str(data.get("review_status") or "unreviewed"),now())
    )
    audit(c,"evidence_source_upserted",actor,{"source_id":sid})
    return dict(c.execute("SELECT * FROM evidence_sources WHERE id=?",(sid,)).fetchone())

def link_claim(c,data,actor):
    publication_id=str(data.get("publication_id") or "")
    source_id=str(data.get("source_id") or "")
    if not c.execute("SELECT 1 FROM publication_versions WHERE id=?",(publication_id,)).fetchone(): raise LookupError("publication_not_found")
    if not c.execute("SELECT 1 FROM evidence_sources WHERE id=?",(source_id,)).fetchone(): raise LookupError("source_not_found")
    citation_id=str(data.get("citation_id") or uid("citation"))
    c.execute(
        "INSERT INTO citations(id,publication_id,source_id,locator,label,status,created_at) VALUES(?,?,?,?,?,'linked',?) ON CONFLICT(id) DO NOTHING",
        (citation_id,publication_id,source_id,str(data.get("locator") or ""),str(data.get("label") or ""),now())
    )
    lid=uid("claim")
    c.execute(
        "INSERT INTO claim_evidence_links(id,publication_id,claim_key,claim_text,source_id,citation_id,reviewer_status,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (lid,publication_id,str(data.get("claim_key") or lid),str(data.get("claim_text") or ""),source_id,citation_id,str(data.get("reviewer_status") or "pending"),now())
    )
    audit(c,"claim_evidence_linked",actor,{"publication_id":publication_id,"source_id":source_id,"claim_id":lid})
    return {"id":lid,"citation_id":citation_id}

def sources_for_publication(c,pid):
    rows=c.execute(
        """SELECT ce.id claim_id,ce.claim_key,ce.claim_text,ce.reviewer_status,c.id citation_id,c.locator,c.label,
                  s.id source_id,s.kind,s.title,s.authors,s.identifier,s.url,s.published_date,s.review_status
           FROM claim_evidence_links ce
           JOIN evidence_sources s ON s.id=ce.source_id
           LEFT JOIN citations c ON c.id=ce.citation_id
           WHERE ce.publication_id=? ORDER BY ce.created_at""",(pid,)
    ).fetchall()
    return [dict(r) for r in rows]
