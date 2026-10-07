def read(c):
    return {
        "ok":True,
        "version":"v1.5",
        "contract":"product-quality",
        "counts":{
            "products":c.execute("SELECT COUNT(*) n FROM product_catalog").fetchone()["n"],
            "materials":c.execute("SELECT COUNT(*) n FROM content_catalog").fetchone()["n"],
            "speakers":c.execute("SELECT COUNT(*) n FROM speakers").fetchone()["n"],
            "partner_packages":c.execute("SELECT COUNT(*) n FROM partner_packages").fetchone()["n"],
            "program_items":c.execute("SELECT COUNT(*) n FROM program_items").fetchone()["n"],
            "session_speaker_links":c.execute("SELECT COUNT(*) n FROM session_speakers").fetchone()["n"],
        },
        "required_ids":{
            "products":[r["id"] for r in c.execute("SELECT id FROM product_catalog ORDER BY id")],
            "materials":[r["id"] for r in c.execute("SELECT id FROM content_catalog ORDER BY id")],
            "packages":[r["id"] for r in c.execute("SELECT id FROM partner_packages ORDER BY id")],
        },
        "surfaces":["premium_home","topic_hubs","media_catalog","product_detail","speaker_profile","rich_session_detail","studio","partner_marketplace"],
        "disclosure":"real Promomed product context is separated from demo partner content",
    }
