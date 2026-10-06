def _held(c,kind,ref):
    try:
        row=c.execute("SELECT reason FROM publication_holds WHERE artifact_kind=? AND artifact_ref=? AND status='active' ORDER BY placed_at DESC LIMIT 1",(kind,ref)).fetchone()
        return (True,row["reason"]) if row else (False,"")
    except Exception:
        return False,""


def snapshot(c):
    row = c.execute("SELECT status,version FROM cms WHERE id='A-014'").fetchone()
    return {
        "speakers": [dict(r) for r in c.execute("SELECT * FROM speakers ORDER BY name")],
        "products": [dict(r)|{"publication_hold":_held(c,"product",r["id"])[0],"publication_hold_reason":_held(c,"product",r["id"])[1]} for r in c.execute("SELECT * FROM product_catalog ORDER BY id")],
        "content_catalog": [dict(r)|{"publication_hold":_held(c,"content",r["id"])[0],"publication_hold_reason":_held(c,"content",r["id"])[1]} for r in c.execute("SELECT * FROM content_catalog ORDER BY id")],
        "studio_episodes": [dict(r) for r in c.execute(
            "SELECT e.*,s.name speaker_name,s.role speaker_role FROM studio_episodes e LEFT JOIN speakers s ON s.id=e.speaker_id ORDER BY e.id"
        )],
        "cms_status": row["status"] if row else "unconfigured",
        "cms_version": row["version"] if row else 0,
    }
