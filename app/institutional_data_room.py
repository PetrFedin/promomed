import hashlib
import json
import time

from app import institutional_onboarding

ROOM_VERSION="promomed-institutional-working-session-data-room-v1"


def _canonical(v):
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)


def _sha(v):
    return hashlib.sha256(_canonical(v).encode("utf-8")).hexdigest()


def snapshot(c,organization_id,now=None):
    now=int(now or time.time())
    onboarding=institutional_onboarding.snapshot(c,organization_id,now=now)
    procurement=onboarding["procurementEvidencePack"]
    readiness=onboarding["readiness"]

    artifacts=[
        {
            "id":"institution_readiness",
            "title":"Institutional readiness",
            "state":"available",
            "authority":"Institutional Pilot Readiness Workspace",
            "reference":"readiness",
        },
        {
            "id":"procurement_pack",
            "title":"Procurement Evidence Pack",
            "state":"available",
            "authority":"Institutional Onboarding Room",
            "reference":"procurementEvidencePack",
            "sha256":procurement["packSha256"],
        },
        {
            "id":"security_controls",
            "title":"Security control evidence",
            "state":"available",
            "authority":"Corporate readiness projection",
            "reference":"procurementEvidencePack.pack.securityPosture",
        },
        {
            "id":"data_privacy",
            "title":"Data handling & privacy map",
            "state":"available",
            "authority":"Corporate readiness projection",
            "reference":"procurementEvidencePack.pack.dataHandling",
        },
        {
            "id":"interop_profile",
            "title":"Interoperability profile",
            "state":"available",
            "authority":"Federation Interoperability Profile",
            "reference":"procurementEvidencePack.pack.interoperability",
        },
        {
            "id":"pilot_scope",
            "title":"Pilot scope working template",
            "state":"available",
            "authority":"Working-session template",
            "reference":"pilotScopeTemplate",
        },
        {
            "id":"raci",
            "title":"Responsibilities / RACI",
            "state":"available",
            "authority":"Working-session template",
            "reference":"raci",
        },
        {
            "id":"success_criteria",
            "title":"Pilot success criteria",
            "state":"available",
            "authority":"Working-session template",
            "reference":"successCriteria",
        },
        {
            "id":"participation_acceptance",
            "title":"External Participation Acceptance",
            "state":"gated",
            "authority":"Future canonical participation authority",
            "reference":None,
        },
    ]

    open_items=[]
    for step in readiness["steps"]:
        if step["state"]!="ready":
            open_items.append({
                "id":"readiness:"+step["key"],
                "domain":"readiness",
                "title":step["label"],
                "state":step["state"],
                "owner":"institution_or_promomed_by_workstream",
                "blocker":step.get("blocker"),
            })

    for gate in procurement["pack"]["vendorLegal"]["procurementGates"] or []:
        if gate.get("status") not in ("complete","ci_proven","live"):
            open_items.append({
                "id":"procurement:"+str(gate.get("id")),
                "domain":"procurement",
                "title":gate.get("title"),
                "state":gate.get("status"),
                "owner":"security_legal_procurement",
                "blocker":gate.get("evidence"),
            })

    decisions=[
        {
            "id":"pilot_scope_approval",
            "title":"Approve pilot scope and exclusions",
            "state":"not_recorded",
            "canResolveHere":False,
            "requiredEvidence":"bilaterally agreed scope outside this read-only room",
        },
        {
            "id":"success_criteria_approval",
            "title":"Approve success criteria and targets",
            "state":"not_recorded",
            "canResolveHere":False,
            "requiredEvidence":"bilaterally approved KPI/measurement definition",
        },
        {
            "id":"security_privacy_disposition",
            "title":"Security / privacy disposition",
            "state":"not_recorded",
            "canResolveHere":False,
            "requiredEvidence":"approved customer/internal diligence outcome",
        },
        {
            "id":"commercial_terms",
            "title":"Commercial / legal terms",
            "state":"not_recorded",
            "canResolveHere":False,
            "requiredEvidence":"signed commercial/legal documentation",
        },
        {
            "id":"external_participation_acceptance",
            "title":"External Participation Acceptance",
            "state":"gated",
            "canResolveHere":False,
            "requiredEvidence":"real non-demo institution + attributable participation evidence + canonical acceptance authority",
        },
    ]

    agenda=[
        "Confirm institution identity and participants",
        "Review readiness blockers",
        "Review security/privacy/procurement evidence",
        "Define pilot scope and explicit exclusions",
        "Assign RACI owners",
        "Agree success-criteria formulas and identify targets to approve",
        "List unresolved legal/SLA/vendor items",
        "Define commercial/procurement handoff",
        "Leave External Participation Acceptance gated until canonical evidence exists",
    ]

    export_body={
        "roomVersion":ROOM_VERSION,
        "organization":onboarding["organization"],
        "procurementPackSha256":procurement["packSha256"],
        "artifacts":artifacts,
        "openItems":open_items,
        "decisions":decisions,
        "agenda":agenda,
        "truthBoundary":{
            "readOnly":True,
            "meetingNotesPersisted":False,
            "decisionAcceptancePersisted":False,
            "contractCreated":False,
            "externalParticipationAcceptance":"GATED",
        },
    }

    return {
        "roomVersion":ROOM_VERSION,
        "generatedAt":now,
        "organization":onboarding["organization"],
        "workingSessionState":"facilitated_read_only",
        "agenda":agenda,
        "artifacts":artifacts,
        "openItems":open_items,
        "decisions":decisions,
        "handoff":onboarding["commercialHandoff"],
        "export":{
            "sha256":_sha(export_body),
            "document":export_body,
        },
        "truthBoundary":{
            "readOnly":True,
            "meetingNotesPersisted":False,
            "decisionAcceptancePersisted":False,
            "commercialCommitmentCreated":False,
            "externalParticipationAcceptance":"GATED",
            "realPilotClaimed":False,
        },
    }
