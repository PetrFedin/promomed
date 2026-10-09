import hashlib
import json
import time

from app import corporate, institutional_followup_board

VERSION = "promomed-institutional-diligence-command-center-v1"


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(item):
    return " ".join(
        str(item.get(key) or "")
        for key in ("id", "title", "category", "owner", "rationale")
    ).lower()


def _domains(item):
    text = _text(item)
    category = str(item.get("category") or "").lower()
    domains = set()

    if item.get("blocksPilot") or category in (
        "pilot",
        "institution",
        "authority",
        "technical",
        "governance",
    ):
        domains.add("pilot")
    if category in ("commercial", "operations") or any(
        token in text for token in ("procurement", "commercial", "purchase order", "vendor")
    ):
        domains.add("procurement")
    if category in ("commercial", "operations", "privacy", "governance") or any(
        token in text for token in ("legal", "contract", "dpa", "sla", "retention", "deletion", "terms")
    ):
        domains.add("legal")
    if category in ("security", "privacy", "technical") or any(
        token in text
        for token in (
            "security",
            "privacy",
            "encryption",
            "sbom",
            "cve",
            "incident",
            "siem",
            "data categories",
        )
    ):
        domains.add("security")

    if not domains:
        domains.add("pilot" if item.get("required") else "procurement")
    return sorted(domains)


def _domain_view(items, domain):
    rows = [item for item in items if domain in _domains(item)]
    blockers = [item for item in rows if item["state"] in ("REQUESTED", "GAP")]
    ready = [item for item in rows if item["state"] == "READY_FOR_DECISION"]
    return {
        "domain": domain,
        "status": "BLOCKED" if blockers else ("READY_FOR_DECISION" if ready else "NO_ACTIVE_ITEMS"),
        "blockerCount": len(blockers),
        "readyForDecisionCount": len(ready),
        "blockers": [
            {
                "id": item["id"],
                "title": item["title"],
                "owner": item.get("nextOwner") or item.get("owner"),
                "state": item["state"],
                "blocksPilot": bool(item.get("blocksPilot")),
                "rationale": item.get("rationale"),
            }
            for item in blockers
        ],
        "readyForDecision": [
            {
                "id": item["id"],
                "title": item["title"],
                "owner": item.get("nextOwner") or item.get("owner"),
                "state": item["state"],
            }
            for item in ready
        ],
    }


def _owner_queue(items):
    grouped = {}
    for item in items:
        if item["state"] not in ("REQUESTED", "GAP", "READY_FOR_DECISION"):
            continue
        owner = item.get("nextOwner") or item.get("owner") or "Unassigned"
        row = grouped.setdefault(
            owner,
            {"owner": owner, "blocking": 0, "readyForDecision": 0, "items": []},
        )
        if item["state"] in ("REQUESTED", "GAP"):
            row["blocking"] += 1
        if item["state"] == "READY_FOR_DECISION":
            row["readyForDecision"] += 1
        row["items"].append(
            {
                "id": item["id"],
                "title": item["title"],
                "state": item["state"],
                "dueClass": item.get("dueClass"),
                "blocksPilot": bool(item.get("blocksPilot")),
            }
        )
    return sorted(
        grouped.values(),
        key=lambda row: (-row["blocking"], -row["readyForDecision"], row["owner"]),
    )


def _matches_stage(item, stage_id):
    if item["id"] == "participation_acceptance":
        return False
    text = _text(item)
    item_id = item["id"]

    if stage_id == "institution_authority":
        return item_id in ("org_identity", "admin_nomination") or any(
            token in text
            for token in (
                "institution identity",
                "institution_identity",
                "administrator",
                "operator",
                "membership",
                "institution role",
                "human authority",
            )
        )
    if stage_id == "technical_scope":
        return item_id in ("integration_map", "success_criteria") or any(
            token in text
            for token in (
                "qualification",
                "public key",
                "trust key",
                "interop",
                "endpoint",
                "delivery runtime",
                "portable evidence",
                "integration",
                "pilot scope",
                "success criteria",
            )
        )
    if stage_id == "security_privacy":
        return item_id in ("security_questionnaire", "data_categories") or any(
            token in text
            for token in (
                "security",
                "privacy",
                "encryption",
                "incident",
                "siem",
                "retention",
                "deletion",
                "data categories",
            )
        )
    if stage_id == "legal_sla":
        return item_id == "sla_expectations" or any(
            token in text
            for token in (
                "legal",
                "dpa",
                "sla",
                "contract terms",
                "commercial / legal",
                "vendor terms",
                "subprocessor",
            )
        )
    if stage_id == "procurement_commercial":
        return item_id == "commercial_process" or any(
            token in text
            for token in (
                "procurement",
                "commercial process",
                "commercial handoff",
                "purchase order",
            )
        )
    return False


def _stage(stage_id, title, items, parallelizable=True):
    rows = [item for item in items if _matches_stage(item, stage_id)]
    blockers = [item for item in rows if item["state"] in ("REQUESTED", "GAP")]
    ready = [item for item in rows if item["state"] == "READY_FOR_DECISION"]
    status = "BLOCKED" if blockers else ("READY_FOR_DECISION" if ready else "NO_ACTIVE_ITEMS")
    return {
        "id": stage_id,
        "title": title,
        "status": status,
        "hardStop": False,
        "parallelizable": bool(parallelizable),
        "blockingItemIds": [item["id"] for item in blockers],
        "readyForDecisionItemIds": [item["id"] for item in ready],
        "nextOwners": sorted(
            {
                item.get("nextOwner") or item.get("owner") or "Unassigned"
                for item in blockers
            }
        ),
    }


def snapshot(c, organization_id, now=None):
    now = int(now or time.time())
    board = institutional_followup_board.snapshot(c, organization_id, now=now)
    corp = corporate.snapshot(c)
    items = board["items"]

    domains = {
        name: _domain_view(items, name)
        for name in ("pilot", "procurement", "legal", "security")
    }
    ready_items = [
        {
            "id": item["id"],
            "title": item["title"],
            "owner": item.get("nextOwner") or item.get("owner"),
            "category": item.get("category"),
            "state": item["state"],
            "approved": False,
        }
        for item in items
        if item["state"] == "READY_FOR_DECISION"
    ]

    participation = next(
        (item for item in items if item["id"] == "participation_acceptance"),
        None,
    )
    participation_missing = (
        not participation or participation["state"] != "READY_FOR_DECISION"
    )

    critical_path = [
        _stage(
            "institution_authority",
            "Institution identity & authority",
            items,
            parallelizable=False,
        ),
        _stage(
            "technical_scope",
            "Pilot scope & technical readiness",
            items,
        ),
        _stage(
            "security_privacy",
            "Security & privacy disposition",
            items,
        ),
        _stage(
            "legal_sla",
            "Legal, DPA & SLA terms",
            items,
        ),
        _stage(
            "procurement_commercial",
            "Procurement & commercial handoff",
            items,
        ),
        {
            "id": "participation_acceptance",
            "title": "External Participation Acceptance",
            "status": "BLOCKED" if participation_missing else "READY_FOR_DECISION",
            "hardStop": True,
            "parallelizable": False,
            "blockingItemIds": ["participation_acceptance"] if participation_missing else [],
            "readyForDecisionItemIds": []
            if participation_missing
            else ["participation_acceptance"],
            "nextOwners": ["Institution + Promomed governance"]
            if participation_missing
            else [],
        },
    ]

    parallel_tracks = [
        {
            "id": "technical",
            "title": "Technical & integration",
            "canProceedInParallel": True,
            "owners": sorted(
                {
                    item.get("nextOwner") or item.get("owner")
                    for item in items
                    if "pilot" in _domains(item) or "security" in _domains(item)
                }
                - {None}
            ),
            "blockingItemIds": [
                item["id"]
                for item in items
                if item["state"] in ("REQUESTED", "GAP")
                and ("pilot" in _domains(item) or "security" in _domains(item))
            ],
        },
        {
            "id": "security_legal",
            "title": "Security, privacy & legal",
            "canProceedInParallel": True,
            "owners": sorted(
                {
                    item.get("nextOwner") or item.get("owner")
                    for item in items
                    if "security" in _domains(item) or "legal" in _domains(item)
                }
                - {None}
            ),
            "blockingItemIds": [
                item["id"]
                for item in items
                if item["state"] in ("REQUESTED", "GAP")
                and ("security" in _domains(item) or "legal" in _domains(item))
            ],
        },
        {
            "id": "commercial",
            "title": "Procurement & commercial",
            "canProceedInParallel": True,
            "owners": sorted(
                {
                    item.get("nextOwner") or item.get("owner")
                    for item in items
                    if "procurement" in _domains(item)
                }
                - {None}
            ),
            "blockingItemIds": [
                item["id"]
                for item in items
                if item["state"] in ("REQUESTED", "GAP")
                and "procurement" in _domains(item)
            ],
        },
    ]

    blockers = [item for item in items if item["state"] in ("REQUESTED", "GAP")]
    hard_stops = [
        stage
        for stage in critical_path
        if stage["hardStop"] and stage["status"] == "BLOCKED"
    ]
    if hard_stops:
        verdict = "HARD_STOP_PARTICIPATION_ACCEPTANCE_MISSING"
    elif blockers:
        verdict = "BLOCKED_BY_DILIGENCE_GAPS"
    elif ready_items:
        verdict = "READY_FOR_DECISION_NOT_APPROVED"
    else:
        verdict = "NO_ACTIVE_DEAL_EVIDENCE"

    impossible_without_participation = [
        "record a real institutional pilot commitment",
        "convert READY_FOR_DECISION into APPROVED",
        "activate production pilot participation",
        "claim signed contract, purchase order, revenue or market traction",
        "represent a demo organisation as external adoption",
    ]

    executive_summary = {
        "verdict": verdict,
        "blockingItems": len(blockers),
        "readyForDecisionItems": len(ready_items),
        "hardStops": len(hard_stops),
        "primaryBlocker": "External Participation Acceptance"
        if participation_missing
        else (blockers[0]["title"] if blockers else None),
        "nextOwner": "Institution + Promomed governance"
        if participation_missing
        else (
            (blockers[0].get("nextOwner") or blockers[0].get("owner"))
            if blockers
            else None
        ),
        "productionRuntimeReady": bool(
            (corp.get("runtime") or {}).get("production_ready")
        ),
    }

    export_body = {
        "version": VERSION,
        "organization": board["organization"],
        "executiveSummary": executive_summary,
        "domains": domains,
        "readyForDecision": ready_items,
        "ownerQueue": _owner_queue(items),
        "criticalPath": critical_path,
        "parallelTracks": parallel_tracks,
        "impossibleWithoutParticipation": impossible_without_participation,
        "followupBoardExportSha256": board["export"]["sha256"],
        "truthBoundary": {
            "readOnly": True,
            "readyForDecisionEqualsApproved": False,
            "criticalPathIsProjection": True,
            "parallelTracksArePlanningOnly": True,
            "approvalAuthorityImplemented": False,
            "participationAcceptanceAuthorityImplemented": False,
        },
    }

    return {
        "version": VERSION,
        "generatedAt": now,
        "organization": board["organization"],
        "executiveSummary": executive_summary,
        "domains": domains,
        "readyForDecision": ready_items,
        "ownerQueue": _owner_queue(items),
        "criticalPath": critical_path,
        "parallelTracks": parallel_tracks,
        "impossibleWithoutParticipation": impossible_without_participation,
        "export": {"sha256": _sha(export_body), "document": export_body},
        "truthBoundary": {
            "readOnly": True,
            "readyForDecisionEqualsApproved": False,
            "criticalPathIsProjection": True,
            "parallelTracksArePlanningOnly": True,
            "approvalPersistedHere": False,
            "externalParticipationAcceptance": "GATED",
            "contractOrRevenueClaimed": False,
            "realPilotClaimed": False,
        },
    }
