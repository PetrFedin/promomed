import hashlib
import json
import time

from app import institutional_pilot_proposal

VERSION="promomed-institutional-buyer-fit-matrix-v1"

DIMENSIONS=(
    ("governed_content","Governed health/scientific content"),
    ("event_journey","Event / programme journey"),
    ("learning_continuation","Learning / community continuation"),
    ("evidence_interchange","Evidence / interoperability"),
    ("partner_reporting","Partner / executive reporting"),
    ("technical_integration","Technical integration"),
    ("security_procurement","Security / procurement diligence"),
    ("medical_governance","Medical / scientific governance intensity"),
)

FIT={
    "clinic":{
        "governed_content":"strong","event_journey":"strong","learning_continuation":"conditional",
        "evidence_interchange":"conditional","partner_reporting":"conditional","technical_integration":"conditional",
        "security_procurement":"strong","medical_governance":"strong",
    },
    "university":{
        "governed_content":"strong","event_journey":"strong","learning_continuation":"strong",
        "evidence_interchange":"conditional","partner_reporting":"conditional","technical_integration":"conditional",
        "security_procurement":"conditional","medical_governance":"conditional",
    },
    "medical_society":{
        "governed_content":"strong","event_journey":"strong","learning_continuation":"conditional",
        "evidence_interchange":"strong","partner_reporting":"conditional","technical_integration":"conditional",
        "security_procurement":"conditional","medical_governance":"strong",
    },
    "pharma":{
        "governed_content":"strong","event_journey":"strong","learning_continuation":"conditional",
        "evidence_interchange":"conditional","partner_reporting":"strong","technical_integration":"conditional",
        "security_procurement":"strong","medical_governance":"strong",
    },
    "knowledge_provider":{
        "governed_content":"strong","event_journey":"conditional","learning_continuation":"conditional",
        "evidence_interchange":"strong","partner_reporting":"conditional","technical_integration":"strong",
        "security_procurement":"conditional","medical_governance":"conditional",
    },
    "strategic_partner":{
        "governed_content":"conditional","event_journey":"conditional","learning_continuation":"conditional",
        "evidence_interchange":"strong","partner_reporting":"strong","technical_integration":"strong",
        "security_procurement":"strong","medical_governance":"conditional",
    },
}

VALIDATION_QUESTIONS={
    "clinic":[
        "Is the pilot education/engagement only, or does the buyer expect clinical-record functionality?",
        "Which participant/patient data categories are explicitly allowed and prohibited?",
        "Who owns medical governance and privacy approval?",
    ],
    "university":[
        "Is this an event companion, learning programme, faculty knowledge hub, or combination?",
        "Is accreditation or formal assessment expected? If yes, this requires separate authority.",
        "Which student/faculty identity integrations are actually required?",
    ],
    "medical_society":[
        "Is the primary value congress operations, governed knowledge, syndication, or member continuation?",
        "Who owns scientific review and disclosure rules?",
        "Does the society require portable evidence/interchange or only a hosted experience?",
    ],
    "pharma":[
        "Is the programme medical-affairs, corporate education, partner engagement, or event-led?",
        "Which compliance, pharmacovigilance, disclosure and approval workflows are in scope?",
        "Which outcomes may be measured without crossing promotional/medical boundaries?",
    ],
    "knowledge_provider":[
        "Is the provider supplying content, evidence packages, expert identity, or all three?",
        "What provenance/versioning obligations exist?",
        "Is downstream syndication required, and who is allowed to consume it?",
    ],
    "strategic_partner":[
        "What exact joint workflow is being tested?",
        "Which side owns integration, governance and commercial decisions?",
        "What would count as a useful pilot result without being mistaken for adoption?",
    ],
}


def _canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)


def _sha(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def snapshot(c,now=None):
    now=int(now or time.time())
    archetypes=[x["id"] for x in institutional_pilot_proposal.archetypes()]
    rows=[]
    for archetype in archetypes:
        proposal=institutional_pilot_proposal.snapshot(c,archetype,now=now)
        fit=FIT[archetype]
        rows.append({
            "archetype":archetype,
            "label":proposal["archetypeLabel"],
            "fit":fit,
            "businessObjectives":proposal["positioning"]["businessObjectives"],
            "useCases":proposal["positioning"]["useCases"],
            "stakeholders":proposal["stakeholders"],
            "validationQuestions":VALIDATION_QUESTIONS[archetype],
            "commercial":{
                "pricing":proposal["commercial"]["pricing"],
                "pilotDuration":proposal["commercial"]["pilotDuration"],
                "supportModel":proposal["commercial"]["supportModel"],
            },
            "participationAcceptance":proposal["truthBoundary"]["externalParticipationAcceptance"],
            "proposalExportSha256":proposal["export"]["sha256"],
        })

    dimension_summary=[]
    for key,label in DIMENSIONS:
        dimension_summary.append({
            "id":key,
            "label":label,
            "strongFor":[x["archetype"] for x in rows if x["fit"][key]=="strong"],
            "conditionalFor":[x["archetype"] for x in rows if x["fit"][key]=="conditional"],
        })

    comparison={
        "version":VERSION,
        "dimensions":[{"id":k,"label":v} for k,v in DIMENSIONS],
        "rows":rows,
        "dimensionSummary":dimension_summary,
        "interpretation":{
            "strong":"Promomed has a direct existing capability match for this archetype/dimension.",
            "conditional":"Potential match, but value depends on real scope, process and buyer constraints.",
            "notPrimary":"Not a primary reason to position the pilot.",
        },
        "usageBoundary":{
            "noMarketDemandClaim":True,
            "noWinProbabilityClaim":True,
            "noRevenuePotentialClaim":True,
            "noCustomerPriorityClaim":True,
            "noSyntheticScore":True,
            "fitIsCapabilityMatchOnly":True,
        },
        "truthBoundary":{
            "planningOnly":True,
            "realCustomerClaimed":False,
            "realPipelineClaimed":False,
            "realPilotClaimed":False,
            "externalParticipationAcceptance":"GATED",
        },
    }

    return {
        **comparison,
        "generatedAt":now,
        "export":{"sha256":_sha(comparison),"document":comparison},
    }
