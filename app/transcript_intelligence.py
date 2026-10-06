import time


DEMO_SEGMENTS = [
    ("TS-P21-01","P21","ST01",0,42,"SP06","Почему разговор о весе изменился: важно отделять общественную повестку от индивидуального медицинского решения.","demo_transcript","reviewed_demo"),
    ("TS-P21-02","P21","ST01",42,96,"SP07","Когда мы обсуждаем исследования, нужно отдельно смотреть дизайн, длительность наблюдения и то, какие именно выводы допустимы.","demo_transcript","reviewed_demo"),
    ("TS-P21-03","P21","ST01",96,154,"SP06","Один и тот же результат исследования нельзя автоматически переносить на любого конкретного человека без клинического контекста.","demo_transcript","reviewed_demo"),
    ("TS-P39-01","P39","ST02",0,48,"SP01","Восстановление — это не один показатель. Полезнее смотреть на устойчивые привычки и контекст, а не на один идеальный score.","demo_transcript","reviewed_demo"),
    ("TS-P39-02","P39","ST02",48,104,"SP07","Технологии могут помогать замечать паттерны, но сами по себе не являются диагнозом и не должны создавать ложную уверенность.","demo_transcript","reviewed_demo"),
]

DEMO_TAKEAWAYS = [
    ("GT-P21-01","P21","ST01","Отделять общий контекст от персонального решения","Образовательный вывод: данные и общественная дискуссия не заменяют индивидуальную клиническую оценку.",0,42,"approved_demo","editor@demo.ru"),
    ("GT-P21-02","P21","ST01","Проверять пределы вывода исследования","Нужно смотреть дизайн и границы переносимости результатов, а не только заголовок.",42,96,"approved_demo","editor@demo.ru"),
    ("GT-P39-01","P39","ST02","Не превращать один score в диагноз","Wearable и другие показатели могут быть полезны как наблюдение, но не как самостоятельный медицинский вывод.",48,104,"approved_demo","editor@demo.ru"),
    ("GT-P39-02","P39","ST02","Черновой AI takeaway","Этот takeaway специально оставлен в generated_demo и не должен попадать в публичную выдачу до human review.",0,48,"generated_demo",None),
]


def seed_demo(c):
    now=int(time.time())
    for row in DEMO_SEGMENTS:
        c.execute(
            "INSERT OR IGNORE INTO transcript_segments(id,item_id,studio_id,start_sec,end_sec,speaker_id,text,source_kind,review_status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (*row,now),
        )
    for row in DEMO_TAKEAWAYS:
        reviewer=row[-1]
        reviewed_at=now if reviewer else None
        c.execute(
            "INSERT OR IGNORE INTO generated_takeaways(id,item_id,studio_id,title,body,segment_start_sec,segment_end_sec,status,reviewer,reviewed_at,created_at,demo_only) VALUES(?,?,?,?,?,?,?,?,?,?,?,1)",
            (*row[:-1],reviewer,reviewed_at,now),
        )


def _segments(c,item_id=None):
    if item_id:
        rows=c.execute(
            "SELECT t.id,t.item_id,t.studio_id,t.start_sec,t.end_sec,t.speaker_id,t.text,t.source_kind,t.review_status,s.name speaker_name FROM transcript_segments t LEFT JOIN speakers s ON s.id=t.speaker_id WHERE t.item_id=? ORDER BY t.start_sec,t.id",
            (item_id,),
        )
    else:
        rows=c.execute(
            "SELECT t.id,t.item_id,t.studio_id,t.start_sec,t.end_sec,t.speaker_id,t.text,t.source_kind,t.review_status,s.name speaker_name FROM transcript_segments t LEFT JOIN speakers s ON s.id=t.speaker_id ORDER BY t.item_id,t.start_sec,t.id"
        )
    return [dict(x) for x in rows]


def _takeaways(c,item_id=None,include_unreviewed=False):
    clauses=[]; params=[]
    if item_id:
        clauses.append("item_id=?");params.append(item_id)
    if not include_unreviewed:
        clauses.append("status IN ('approved','approved_demo')")
    where=(" WHERE "+" AND ".join(clauses)) if clauses else ""
    rows=c.execute(
        "SELECT id,item_id,studio_id,title,body,segment_start_sec,segment_end_sec,status,reviewer,reviewed_at,created_at FROM generated_takeaways"+where+" ORDER BY item_id,segment_start_sec,id",
        tuple(params),
    )
    return [dict(x) for x in rows]


def snapshot(c,item_id=None,editor=False):
    segments=_segments(c,item_id)
    takeaways=_takeaways(c,item_id,include_unreviewed=editor)
    return {
        "version":"transcript-intelligence-v1",
        "item_id":item_id,
        "segments":segments,
        "takeaways":takeaways,
        "counts":{
            "segments":len(segments),
            "takeaways":len(takeaways),
            "approved_takeaways":sum(1 for x in takeaways if x["status"] in ("approved","approved_demo")),
            "pending_takeaways":sum(1 for x in takeaways if x["status"] not in ("approved","approved_demo")),
        },
        "publication_rule":"A takeaway is public only after human review and must resolve to an exact transcript time range.",
        "truth_boundary":{
            "demo_transcript":True,
            "ai_generated_source_claim":False,
            "human_review_required":True,
            "automatic_medical_publication":False,
        },
    }


def review_takeaway(c,takeaway_id,action,reviewer):
    row=c.execute("SELECT id,status FROM generated_takeaways WHERE id=?",(takeaway_id,)).fetchone()
    if not row:
        raise ValueError("takeaway_not_found")
    if action not in ("approve_demo","reject_demo"):
        raise ValueError("bad_action")
    status="approved_demo" if action=="approve_demo" else "rejected_demo"
    c.execute(
        "UPDATE generated_takeaways SET status=?,reviewer=?,reviewed_at=? WHERE id=?",
        (status,reviewer,int(time.time()),takeaway_id),
    )
