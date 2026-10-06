import hashlib
import json
import time
from datetime import datetime, timezone

from app import contract_builder


DEMO_OBLIGATIONS = {
    "t50": {
        "m3": [
            {
                "id": "attendance_actuals",
                "title": "Verified attendance actuals",
                "owner": "Event Operations",
                "required_evidence": "Check-in export + attendance reconciliation",
                "seed_status": "accepted_demo",
                "seed_evidence": "demo://checkin-reconciliation",
            },
            {
                "id": "operations_close",
                "title": "Operational close report",
                "owner": "Event Operations",
                "required_evidence": "Incident/recovery ledger + venue/live close report",
                "seed_status": "accepted_demo",
                "seed_evidence": "demo://operations-close",
            },
            {
                "id": "partner_delivery",
                "title": "Partner delivery acceptance",
                "owner": "Commercial Director",
                "required_evidence": "Signed partner delivery acceptance",
                "seed_status": "awaiting",
                "seed_evidence": "",
            },
            {
                "id": "consent_evidence",
                "title": "Consent-first continuation evidence",
                "owner": "CRM / Privacy Owner",
                "required_evidence": "Consent log + allowed continuation actions",
                "seed_status": "accepted_demo",
                "seed_evidence": "demo://consent-ledger",
            },
            {
                "id": "kpi_actuals",
                "title": "Contractual KPI actuals",
                "owner": "Analytics Owner",
                "required_evidence": "KPI actuals using pre-agreed definitions",
                "seed_status": "accepted_demo",
                "seed_evidence": "demo://kpi-actuals",
            },
        ]
    }
}


def _evidence_rows(c):
    try:
        return [dict(r) for r in c.execute(
            "SELECT id,tranche_id,milestone_id,obligation_id,title,document_type,storage_ref,content_sha256,status,owner,registered_by,registered_at,demo_only "
            "FROM deal_evidence_documents ORDER BY registered_at,id"
        )]
    except Exception:
        return []


def _sla_rows(c):
    try:
        return [dict(r) for r in c.execute(
            "SELECT id,tranche_id,milestone_id,obligation_id,owner,due_at,escalation_owner,escalation_level,escalated_at,updated_at,demo_only "
            "FROM deal_obligation_sla ORDER BY due_at,id"
        )]
    except Exception:
        return []


def _payment_rows(c):
    try:
        return [dict(r) for r in c.execute(
            "SELECT id,tranche_id,milestone_id,amount_rub,status,requested_by,requested_at,finance_owner,evidence_packet_hash,payment_authorized,demo_only "
            "FROM deal_payment_requests ORDER BY requested_at,id"
        )]
    except Exception:
        return []


def _iso(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat().replace("+00:00", "Z")


def register_demo_evidence(c, tranche_id, milestone_id, obligation_id, actor, title, document_type, storage_ref):
    allowed = {
        (tid, mid, item["id"]): item
        for tid, mids in DEMO_OBLIGATIONS.items()
        for mid, items in mids.items()
        for item in items
    }
    item = allowed.get((tranche_id, milestone_id, obligation_id))
    if not item:
        raise ValueError("unknown_obligation")
    if not storage_ref.strip():
        raise ValueError("storage_ref_required")
    now = int(time.time())
    digest = hashlib.sha256(storage_ref.strip().encode("utf-8")).hexdigest()
    doc_id = f"doc:{tranche_id}:{milestone_id}:{obligation_id}:{digest[:12]}"
    c.execute(
        "INSERT INTO deal_evidence_documents(id,tranche_id,milestone_id,obligation_id,title,document_type,storage_ref,content_sha256,status,owner,registered_by,registered_at,demo_only) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1) ON CONFLICT(id) DO UPDATE SET title=excluded.title,document_type=excluded.document_type,storage_ref=excluded.storage_ref,content_sha256=excluded.content_sha256,status=excluded.status,registered_by=excluded.registered_by,registered_at=excluded.registered_at",
        (doc_id,tranche_id,milestone_id,obligation_id,title or item["required_evidence"],document_type or "evidence_reference",storage_ref,digest,"registered_demo",item["owner"],actor,now),
    )
    return {"id": doc_id, "sha256": digest}


def create_demo_payment_request(c, actor):
    d = snapshot(c)
    if not d["readiness"]["demo_payment_eligible"]:
        raise ValueError("milestone_not_eligible")
    now = int(time.time())
    packet_hash = d["board_packet"]["packet_hash"]
    req_id = f"payreq:t50:m3:{packet_hash[:12]}"
    c.execute(
        "INSERT INTO deal_payment_requests(id,tranche_id,milestone_id,amount_rub,status,requested_by,requested_at,finance_owner,evidence_packet_hash,payment_authorized,demo_only) "
        "VALUES(?,?,?,?,?,?,?,?,?,0,1) "
        "ON CONFLICT(tranche_id,milestone_id) DO UPDATE SET id=excluded.id,status=excluded.status,requested_by=excluded.requested_by,requested_at=excluded.requested_at,finance_owner=excluded.finance_owner,evidence_packet_hash=excluded.evidence_packet_hash,payment_authorized=0,demo_only=1",
        (req_id,"t50","m3",d["deal"]["amount_rub"],"finance_review_demo",actor,now,"Finance",packet_hash),
    )
    return req_id


def _rows(c):
    try:
        return [dict(r) for r in c.execute(
            "SELECT id,tranche_id,milestone_id,obligation_id,owner,status,evidence_ref,note,accepted_by,accepted_at,updated_at,demo_only "
            "FROM deal_obligation_records ORDER BY tranche_id,milestone_id,obligation_id"
        )]
    except Exception:
        return []


def _issues(c):
    try:
        return [dict(r) for r in c.execute(
            "SELECT id,tranche_id,milestone_id,obligation_id,severity,title,status,remediation,owner,created_by,created_at,resolved_by,resolved_at,demo_only "
            "FROM deal_issues ORDER BY created_at,id"
        )]
    except Exception:
        return []


def seed_demo_case(c, actor="system"):
    now = int(time.time())
    for tranche_id, milestones in DEMO_OBLIGATIONS.items():
        for milestone_id, obligations in milestones.items():
            for item in obligations:
                rec_id = f"{tranche_id}:{milestone_id}:{item['id']}"
                accepted = item["seed_status"] == "accepted_demo"
                c.execute(
                    "INSERT INTO deal_obligation_records(id,tranche_id,milestone_id,obligation_id,owner,status,evidence_ref,note,accepted_by,accepted_at,updated_at,demo_only) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,1) ON CONFLICT(tranche_id,milestone_id,obligation_id) DO NOTHING",
                    (
                        rec_id,
                        tranche_id,
                        milestone_id,
                        item["id"],
                        item["owner"],
                        item["seed_status"],
                        item["seed_evidence"],
                        "Seeded presentation case",
                        actor if accepted else None,
                        now if accepted else None,
                        now,
                    ),
                )
            partner = next(x for x in obligations if x["id"] == "partner_delivery")
            due_at = now + 3 * 24 * 60 * 60
            sla_id = f"sla:{tranche_id}:{milestone_id}:partner_delivery"
            c.execute(
                "INSERT INTO deal_obligation_sla(id,tranche_id,milestone_id,obligation_id,owner,due_at,escalation_owner,escalation_level,escalated_at,updated_at,demo_only) "
                "VALUES(?,?,?,?,?,?,?,'none',NULL,?,1) ON CONFLICT(tranche_id,milestone_id,obligation_id) DO NOTHING",
                (sla_id,tranche_id,milestone_id,partner["id"],partner["owner"],due_at,"Executive Sponsor",now),
            )
            issue_id = f"issue:{tranche_id}:{milestone_id}:partner_delivery"
            c.execute(
                "INSERT INTO deal_issues(id,tranche_id,milestone_id,obligation_id,severity,title,status,remediation,owner,created_by,created_at,resolved_by,resolved_at,demo_only) "
                "VALUES(?,?,?,?,?,'Partner acceptance missing','open',?,?,?, ?,NULL,NULL,1) ON CONFLICT(id) DO NOTHING",
                (
                    issue_id,
                    tranche_id,
                    milestone_id,
                    partner["id"],
                    "high",
                    "Obtain signed partner delivery acceptance and attach the reference.",
                    partner["owner"],
                    actor,
                    now,
                ),
            )


def reset_demo(c, actor="system"):
    c.execute("DELETE FROM deal_payment_requests WHERE demo_only=1")
    c.execute("DELETE FROM deal_evidence_documents WHERE demo_only=1")
    c.execute("DELETE FROM deal_obligation_sla WHERE demo_only=1")
    c.execute("DELETE FROM deal_issues WHERE demo_only=1")
    c.execute("DELETE FROM deal_obligation_records WHERE demo_only=1")
    seed_demo_case(c, actor)


def attach_and_accept_demo(c, tranche_id, milestone_id, obligation_id, actor, evidence_ref, note=""):
    allowed = {
        (tid, mid, item["id"]): item
        for tid, mids in DEMO_OBLIGATIONS.items()
        for mid, items in mids.items()
        for item in items
    }
    item = allowed.get((tranche_id, milestone_id, obligation_id))
    if not item:
        raise ValueError("unknown_obligation")
    if not evidence_ref.strip():
        raise ValueError("evidence_required")
    now = int(time.time())
    rec_id = f"{tranche_id}:{milestone_id}:{obligation_id}"
    c.execute(
        "INSERT INTO deal_obligation_records(id,tranche_id,milestone_id,obligation_id,owner,status,evidence_ref,note,accepted_by,accepted_at,updated_at,demo_only) "
        "VALUES(?,?,?,?,?,'accepted_demo',?,?,?,?,?,1) "
        "ON CONFLICT(tranche_id,milestone_id,obligation_id) DO UPDATE SET status='accepted_demo',evidence_ref=excluded.evidence_ref,note=excluded.note,accepted_by=excluded.accepted_by,accepted_at=excluded.accepted_at,updated_at=excluded.updated_at,demo_only=1",
        (rec_id, tranche_id, milestone_id, obligation_id, item["owner"], evidence_ref, note, actor, now, now),
    )
    c.execute(
        "UPDATE deal_issues SET status='resolved_demo',remediation=?,resolved_by=?,resolved_at=? "
        "WHERE tranche_id=? AND milestone_id=? AND obligation_id=? AND status='open' AND demo_only=1",
        (f"Evidence accepted: {evidence_ref}", actor, now, tranche_id, milestone_id, obligation_id),
    )
    c.execute(
        "UPDATE deal_obligation_sla SET escalation_level='resolved',updated_at=? "
        "WHERE tranche_id=? AND milestone_id=? AND obligation_id=? AND demo_only=1",
        (now,tranche_id,milestone_id,obligation_id),
    )


def _obligation_projection(c, tranche_id, milestone_id):
    seed_demo_case(c)
    rows = {
        (r["tranche_id"], r["milestone_id"], r["obligation_id"]): r
        for r in _rows(c)
    }
    definitions = DEMO_OBLIGATIONS.get(tranche_id, {}).get(milestone_id, [])
    items = []
    for d in definitions:
        r = rows.get((tranche_id, milestone_id, d["id"]))
        items.append({
            "id": d["id"],
            "title": d["title"],
            "owner": d["owner"],
            "required_evidence": d["required_evidence"],
            "status": r["status"] if r else "awaiting",
            "evidence_ref": r["evidence_ref"] if r else "",
            "accepted_by": r["accepted_by"] if r else None,
            "accepted_at": r["accepted_at"] if r else None,
            "demo_only": True,
        })
    return items


def snapshot(c):
    seed_demo_case(c)
    contract = contract_builder.snapshot(c)
    p50 = next(x for x in contract["packages"] if x["id"] == "t50")
    m3 = next(x for x in p50["payment_milestones"] if x["id"] == "m3")
    obligations = _obligation_projection(c, "t50", "m3")
    issues = [
        x for x in _issues(c)
        if x["tranche_id"] == "t50" and x["milestone_id"] == "m3"
    ]
    open_issues = [x for x in issues if x["status"] == "open"]
    evidence_docs = [
        x for x in _evidence_rows(c)
        if x["tranche_id"] == "t50" and x["milestone_id"] == "m3"
    ]
    sla_rows = [
        x for x in _sla_rows(c)
        if x["tranche_id"] == "t50" and x["milestone_id"] == "m3"
    ]
    payment_requests = [
        x for x in _payment_rows(c)
        if x["tranche_id"] == "t50" and x["milestone_id"] == "m3"
    ]
    accepted_count = sum(1 for x in obligations if x["status"] == "accepted_demo")
    required_count = len(obligations)
    evidence_complete = required_count > 0 and accepted_count == required_count
    demo_payment_eligible = evidence_complete and not open_issues

    packet_payload = {
        "tranche": "t50",
        "milestone": "m3",
        "accepted_count": accepted_count,
        "required_count": required_count,
        "open_issue_ids": [x["id"] for x in open_issues],
        "payment_amount_rub": m3["amount_rub"],
        "demo_payment_eligible": demo_payment_eligible,
    }
    packet_hash = hashlib.sha256(
        json.dumps(packet_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    return {
        "version": "pilot-deal-room-v1",
        "deal": {
            "tranche_id": "t50",
            "milestone_id": "m3",
            "title": m3["title"],
            "amount_rub": m3["amount_rub"],
            "share_pct": m3["share_pct"],
            "responsible": m3["responsible"],
            "payment_rule": m3["payment_rule"],
            "stop_go": m3["stop_go"],
        },
        "obligations": obligations,
        "issues": issues,
        "evidence_registry": [
            {
                **x,
                "registered_at_iso": _iso(x["registered_at"]),
            }
            for x in evidence_docs
        ],
        "owner_inbox": [
            {
                "obligation_id": x["obligation_id"],
                "title": next((o["title"] for o in obligations if o["id"] == x["obligation_id"]), x["obligation_id"]),
                "owner": x["owner"],
                "due_at": x["due_at"],
                "due_at_iso": _iso(x["due_at"]),
                "days_remaining": max(0, (int(x["due_at"]) - int(time.time()) + 86399) // 86400),
                "escalation_owner": x["escalation_owner"],
                "escalation_level": x["escalation_level"],
                "status": next((o["status"] for o in obligations if o["id"] == x["obligation_id"]), "awaiting"),
                "required_evidence": next((o["required_evidence"] for o in obligations if o["id"] == x["obligation_id"]), ""),
            }
            for x in sla_rows
        ],
        "payment_requests": [
            {
                **x,
                "requested_at_iso": _iso(x["requested_at"]),
                "payment_authorized": bool(x["payment_authorized"]),
            }
            for x in payment_requests
        ],
        "readiness": {
            "accepted_count": accepted_count,
            "required_count": required_count,
            "open_issue_count": len(open_issues),
            "evidence_complete": evidence_complete,
            "demo_payment_eligible": demo_payment_eligible,
            "actual_payment_authorized": False,
            "state": "ELIGIBLE_DEMO_PREVIEW" if demo_payment_eligible else "BLOCKED",
            "reason": (
                "All demo obligations accepted and no open demo issues remain."
                if demo_payment_eligible
                else "Payment remains blocked until every required obligation is accepted and all blocking issues are resolved."
            ),
        },
        "board_packet": {
            "packet_id": f"pilot-board-{packet_hash[:12]}",
            "packet_hash": packet_hash,
            "decision_preview": "GO_TO_FINANCE_REVIEW" if demo_payment_eligible else "HOLD",
            "payment_amount_rub": m3["amount_rub"],
            "accepted_obligations": accepted_count,
            "required_obligations": required_count,
            "open_issues": len(open_issues),
            "included_sections": [
                "Contract scope reference",
                "Milestone obligation matrix",
                "Evidence references",
                "Issue / remediation log",
                "Payment readiness",
                "STOP / GO recommendation",
            ],
            "legal_effect": "NONE",
            "payment_authority": "NONE",
            "export": {
                "format": "json/text-preview",
                "filename": f"promomed-pilot-board-{packet_hash[:12]}.json",
                "ready": True,
                "payload": packet_payload,
            },
        },
        "truth_boundary": {
            "demo_only": True,
            "evidence_uploads_are_references_only": True,
            "actual_payment_authorized": False,
            "binding_acceptance": False,
            "note": "The Deal Room demonstrates workflow and control logic. Production use requires approved document storage, legal acceptance policy, authorized identities and payment authority integration.",
        },
    }
