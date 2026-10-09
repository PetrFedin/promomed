import hashlib
import json
import time

from app import institutional_buyer_fit, institutional_pilot_proposal

VERSION="promomed-institutional-outreach-pack-v1"

MEETING_AGENDA=[
    {"order":1,"title":"Why this conversation","minutes":5,"output":"shared problem statement"},
    {"order":2,"title":"Current workflow and friction","minutes":10,"output":"buyer-side current-state map"},
    {"order":3,"title":"Relevant Promomed capability fit","minutes":10,"output":"capability-to-problem mapping"},
    {"order":4,"title":"Pilot shape and exclusions","minutes":10,"output":"candidate scope / explicit out-of-scope"},
    {"order":5,"title":"Security, legal and procurement path","minutes":10,"output":"diligence path and owners"},
    {"order":6,"title":"Success measurement","minutes":5,"output":"candidate formulas; targets remain to agree"},
    {"order":7,"title":"Next evidence / next meeting","minutes":5,"output":"mutual follow-up inputs, not commitment"},
]

BASE_DISCOVERY=[
    "What concrete problem are you trying to solve in the next 6–12 months?",
    "Who owns the problem, budget, technical integration and governance approval?",
    "Which users, teams or participant groups are actually in scope?",
    "Which data categories are allowed, prohibited or require special handling?",
    "Which existing systems would need to integrate, if any?",
    "What would make a bounded pilot useful enough to continue?",
    "What procurement, legal, security or privacy process must be completed before a pilot?",
    "Which outcomes must not be claimed or measured?",
]

CLAIMS_NOT_TO_MAKE=[
    "do not claim a real customer, signed pilot or external adoption",
    "do not claim agreed pricing, duration, SLA, KPI targets or commercial terms",
    "do not claim accreditation, regulator approval or security certification",
    "do not claim clinical decision support, EHR functionality or medical-record authority",
    "do not claim ARR/MRR, revenue, purchase order or market traction",
    "do not treat compatibility, readiness or READY_FOR_DECISION as approval",
    "do not imply External Participation Acceptance exists before canonical real-party evidence",
]

EVIDENCE_TO_SHOW=[
    {"id":"product","title":"Product / executive demo","purpose":"show the participant and institutional experience"},
    {"id":"readiness","title":"Institutional readiness / onboarding","purpose":"show what must be proven before pilot"},
    {"id":"procurement","title":"Procurement Evidence Pack","purpose":"show security/privacy/legal/procurement posture and gaps"},
    {"id":"working_session","title":"Working Session / Data Room","purpose":"show how diligence is structured"},
    {"id":"followup","title":"Diligence Follow-up Board","purpose":"show ownership and unresolved evidence gaps"},
    {"id":"command_center","title":"Diligence Command Center","purpose":"show executive blockers, critical path and parallel workstreams"},
    {"id":"proposal","title":"Pilot Proposal Studio","purpose":"show archetype-specific pilot options without commitment"},
    {"id":"fit","title":"Buyer Fit Matrix","purpose":"show capability match and questions still requiring validation"},
]


def _canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)


def _sha(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _archetype_questions(fit_row):
    return fit_row.get("validationQuestions") or []


def _framing(archetype,proposal):
    frames={
        "clinic":"Frame Promomed as governed education/engagement infrastructure, not as a clinical record or treatment system.",
        "university":"Frame Promomed as an education/event/knowledge-continuation platform; accreditation requires separate authority.",
        "medical_society":"Frame Promomed around governed knowledge, congress journeys and evidence portability without implying society endorsement.",
        "pharma":"Frame Promomed as governed health-communication and engagement infrastructure with explicit medical/compliance boundaries.",
        "knowledge_provider":"Frame Promomed around attributable content/evidence packaging, provenance and governed downstream use.",
        "strategic_partner":"Frame Promomed as a bounded joint-workflow pilot with explicit ownership and decision gates, not as adoption evidence.",
    }
    return {
        "opening":frames[archetype],
        "proposalHeadline":proposal["positioning"]["headline"],
        "primaryUseCases":proposal["positioning"]["useCases"],
    }


def snapshot(c,archetype,now=None):
    now=int(now or time.time())
    proposal=institutional_pilot_proposal.snapshot(c,archetype,now=now)
    matrix=institutional_buyer_fit.snapshot(c,now=now)
    fit_row=next((x for x in matrix["rows"] if x["archetype"]==archetype),None)
    if fit_row is None:
        raise ValueError("unsupported_archetype")

    discovery_questions=BASE_DISCOVERY+_archetype_questions(fit_row)

    outputs_expected=[
        {"id":"problem","title":"Confirmed problem statement","state":"to_capture_in_real_meeting"},
        {"id":"scope","title":"Candidate pilot scope and exclusions","state":"to_capture_in_real_meeting"},
        {"id":"owners","title":"Named buyer-side owners for business / technical / governance / procurement","state":"to_capture_in_real_meeting"},
        {"id":"inputs","title":"List of evidence/documents buyer must provide","state":"to_capture_in_real_meeting"},
        {"id":"success","title":"Candidate success metrics and who can approve targets","state":"to_capture_in_real_meeting"},
        {"id":"diligence","title":"Security/legal/procurement path","state":"to_capture_in_real_meeting"},
        {"id":"next_step","title":"Mutually agreed next step, if any","state":"to_capture_in_real_meeting"},
        {"id":"participation","title":"External Participation Acceptance","state":"GATED"},
    ]

    brief={
        "version":VERSION,
        "archetype":archetype,
        "archetypeLabel":proposal["archetypeLabel"],
        "framing":_framing(archetype,proposal),
        "agenda":MEETING_AGENDA,
        "discoveryQuestions":discovery_questions,
        "evidenceToShow":EVIDENCE_TO_SHOW,
        "customerInputsToRequest":proposal["customerInputsRequired"],
        "stakeholdersToInvite":proposal["stakeholders"],
        "successCriteriaToDiscuss":proposal["successCriteria"],
        "claimsNotToMake":CLAIMS_NOT_TO_MAKE,
        "meetingOutputsExpected":outputs_expected,
        "followupHandoff":{
            "ifInterestExists":"move to a real institutional working session / diligence process",
            "ifScopeUnclear":"schedule a scoped discovery follow-up; do not invent pilot terms",
            "ifSecurityOrLegalBlocks":"route to diligence owners with evidence pack; do not mark approved",
            "ifNoNextStep":"record no commitment externally; do not create synthetic pipeline truth in this layer",
        },
        "truthBoundary":{
            "planningOnly":True,
            "meetingOccurredClaimed":False,
            "buyerInterestClaimed":False,
            "pipelineStageClaimed":False,
            "nextMeetingClaimed":False,
            "pilotClaimed":False,
            "pricingAgreed":False,
            "targetsAgreed":False,
            "externalParticipationAcceptance":"GATED",
        },
        "sourceBindings":{
            "proposalExportSha256":proposal["export"]["sha256"],
            "buyerFitExportSha256":matrix["export"]["sha256"],
        },
    }

    return {
        **brief,
        "generatedAt":now,
        "export":{"sha256":_sha(brief),"document":brief},
    }
