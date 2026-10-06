from urllib.parse import parse_qs, urlparse

from app import discovery, db


def read(c, raw_path, role, email):
    parsed = urlparse(raw_path)
    if parsed.path not in ("/api/discovery", "/api/discovery/saved"):
        return None
    if parsed.path == "/api/discovery/saved":
        if role != "participant" or not email:
            return {"error": "forbidden"}, 403
        return {"saved": discovery.saved_items(c, email)}, 200

    q = parse_qs(parsed.query)
    replay_raw = (q.get("replay") or [""])[0].strip().lower()
    replay = None if replay_raw == "" else replay_raw in ("1", "true", "yes", "on")
    limit_raw = (q.get("limit") or ["30"])[0]
    try:
        limit = int(limit_raw)
    except Exception:
        limit = 30

    return discovery.search(
        c,
        query=(q.get("q") or [""])[0][:160],
        kind=(q.get("kind") or [""])[0][:30],
        topic=(q.get("topic") or [""])[0][:120],
        expert=(q.get("expert") or [""])[0][:120],
        event=(q.get("event") or [""])[0][:40],
        replay=replay,
        review_status=(q.get("review_status") or [""])[0][:60],
        limit=limit,
        email=email if role == "participant" else None,
    ), 200


def serve(raw_path, role, email):
    c = db.connect()
    try:
        return read(c, raw_path, role, email)
    finally:
        c.close()
