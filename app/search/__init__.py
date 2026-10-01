import os
import re
from app.domain import now
from app.providers import request_json

MEILI_URL=os.environ.get("MEILISEARCH_URL","").rstrip("/")
MEILI_INDEX=os.environ.get("MEILISEARCH_INDEX","promomed")
MEILI_KEY=os.environ.get("MEILISEARCH_API_KEY","")
SEMANTIC_URL=os.environ.get("SEMANTIC_RETRIEVAL_URL","").rstrip("/")

def provider_status():
    return {
        "full_text":{"provider":"meilisearch","connected":bool(MEILI_URL),"fallback":"promomed_sql_projection"},
        "semantic":{"provider":"external_postgres_compatible","connected":bool(SEMANTIC_URL),"fallback":"deterministic_term_overlap"}
    }

def rebuild(c):
    c.execute("DELETE FROM search_documents")
    ts=now()
    for r in c.execute("SELECT id,title,body,publication_key,state FROM publication_versions WHERE state IN ('published','corrected')"):
        c.execute("INSERT INTO search_documents(document_id,kind,title,body,topic,expert_id,event_id,partner,review_status,availability,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                  ("publication:"+r["id"],"publication",r["title"],r["body"] or "","",None,None,None,r["state"],"available",ts))
    for r in c.execute("SELECT id,name,role,org,bio,topics FROM speakers"):
        c.execute("INSERT INTO search_documents VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                  ("expert:"+r["id"],"expert",r["name"],(r["role"] or "")+" "+(r["org"] or "")+" "+(r["bio"] or ""),r["topics"] or "",r["id"],None,None,"profile","available",ts))
    for r in c.execute('SELECT id,title,track,format,venue,partner,replay,stream FROM program_items'):
        availability="live_replay" if r["stream"] and r["replay"] else ("replay" if r["replay"] else "onsite")
        c.execute("INSERT INTO search_documents VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                  ("session:"+r["id"],"session",r["title"],(r["format"] or "")+" "+(r["venue"] or ""),r["track"] or "",None,r["id"],r["partner"] or "","programme",availability,ts))
    for r in c.execute("SELECT id,title,dek,topic,speaker_id,item_id,status FROM studio_episodes"):
        c.execute("INSERT INTO search_documents VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                  ("studio:"+r["id"],"studio",r["title"],r["dek"] or "",r["topic"] or "",r["speaker_id"],r["item_id"],None,"editorial",r["status"],ts))
    for r in c.execute("SELECT id,name,category,description,status FROM partners"):
        c.execute("INSERT INTO search_documents VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                  ("partner:"+r["id"],"partner",r["name"],r["description"] or "",r["category"] or "",None,None,r["id"],"commercial_disclosure",r["status"],ts))
    for r in c.execute("SELECT id,name,theme,summary,company,disclosure FROM product_catalog"):
        c.execute("INSERT INTO search_documents VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                  ("product:"+r["id"],"product",r["name"],(r["summary"] or "")+" "+(r["disclosure"] or ""),r["theme"] or "",None,None,r["company"] or "","product_context","available",ts))
    for r in c.execute("SELECT id,title,topic,summary FROM learning_tracks"):
        c.execute("INSERT INTO search_documents VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                  ("learning:"+r["id"],"learning",r["title"],r["summary"] or "",r["topic"] or "",None,None,None,"editorial","available",ts))
    count=c.execute("SELECT COUNT(*) n FROM search_documents").fetchone()["n"]
    if MEILI_URL:
        sync_meilisearch(c)
    return count

def sync_meilisearch(c):
    if not MEILI_URL:
        return {"ok":False,"error":"provider_not_configured"}
    headers={"Authorization":"Bearer "+MEILI_KEY} if MEILI_KEY else {}
    docs=[dict(r) for r in c.execute("SELECT * FROM search_documents ORDER BY document_id")]
    facets=["kind","topic","expert_id","event_id","partner","review_status","availability"]
    settings=request_json(
        f"{MEILI_URL}/indexes/{MEILI_INDEX}/settings/filterable-attributes",
        facets,"PUT",headers
    )
    pushed=request_json(f"{MEILI_URL}/indexes/{MEILI_INDEX}/documents",docs,"POST",headers)
    return {"ok":bool(pushed.get("ok")),"settings":settings,"documents":pushed,"count":len(docs)}

def query(c,q="",kind=None,topic=None,review_status=None,availability=None,limit=30):
    clauses=[]; params=[]
    if q:
        clauses.append("(LOWER(title) LIKE ? OR LOWER(body) LIKE ? OR LOWER(topic) LIKE ?)")
        needle="%"+q.lower()+"%"; params += [needle,needle,needle]
    for col,val in (("kind",kind),("topic",topic),("review_status",review_status),("availability",availability)):
        if val:
            clauses.append(col+"=?"); params.append(val)
    sql="SELECT * FROM search_documents"
    if clauses: sql+=" WHERE "+" AND ".join(clauses)
    sql+=" ORDER BY kind,title LIMIT ?"; params.append(max(1,min(int(limit),100)))
    return [dict(r) for r in c.execute(sql,tuple(params)).fetchall()]

def semantic(c,q,limit=12):
    if SEMANTIC_URL:
        external=request_json(SEMANTIC_URL,{"query":q,"limit":max(1,min(int(limit),30))})
        if external.get("ok") and isinstance(external.get("body"),dict) and isinstance(external["body"].get("items"),list):
            return external["body"]["items"]
    tokens={x for x in re.findall(r"[\w-]+",q.lower()) if len(x)>2}
    rows=query(c,"",limit=100)
    scored=[]
    for r in rows:
        hay=((r.get("title") or "")+" "+(r.get("body") or "")+" "+(r.get("topic") or "")).lower()
        words=set(re.findall(r"[\w-]+",hay))
        score=len(tokens & words)
        if score:
            x=dict(r); x["similarity_basis"]="deterministic_term_overlap"; x["score"]=score; scored.append(x)
    scored.sort(key=lambda x:(-x["score"],x["kind"],x["document_id"]))
    return scored[:max(1,min(int(limit),30))]
