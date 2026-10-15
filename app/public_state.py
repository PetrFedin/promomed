"""Anonymous public-state projection with explicit hash-bound publication admission.

Nothing becomes public because it exists in a canonical table. Each returned
artifact must have an active admission for the exact public payload hash and no
active publication hold. This module does not create admissions.
"""
import hashlib
import json
from urllib.parse import urlparse

from app import db

ROUTE = "/api/public-state/v1"

CONTENT_FIELDS = (
    "id", "kind", "theme", "title", "dek", "duration", "author", "partner",
)
EVENT_FIELDS = (
    "id", "start", "end", "venue", "track", "format", "title",
    "audience", "capacity", "stream", "replay", "partner",
)


def _canonical(kind, row):
    fields = CONTENT_FIELDS if kind == "content" else EVENT_FIELDS
    payload = {field: row[field] for field in fields}
    return payload


def payload_sha256(kind, row):
    raw = json.dumps(
        _canonical(kind, row),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _held(c, kind, ref):
    try:
        return bool(c.execute(
            "SELECT 1 FROM publication_holds "
            "WHERE artifact_kind=? AND artifact_ref=? AND status='active' LIMIT 1",
            (kind, ref),
        ).fetchone())
    except Exception:
        # Missing/invalid hold authority cannot be interpreted as approval.
        return True


def _admission(c, kind, ref, digest):
    row = c.execute(
        "SELECT reviewer_ref,source_ref,admitted_at,demo_only "
        "FROM public_artifact_admissions "
        "WHERE artifact_kind=? AND artifact_ref=? AND payload_sha256=? "
        "AND status='admitted' LIMIT 1",
        (kind, ref, digest),
    ).fetchone()
    if row is None:
        return None
    if not db.demo_seed_enabled() and int(row["demo_only"] or 0) != 0:
        return None
    return dict(row)


def _publishable(c, kind, row):
    ref = str(row["id"])
    if _held(c, kind, ref):
        return None
    digest = payload_sha256(kind, row)
    admission = _admission(c, kind, ref, digest)
    if admission is None:
        return None
    return {
        **_canonical(kind, row),
        "publication": {
            "payloadSha256": digest,
            "reviewerRef": admission["reviewer_ref"],
            "sourceRef": admission["source_ref"],
            "admittedAt": admission["admitted_at"],
        },
    }


def snapshot(c):
    content = []
    for row in c.execute(
        "SELECT id,kind,theme,title,dek,duration,author,partner,status "
        "FROM content_catalog WHERE status='published' ORDER BY id"
    ):
        public = _publishable(c, "content", row)
        if public is not None:
            content.append(public)

    agenda = []
    for row in c.execute(
        'SELECT id,start,"end",venue,track,format,title,audience,capacity,'
        "stream,replay,partner FROM program_items ORDER BY start,venue,id"
    ):
        public = _publishable(c, "event", row)
        if public is not None:
            agenda.append(public)

    return {
        "version": "public-state-v1",
        "content": content,
        "agenda": agenda,
        "counts": {"content": len(content), "agenda": len(agenda)},
        "truthBoundary": {
            "explicitAdmissionRequired": True,
            "exactPayloadHashRequired": True,
            "publicationHoldFailClosed": True,
            "personalData": False,
            "globalCommercialKpi": False,
            "attendanceOrRetention": False,
            "medicalInference": False,
        },
    }


def serve(raw_path):
    parsed = urlparse(raw_path)
    if parsed.path != ROUTE:
        return None
    if parsed.query or parsed.fragment:
        return {"error": "unsupported_query"}, 422
    c = db.connect()
    try:
        return snapshot(c), 200
    finally:
        c.close()
