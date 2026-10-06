from collections import Counter


KINDS = ("content","expert","event","studio","replay","learning","topic","partner","product")


def _norm(value):
    return " ".join(str(value or "").lower().replace("ё","е").split())


def _tokens(value):
    return [x for x in _norm(value).replace("/"," ").replace("·"," ").replace(","," ").split() if x]


def _contains(haystack, needle):
    return needle in _norm(haystack)


def _index(c):
    rows=[]

    for x in c.execute("SELECT id,kind,theme,title,dek,duration,author,reviewer,partner,status FROM content_catalog"):
        rows.append({
            "kind":"content","ref":x["id"],"title":x["title"],"subtitle":x["dek"],"topic":x["theme"],
            "content_type":x["kind"],"expert":"","event":"","replay":False,"review_status":x["status"],
            "partner":x["partner"] or "","search_text":" ".join(map(str,[x["title"],x["dek"],x["theme"],x["author"],x["reviewer"],x["partner"]])),
        })

    for x in c.execute("SELECT id,name,role,org,bio,topics,kind FROM speakers"):
        rows.append({
            "kind":"expert","ref":x["id"],"title":x["name"],"subtitle":f"{x['role']} · {x['org']}","topic":x["topics"],
            "content_type":"expert","expert":x["name"],"event":"","replay":False,"review_status":"demo_profile",
            "partner":x["org"] or "","search_text":" ".join(map(str,[x["name"],x["role"],x["org"],x["bio"],x["topics"],x["kind"]])),
        })

    for x in c.execute('SELECT id,start,"end",venue,track,format,title,audience,stream,replay,partner FROM program_items'):
        rows.append({
            "kind":"event","ref":x["id"],"title":x["title"],"subtitle":f"{x['start']} · {x['venue']} · {x['format']}","topic":x["track"],
            "content_type":x["format"],"expert":"","event":x["id"],"replay":bool(x["replay"]),"review_status":"programme",
            "partner":x["partner"] or "","search_text":" ".join(map(str,[x["title"],x["track"],x["venue"],x["format"],x["audience"],x["partner"]])),
        })
        if x["replay"]:
            rows.append({
                "kind":"replay","ref":x["id"],"title":f"Replay · {x['title']}","subtitle":f"{x['venue']} · запись после события","topic":x["track"],
                "content_type":"replay","expert":"","event":x["id"],"replay":True,"review_status":"programme",
                "partner":x["partner"] or "","search_text":" ".join(map(str,[x["title"],x["track"],x["venue"],"replay запись видео",x["partner"]])),
            })

    for x in c.execute("SELECT e.id,e.topic,e.title,e.dek,e.duration,e.speaker_id,e.item_id,e.status,s.name speaker_name FROM studio_episodes e LEFT JOIN speakers s ON s.id=e.speaker_id"):
        rows.append({
            "kind":"studio","ref":x["id"],"title":x["title"],"subtitle":x["dek"],"topic":x["topic"],
            "content_type":"studio","expert":x["speaker_name"] or "","event":x["item_id"] or "","replay":x["status"]=="ready","review_status":x["status"],
            "partner":"","search_text":" ".join(map(str,[x["title"],x["dek"],x["topic"],x["speaker_name"],x["status"]])),
        })

    for x in c.execute("SELECT id,topic,title,summary,duration_days,level FROM learning_tracks"):
        rows.append({
            "kind":"learning","ref":x["id"],"title":x["title"],"subtitle":x["summary"],"topic":x["topic"],
            "content_type":"learning_track","expert":"","event":"","replay":False,"review_status":"educational",
            "partner":"","search_text":" ".join(map(str,[x["title"],x["summary"],x["topic"],x["level"]])),
        })

    topics=set()
    for row in c.execute("SELECT DISTINCT topic FROM community_threads WHERE status='open'"):
        if row["topic"]: topics.add(row["topic"])
    for row in c.execute("SELECT DISTINCT theme topic FROM content_catalog"):
        if row["topic"]: topics.add(row["topic"])
    for row in c.execute("SELECT DISTINCT track topic FROM program_items"):
        if row["topic"]: topics.add(row["topic"])
    for topic in sorted(topics):
        rows.append({
            "kind":"topic","ref":topic,"title":topic,"subtitle":"Материалы · эксперты · события · Studio · learning","topic":topic,
            "content_type":"topic","expert":"","event":"","replay":False,"review_status":"derived",
            "partner":"","search_text":topic,
        })

    for x in c.execute("SELECT id,name,category,description,status FROM partners"):
        rows.append({
            "kind":"partner","ref":x["id"],"title":x["name"],"subtitle":x["description"],"topic":x["category"],
            "content_type":"partner","expert":"","event":"","replay":False,"review_status":x["status"],
            "partner":x["name"],"search_text":" ".join(map(str,[x["name"],x["category"],x["description"]])),
        })

    for x in c.execute("SELECT id,name,company,theme,kind,summary,disclosure FROM product_catalog"):
        rows.append({
            "kind":"product","ref":x["id"],"title":x["name"],"subtitle":x["summary"],"topic":x["theme"],
            "content_type":x["kind"],"expert":"","event":"","replay":False,"review_status":"product_context",
            "partner":x["company"] or "","search_text":" ".join(map(str,[x["name"],x["company"],x["theme"],x["summary"],x["disclosure"]])),
        })
    return rows


def _score(row, query):
    q=_norm(query)
    if not q:
        return 1.0
    toks=_tokens(query)
    title=_norm(row["title"])
    topic=_norm(row["topic"])
    body=_norm(row["search_text"])
    score=0.0
    if q==title: score+=100
    if q in title: score+=45
    if q in topic: score+=30
    for t in toks:
        if t in title: score+=12
        if t in topic: score+=8
        if t in body: score+=3
    return score


def search(c, query="", kind="", topic="", expert="", event="", replay=None, review_status="", limit=30, email=None):
    rows=_index(c)
    saved=set()
    if email:
        try:
            saved={(x["target_kind"],x["target_ref"]) for x in c.execute("SELECT target_kind,target_ref FROM discovery_saves WHERE email=?",(email,))}
        except Exception:
            saved=set()

    filtered=[]
    for row in rows:
        if kind and row["kind"]!=kind: continue
        if topic and not _contains(row["topic"],topic): continue
        if expert and not _contains(row["expert"],expert): continue
        if event and row["event"]!=event: continue
        if replay is not None and bool(row["replay"])!=bool(replay): continue
        if review_status and row["review_status"]!=review_status: continue
        score=_score(row,query)
        if query and score<=0: continue
        out={k:v for k,v in row.items() if k!="search_text"}
        out["score"]=round(score,1)
        out["saved"]=(row["kind"],row["ref"]) in saved
        out["why"]="exact_title" if query and _norm(query)==_norm(row["title"]) else ("title_topic_match" if query else "browse")
        filtered.append(out)

    filtered.sort(key=lambda x:(-x["score"], x["kind"], x["title"], x["ref"]))
    filtered=filtered[:max(1,min(int(limit or 30),100))]

    facets={
        "kind":dict(Counter(x["kind"] for x in rows)),
        "topic":dict(Counter(x["topic"] for x in rows if x["topic"])),
        "review_status":dict(Counter(x["review_status"] for x in rows if x["review_status"])),
        "replay":{"true":sum(1 for x in rows if x["replay"]),"false":sum(1 for x in rows if not x["replay"])},
    }

    return {
        "version":"discovery-native-v1",
        "query":query,
        "filters":{"kind":kind,"topic":topic,"expert":expert,"event":event,"replay":replay,"review_status":review_status},
        "total":len(filtered),
        "results":filtered,
        "facets":facets,
        "authority":"Promomed canonical tables; search projection is rebuildable",
        "external_index":"not_required_for_mvp",
        "medical_inference":False,
    }


def saved_items(c,email):
    if not email: return []
    return [dict(x) for x in c.execute(
        "SELECT target_kind,target_ref,title,topic,created_at FROM discovery_saves WHERE email=? ORDER BY created_at DESC,target_kind,target_ref LIMIT 50",
        (email,)
    )]
