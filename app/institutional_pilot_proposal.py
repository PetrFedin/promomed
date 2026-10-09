import hashlib
import json
import time

from app import corporate

VERSION="promomed-institutional-pilot-proposal-studio-v1"

ARCHETYPES={
    "clinic":{
        "label":"Clinic / healthcare provider",
        "businessObjectives":[
            "structure patient/participant education and engagement around governed health content",
            "connect event, media and post-event journeys without presenting the platform as an EHR",
            "measure attendance, content engagement and consent-based continuation",
        ],
        "useCases":[
            "patient/participant education programme",
            "expert-led event and replay journey",
            "consent-based follow-up and partner continuation",
        ],
        "stakeholders":["Business owner","Clinical/medical governance","IT","Security/Privacy/Legal","Procurement"],
    },
    "university":{
        "label":"University / education institution",
        "businessObjectives":[
            "deliver evidence-aware health education and event programming",
            "connect faculty, sessions, media, learning tracks and community continuation",
            "measure participation and learning engagement without claiming accreditation",
        ],
        "useCases":[
            "health education programme",
            "faculty/expert knowledge hub",
            "conference-to-learning continuation",
        ],
        "stakeholders":["Programme owner","Faculty/academic governance","IT","Privacy/Legal","Procurement"],
    },
    "medical_society":{
        "label":"Medical / scientific society",
        "businessObjectives":[
            "publish governed expert content with provenance and review boundaries",
            "support events, replay, evidence packs and member continuation",
            "make interoperability/evidence posture inspectable without implying endorsement",
        ],
        "useCases":[
            "society congress companion",
            "governed knowledge hub",
            "evidence-backed content syndication pilot",
        ],
        "stakeholders":["Society leadership","Scientific/medical governance","Editorial","IT","Legal/Procurement"],
    },
    "pharma":{
        "label":"Pharma / biopharma partner",
        "businessObjectives":[
            "run governed health-communication experiences with explicit evidence and disclosure boundaries",
            "separate educational value from commercial continuation",
            "support institutional diligence, partner reporting and consent-based engagement",
        ],
        "useCases":[
            "corporate health-education programme",
            "conference/content ecosystem",
            "partner evidence and engagement reporting",
        ],
        "stakeholders":["Business sponsor","Medical affairs","Compliance/Legal","IT/Security","Procurement"],
    },
    "knowledge_provider":{
        "label":"Knowledge / content provider",
        "businessObjectives":[
            "package attributable evidence/content for governed downstream use",
            "expose provenance, versioning and compatibility without claiming adoption",
            "support portable evidence interchange and content continuation",
        ],
        "useCases":[
            "content/evidence syndication",
            "expert knowledge hub",
            "portable evidence pilot",
        ],
        "stakeholders":["Content owner","Editorial/scientific governance","Technical owner","Legal","Commercial"],
    },
    "strategic_partner":{
        "label":"Strategic / ecosystem partner",
        "businessObjectives":[
            "test a bounded cross-organisation workflow before any long-term commitment",
            "align technical, governance and procurement readiness in one pilot path",
            "measure operational usefulness without treating a demo as traction",
        ],
        "useCases":[
            "joint institutional pilot",
            "interoperability/evidence workflow",
            "co-developed event/content journey",
        ],
        "stakeholders":["Executive sponsor","Business owner","Technical owner","Security/Legal","Procurement"],
    },
}


def _canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)


def _sha(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _common_scope():
    return [
        {
            "id":"foundation",
            "title":"Foundation",
            "includes":["institution profile","participant roles","pilot scope workshop","truth-boundary review"],
            "status":"proposed",
        },
        {
            "id":"experience",
            "title":"Experience",
            "includes":["programme/content surface","registration/attendance or learning journey","post-event continuation"],
            "status":"proposed",
        },
        {
            "id":"evidence",
            "title":"Evidence & governance",
            "includes":["evidence provenance","review boundaries","procurement evidence pack","readiness/follow-up views"],
            "status":"proposed",
        },
        {
            "id":"integration",
            "title":"Technical integration",
            "includes":["identity/integration discovery","endpoint/data-boundary review","optional federation/interchange where in scope"],
            "status":"optional_to_agree",
        },
    ]


def snapshot(c,archetype,now=None):
    now=int(now or time.time())
    archetype=(archetype or "").strip().lower()
    if archetype not in ARCHETYPES:
        raise ValueError("unsupported_archetype")

    profile=ARCHETYPES[archetype]
    corp=corporate.snapshot(c)

    success_criteria=[
        {"metric":"required onboarding completion","formula":"completed mandatory onboarding items / mandatory onboarding items","target":"to_agree"},
        {"metric":"participant journey completion","formula":"users completing agreed pilot journey / users entering pilot journey","target":"to_agree_if_in_scope"},
        {"metric":"attendance / content engagement","formula":"verified attendance or governed content interactions / eligible pilot participants","target":"to_agree_if_in_scope"},
        {"metric":"consent-based continuation","formula":"explicit consented continuation actions / eligible continuation opportunities","target":"to_agree_if_in_scope"},
        {"metric":"critical blocker closure","formula":"material blockers closed / material blockers identified","target":"to_agree"},
        {"metric":"operational recovery","formula":"critical scenarios with documented recovery path / critical scenarios observed","target":"to_agree_if_in_scope"},
    ]

    customer_inputs=[
        "named business sponsor and accountable owner",
        "intended pilot objective and explicit exclusions",
        "in-scope user groups / teams",
        "in-scope systems and integrations",
        "intended data categories and prohibited data categories",
        "security/vendor questionnaire if applicable",
        "required legal/DPA/SLA process",
        "procurement process and decision owners",
        "proposed success targets for jointly selected metrics",
        "real participation acceptance only when a real pilot is actually authorized",
    ]

    prerequisites=[
        {
            "id":"scope",
            "title":"Pilot scope agreed",
            "state":"TO_AGREE",
            "evidenceRequired":"bilaterally agreed objective, in-scope workflows and exclusions",
        },
        {
            "id":"security_privacy",
            "title":"Security/privacy disposition",
            "state":"TO_AGREE",
            "evidenceRequired":"customer/internal diligence outcome for actual pilot scope",
        },
        {
            "id":"legal",
            "title":"Legal / DPA / SLA position",
            "state":"TO_AGREE",
            "evidenceRequired":"approved contractual position where applicable",
        },
        {
            "id":"commercial",
            "title":"Commercial terms",
            "state":"TO_PRICE_AND_AGREE",
            "evidenceRequired":"approved commercial offer outside this projection",
        },
        {
            "id":"participation",
            "title":"External Participation Acceptance",
            "state":"GATED",
            "evidenceRequired":"real non-demo institution + attributable acceptance evidence + canonical authority",
        },
    ]

    proposal={
        "version":VERSION,
        "archetype":archetype,
        "archetypeLabel":profile["label"],
        "positioning":{
            "headline":"Proposed institutional pilot — for discussion, not a commitment",
            "businessObjectives":profile["businessObjectives"],
            "useCases":profile["useCases"],
        },
        "stakeholders":profile["stakeholders"],
        "scopeOptions":_common_scope(),
        "customerInputsRequired":customer_inputs,
        "successCriteria":success_criteria,
        "prerequisites":prerequisites,
        "commercial":{
            "pricing":"TO_PRICE",
            "pilotDuration":"TO_AGREE",
            "supportModel":"TO_AGREE",
            "sla":"TO_AGREE_IF_REQUIRED",
            "purchaseOrder":"NOT_CLAIMED",
            "revenue":"NOT_CLAIMED",
        },
        "currentProductEvidence":{
            "productionRuntimeReady":bool((corp.get("runtime") or {}).get("production_ready")),
            "securityCertificationClaimed":False,
            "approvedDpaSlaClaimed":False,
            "approvedRtoRpoClaimed":False,
            "livePostgresClaimed":bool((corp.get("security_truth") or {}).get("can_claim_live_postgres")),
            "ciProvenAuthRestoreControls":bool((corp.get("security_truth") or {}).get("can_claim_auth_restore_controls_ci_proven")),
        },
        "truthBoundary":{
            "proposalOnly":True,
            "realCustomerClaimed":False,
            "realPilotClaimed":False,
            "commercialCommitmentClaimed":False,
            "targetsAgreed":False,
            "timelineAgreed":False,
            "pricingAgreed":False,
            "externalParticipationAcceptance":"GATED",
        },
    }

    return {
        **proposal,
        "export":{
            "sha256":_sha(proposal),
            "document":proposal,
        },
        "generatedAt":now,
    }


def archetypes():
    return [{"id":k,"label":v["label"]} for k,v in ARCHETYPES.items()]
