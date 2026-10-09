import hashlib
import json
import time

from app import institutional_data_room

VERSION="promomed-institutional-working-session-usability-v1"


def _canonical(v):
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)


def _sha(v):
    return hashlib.sha256(_canonical(v).encode("utf-8")).hexdigest()


def snapshot(c,organization_id,now=None):
    now=int(now or time.time())
    room=institutional_data_room.snapshot(c,organization_id,now=now)

    participant_roles=[
        {"role":"Promomed facilitator","purpose":"Run agenda, keep evidence boundaries explicit, assign follow-up owners.","canApprove":False},
        {"role":"Institution business owner","purpose":"Confirm business objective, scope, exclusions and expected value.","canApprove":False},
        {"role":"Institution technical owner","purpose":"Answer integration, endpoint, identity and interoperability questions.","canApprove":False},
        {"role":"Security / Privacy / Legal","purpose":"Review control evidence, privacy boundaries, vendor and contractual gaps.","canApprove":False},
        {"role":"Procurement / Commercial","purpose":"Clarify procurement path, commercial process and required documents.","canApprove":False},
        {"role":"Medical / Editorial governance","purpose":"Join only when the pilot scope requires governed scientific content workflows.","canApprove":False},
    ]

    document_requests=[
        {"id":"org_identity","category":"Institution","title":"Institution identity reference","required":True,"owner":"Institution business owner","state":"requested"},
        {"id":"admin_nomination","category":"Authority","title":"Named accountable administrator/operator","required":True,"owner":"Institution business owner","state":"requested"},
        {"id":"integration_map","category":"Technical","title":"In-scope systems and integration map","required":True,"owner":"Institution technical owner","state":"requested"},
        {"id":"security_questionnaire","category":"Security","title":"Customer security/vendor questionnaire","required":False,"owner":"Security / Privacy / Legal","state":"requested_if_applicable"},
        {"id":"data_categories","category":"Privacy","title":"Intended pilot data categories","required":True,"owner":"Security / Privacy / Legal","state":"requested"},
        {"id":"sla_expectations","category":"Operations","title":"Required SLA / support expectations","required":False,"owner":"Procurement / Commercial","state":"requested_if_applicable"},
        {"id":"success_criteria","category":"Pilot","title":"Proposed pilot success criteria / target values","required":True,"owner":"Institution business owner","state":"requested"},
        {"id":"commercial_process","category":"Commercial","title":"Procurement process, owner and required commercial documents","required":True,"owner":"Procurement / Commercial","state":"requested"},
        {"id":"participation_acceptance","category":"Governance","title":"External Participation Acceptance evidence","required":True,"owner":"Institution + Promomed governance","state":"gated"},
    ]

    question_routes=[
        {"topic":"identity_authority","question":"Who is authorized to represent the institution for this pilot?","routeTo":"Institution business owner","evidence":"identity reference + membership/authority evidence"},
        {"topic":"integration","question":"Which systems and endpoints are in scope?","routeTo":"Institution technical owner","evidence":"integration map + endpoint details"},
        {"topic":"security","question":"Which security controls require customer approval?","routeTo":"Security / Privacy / Legal","evidence":"security questionnaire + control disposition"},
        {"topic":"privacy","question":"Which data categories and purposes are allowed?","routeTo":"Security / Privacy / Legal","evidence":"approved data categories/purpose boundary"},
        {"topic":"sla","question":"Which recovery/support/notification terms must become contractual?","routeTo":"Procurement / Commercial","evidence":"agreed SLA/support terms"},
        {"topic":"pilot_scope","question":"What is explicitly in and out of scope?","routeTo":"Institution business owner","evidence":"bilaterally agreed scope/exclusions"},
        {"topic":"success","question":"How will the pilot be judged?","routeTo":"Institution business owner","evidence":"approved KPI formulas + target values"},
        {"topic":"commercial","question":"What is required to move from diligence to contract?","routeTo":"Procurement / Commercial","evidence":"commercial/legal checklist completion"},
        {"topic":"participation","question":"Has a real institution explicitly accepted participation?","routeTo":"Institution + Promomed governance","evidence":"canonical participation acceptance","state":"gated"},
    ]

    gap_ownership=[]
    for item in room["openItems"]:
        domain=item.get("domain")
        owner="Promomed facilitator"
        if domain=="procurement":
            owner="Security / Privacy / Legal or Procurement / Commercial"
        elif domain=="readiness":
            title=(item.get("title") or "").lower()
            if "identity" in title or "administrator" in title:
                owner="Institution business owner"
            elif "qualification" in title or "key" in title or "interop" in title or "endpoint" in title:
                owner="Institution technical owner"
        gap_ownership.append({
            "id":item["id"],
            "title":item.get("title"),
            "state":item.get("state"),
            "owner":owner,
            "blocker":item.get("blocker"),
            "resolutionCanBeAcceptedHere":False,
        })

    agenda=[
        {"order":1,"title":"Who is in the room?","output":"participant roles mapped","status":"ready"},
        {"order":2,"title":"What evidence already exists?","output":"artifacts reviewed","status":"ready"},
        {"order":3,"title":"What is missing?","output":"gap ownership assigned","status":"ready"},
        {"order":4,"title":"What documents must the institution provide?","output":"document request checklist","status":"ready"},
        {"order":5,"title":"Who answers each diligence question?","output":"question routing map","status":"ready"},
        {"order":6,"title":"What must be agreed outside this room?","output":"decision/contract handoff","status":"ready"},
        {"order":7,"title":"Participation acceptance","output":"remains gated until canonical real-party evidence exists","status":"gated"},
    ]

    export_body={
        "version":VERSION,
        "organization":room["organization"],
        "participantRoles":participant_roles,
        "documentRequests":document_requests,
        "questionRoutes":question_routes,
        "gapOwnership":gap_ownership,
        "agenda":agenda,
        "dataRoomExportSha256":room["export"]["sha256"],
        "truthBoundary":{
            "readOnly":True,
            "documentReceiptPersisted":False,
            "questionAnswerPersisted":False,
            "ownerAssignmentAccepted":False,
            "approvalPersisted":False,
            "externalParticipationAcceptance":"GATED",
        },
    }

    return {
        "version":VERSION,
        "generatedAt":now,
        "organization":room["organization"],
        "participantRoles":participant_roles,
        "documentRequests":document_requests,
        "questionRoutes":question_routes,
        "gapOwnership":gap_ownership,
        "agenda":agenda,
        "handoff":room["handoff"],
        "export":{"sha256":_sha(export_body),"document":export_body},
        "truthBoundary":{
            "readOnly":True,
            "documentReceiptPersisted":False,
            "questionAnswerPersisted":False,
            "ownerAssignmentAccepted":False,
            "approvalPersisted":False,
            "externalParticipationAcceptance":"GATED",
            "realPilotClaimed":False,
        },
    }
