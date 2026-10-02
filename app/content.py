def snapshot(c):
    row = c.execute("SELECT status,version FROM cms WHERE id='A-014'").fetchone()
    return {
        "speakers": [dict(r) for r in c.execute("SELECT * FROM speakers ORDER BY name")],
        "products": [dict(r) for r in c.execute("SELECT * FROM product_catalog ORDER BY id")],
        "content_catalog": [dict(r) for r in c.execute("SELECT * FROM content_catalog ORDER BY id")],
        "studio_episodes": [dict(r) for r in c.execute(
            "SELECT e.*,s.name speaker_name,s.role speaker_role FROM studio_episodes e LEFT JOIN speakers s ON s.id=e.speaker_id ORDER BY e.id"
        )],
        "cms_status": row["status"],
        "cms_version": row["version"],
    }
