import hashlib
import json
import time

from app import institutional_working_session

VERSION="promomed-institutional-diligence-followup-board-v1"
ALLOWED_STATES=("REQUESTED","RECEIVED","UNDER_REVIEW","GAP","READY_FOR_DECISION")


def _canonical(v):
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)


def _sha(v):
    return hashlib.sha256(_canonical(v).encode("utf-8")).hexdigest()


def _due_class(category,required,state):
    if state=="GAP":
        return "urgent"
    if required:
        return "standard"
    if category in ("Security","Privacy","Commercial","Governance"):
        return "standard_if_applicable"
    return "optional"


def _board_state(request,room):
    req_id=request["id"]
    if req_id=="participation_acceptance":
        return "GAP","External Participation Acceptance remains gated."

    related=[]
    for item in room.get("gapOwnership") or []:
        text=((item.get("title") or "")+" "+(item.get("blocker") or "")).lower()
        tokens={
            "org_identity":["identity"],
            "admin_nomination":["administrator","operator","membership"],
            "integration_map":["integration","endpoint","interop"],
            "security_questionnaire":["security"],
            "data_categories":["privacy","data"],
            "sla_expectations":["sla","support"],
            "success_criteria":["success","criteria"],
            "commercial_process":["commercial","procurement"],
        }.get(req_id,[])
        if any(t in text for t in tokens):
            related.append(item)

    if related:
        return "GAP","Existing canonical readiness/procurement evidence still shows an unresolved gap."

    # v1 deliberately does not infer receipt/review from a workshop click.
    # If no canonical unresolved gap exists, the item is ready to be considered by the appropriate authority.
    if request.get("required"):
        return "READY_FOR_DECISION","No unresolved canonical gap matched this request; decision still requires external authority."
    return "REQUESTED","Optional/conditional evidence has no canonical receipt or review record."


def snapshot(c,organization_id,now=None):
    now=int(now or time.time())
    room=institutional_working_session.snapshot(c,organization_id,now=now)

    items=[]
    for request in room["documentRequests"]:
        state,rationale=_board_state(request,room)
        item={
            "id":request["id"],
            "title":request["title"],
            "category":request["category"],
            "owner":request["owner"],
            "required":bool(request["required"]),
            "state":state,
            "dueClass":_due_class(request["category"],bool(request["required"]),state),
            "blocksPilot": bool(request["required"]) and state in ("REQUESTED","GAP"),
            "nextOwner":request["owner"],
            "evidenceReference":None,
            "rationale":rationale,
            "canMarkReceivedHere":False,
            "canStartReviewHere":False,
            "canApproveHere":False,
        }
        items.append(item)

    for gap in room.get("gapOwnership") or []:
        gid="gap:"+gap["id"]
        if any(x["id"]==gid for x in items):
            continue
        items.append({
            "id":gid,
            "title":gap.get("title") or gap["id"],
            "category":"Evidence gap",
            "owner":gap.get("owner"),
            "required":True,
            "state":"GAP",
            "dueClass":"urgent",
            "blocksPilot":True,
            "nextOwner":gap.get("owner"),
            "evidenceReference":None,
            "rationale":gap.get("blocker"),
            "canMarkReceivedHere":False,
            "canStartReviewHere":False,
            "canApproveHere":False,
        })

    counts={state:sum(1 for x in items if x["state"]==state) for state in ALLOWED_STATES}
    blocking=sum(1 for x in items if x["blocksPilot"])

    columns=[
        {"state":"REQUESTED","meaning":"Evidence/action requested; no canonical receipt exists."},
        {"state":"RECEIVED","meaning":"Reserved for canonical receipt evidence; v1 board cannot create it."},
        {"state":"UNDER_REVIEW","meaning":"Reserved for canonical review disposition; v1 board cannot create it."},
        {"state":"GAP","meaning":"Canonical evidence shows a missing or unresolved requirement."},
        {"state":"READY_FOR_DECISION","meaning":"Enough evidence is visible to route for decision; this is not approval."},
    ]

    export_body={
        "version":VERSION,
        "organization":room["organization"],
        "columns":columns,
        "items":items,
        "counts":counts,
        "blockingPilotItems":blocking,
        "workingSessionExportSha256":room["export"]["sha256"],
        "truthBoundary":{
            "readOnly":True,
            "readyForDecisionEqualsApproved":False,
            "documentReceiptAuthorityImplemented":False,
            "reviewDispositionAuthorityImplemented":False,
            "participationAcceptanceAuthorityImplemented":False,
        },
    }

    return {
        "version":VERSION,
        "generatedAt":now,
        "organization":room["organization"],
        "columns":columns,
        "items":items,
        "summary":{
            "counts":counts,
            "blockingPilotItems":blocking,
            "totalItems":len(items),
        },
        "export":{"sha256":_sha(export_body),"document":export_body},
        "truthBoundary":{
            "readOnly":True,
            "readyForDecisionEqualsApproved":False,
            "documentReceiptPersistedHere":False,
            "reviewDispositionPersistedHere":False,
            "approvalPersistedHere":False,
            "externalParticipationAcceptance":"GATED",
            "realPilotClaimed":False,
        },
    }
