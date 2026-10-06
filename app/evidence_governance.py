import hashlib
import json
import time
import uuid

STANDARD_VERSION = "promomed-evidence-governance-v1"
ALLOWED_SOURCE_TYPES = {"primary", "guideline", "review", "study", "registry", "institutional", "other"}
ALLOWED_DECISIONS = {"approved", "rejected", "needs_changes"}


def _rowdict(row):
    return dict(row) if row is not None else None


def _canonical_hash(payload):
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def record_review(c, *, content_id, source_type, source_ref, reviewer_email, reviewer_role,
                  disclosure, decision, valid_until=None, source_date=None):
    content = c.execute(
        "SELECT id,title,status,version,author,reviewer,partner FROM content_catalog WHERE id=?",
        (str(content_id),),
    ).fetchone()
    if not content:
        raise ValueError("content_not_found")
    source_type = str(source_type or "").strip().lower()
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise ValueError("source_type_invalid")
    source_ref = str(source_ref or "").strip()
    if len(source_ref) < 3 or len(source_ref) > 1000:
        raise ValueError("source_ref_invalid")
    reviewer_role = str(reviewer_role or "").strip()
    disclosure = str(disclosure or "").strip()
    decision = str(decision or "").strip().lower()
    if len(reviewer_role) < 2:
        raise ValueError("reviewer_role_required")
    if not disclosure:
        raise ValueError("disclosure_required")
    if decision not in ALLOWED_DECISIONS:
        raise ValueError("decision_invalid")
    now = int(time.time())
    if valid_until is not None:
        valid_until = int(valid_until)
        if valid_until <= now:
            raise ValueError("valid_until_must_be_future")
    source_id = "src_" + uuid.uuid4().hex
    review_id = "rev_" + uuid.uuid4().hex
    c.execute(
        """INSERT INTO evidence_sources(id,content_id,content_version,source_type,source_ref,source_date,metadata_json,created_at)
           VALUES(?,?,?,?,?,?,?,?)""",
        (source_id, content["id"], int(content["version"]), source_type, source_ref, source_date, "{}", now),
    )
    c.execute(
        """UPDATE evidence_reviews SET superseded_at=?
           WHERE content_id=? AND content_version=? AND superseded_at IS NULL""",
        (now, content["id"], int(content["version"])),
    )
    c.execute(
        """INSERT INTO evidence_reviews(id,content_id,content_version,source_id,reviewer_email,reviewer_role,
           disclosure,decision,reviewed_at,valid_until,superseded_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,NULL)""",
        (review_id, content["id"], int(content["version"]), source_id, reviewer_email,
         reviewer_role, disclosure, decision, now, valid_until),
    )
    return build_manifest(c, content_id=content["id"], now=now)


def build_manifest(c, *, content_id, now=None):
    now = int(now or time.time())
    content = c.execute(
        "SELECT id,kind,theme,title,author,reviewer,partner,status,version FROM content_catalog WHERE id=?",
        (str(content_id),),
    ).fetchone()
    if not content:
        return None
    sources = [_rowdict(row) for row in c.execute(
        """SELECT id,content_id,content_version,source_type,source_ref,source_date,created_at
           FROM evidence_sources WHERE content_id=? AND content_version=? ORDER BY created_at,id""",
        (content["id"], int(content["version"])),
    )]
    review = _rowdict(c.execute(
        """SELECT id,content_id,content_version,source_id,reviewer_email,reviewer_role,disclosure,
                  decision,reviewed_at,valid_until,superseded_at
           FROM evidence_reviews
           WHERE content_id=? AND content_version=? AND superseded_at IS NULL
           ORDER BY reviewed_at DESC,id DESC LIMIT 1""",
        (content["id"], int(content["version"])),
    ).fetchone())
    seal_status = "missing_review"
    if review:
        if review["decision"] != "approved":
            seal_status = "not_approved"
        elif review["valid_until"] is not None and int(review["valid_until"]) <= now:
            seal_status = "expired"
        elif not sources:
            seal_status = "missing_source"
        elif not str(review["disclosure"] or "").strip():
            seal_status = "missing_disclosure"
        else:
            seal_status = "valid"
    canonical = {
        "standardVersion": STANDARD_VERSION,
        "content": {
            "id": content["id"], "version": int(content["version"]), "kind": content["kind"],
            "theme": content["theme"], "title": content["title"], "author": content["author"],
            "partner": content["partner"], "publicationStatus": content["status"],
        },
        "sources": sources,
        "review": review,
        "seal": {
            "status": seal_status, "valid": seal_status == "valid",
            "reviewedAt": review["reviewed_at"] if review else None,
            "validUntil": review["valid_until"] if review else None,
        },
    }
    return {**canonical, "evidencePackageSha256": _canonical_hash(canonical)}


def verification_projection(manifest):
    if not manifest:
        return None
    return {
        "standardVersion": manifest["standardVersion"],
        "contentId": manifest["content"]["id"],
        "contentVersion": manifest["content"]["version"],
        "title": manifest["content"]["title"],
        "seal": manifest["seal"],
        "evidencePackageSha256": manifest["evidencePackageSha256"],
        "sourceCount": len(manifest["sources"]),
        "reviewDecision": manifest["review"]["decision"] if manifest["review"] else None,
        "disclosurePresent": bool(manifest["review"] and str(manifest["review"]["disclosure"] or "").strip()),
    }
