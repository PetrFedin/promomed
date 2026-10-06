from urllib.parse import parse_qs, urlparse

from app import db, transcript_intelligence


def serve(raw_path, role):
    parsed=urlparse(raw_path)
    if parsed.path!="/api/transcript-intelligence":
        return None
    q=parse_qs(parsed.query)
    item=(q.get("item_id") or [""])[0][:40] or None
    c=db.connect()
    try:
        return transcript_intelligence.snapshot(c,item_id=item,editor=role=="editor"),200
    finally:
        c.close()
