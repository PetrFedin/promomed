import hashlib
import json
import time

from app import corporate, federation_interop, pilot_workspace

ROOM_VERSION="promomed-institutional-onboarding-room-v1"
PACK_VERSION="promomed-procurement-evidence-pack-v1"


def _canonical(v):
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)


def _sha(v):
    return hashlib.sha256(_canonical(v).encode("utf-8")).hexdigest()


def _section(key,title,state,detail):
    return {"key":key,"title":title,"state":state,"detail":detail}


def _procurement_pack(c,readiness,corp):
    profile=federation_interop.public_profile(c)
    controls=corp.get("controls") or []
    body={
        "packVersion":PACK_VERSION,
        "organization":readiness["organization"],
        "architecture":{
            "runtime":corp.get("runtime"),
            "model":"bounded contexts + versioned persistence + governed institutional interoperability",
            "evidence":["app/db.py","app/auth.py","app/pilot_workspace.py","app/federation_interop.py"],
        },
        "securityPosture":{
            "controls":controls,
            "truth":corp.get("security_truth"),
            "frameworkCrosswalk":corp.get("framework_crosswalk"),
        },
        "dataHandling":{
            "inventory":corp.get("data_inventory"),
            "privacyPrinciples":corp.get("privacy_principles"),
        },
        "governance":{
            "readiness":readiness["readiness"],
            "steps":readiness["steps"],
            "blockers":readiness["blockers"],
            "nextAction":readiness["nextAction"],
        },
        "interoperability":{
            "profileId":profile.get("id"),
            "profileVersion":profile.get("profileVersion"),
            "profileSha256":profile.get("profileSha256"),
            "status":profile.get("status"),
        },
        "integrationRequirements":[
            "attributable institutional identity",
            "verified institutional administrator/operator",
            "mandatory technical conformance",
            "institution-controlled Ed25519 key + proof-of-possession",
            "verified HTTPS delivery endpoint when event delivery is in scope",
        ],
        "slaBoundaries":{
            "provenMechanics":["delivery retry/idempotency","update/withdrawal tracking","backup and isolated restore"],
            "notYetContracted":["RTO/RPO","support response","incident notification","DSAR/deletion","availability/service credits"],
        },
        "vendorLegal":{
            "questions":corp.get("vendor_questions"),
            "procurementGates":corp.get("procurement_gates"),
        },
        "customerInputsRequired":[
            "institution identity reference","accountable administrator","technical owner",
            "security/privacy/legal contacts","pilot use cases","in-scope systems",
            "intended data categories","security/vendor questionnaire","SLA expectations",
            "bilaterally approved success criteria","procurement owner",
        ],
        "truthBoundary":{
            "securityCertificationClaimed":False,
            "accreditationClaimed":False,
            "medicalEfficacyClaimed":False,
            "externalAdoptionInferred":False,
            "commercialContractClaimed":False,
            "externalParticipationAcceptance":"GATED",
        },
    }
    return {"packVersion":PACK_VERSION,"packSha256":_sha(body),"pack":body}


def snapshot(c,organization_id,now=None):
    now=int(now or time.time())
    readiness=pilot_workspace.snapshot(c,organization_id,now=now)
    corp=corporate.snapshot(c)
    ready={x["key"] for x in readiness["steps"] if x["state"]=="ready"}

    sections=[
        _section("organisation_profile","Organisation Profile","ready" if "institution_identity" in ready else "blocked","Canonical attributable institutional identity."),
        _section("people_authority","People & Authority","ready" if "human_authority" in ready else "blocked","Verified administrator/operator for the exact institution."),
        _section("technical_qualification","Technical Qualification","ready" if "syndication_qualification" in ready else "blocked","Mandatory conformance and current qualification."),
        _section("trust_key_setup","Trust & Key Setup","ready" if "independent_key" in ready else "blocked","Institution-controlled key, proof and lifecycle."),
        _section("integration_readiness","Integration Readiness","ready" if "federation_compatibility" in ready else "blocked","Federation profile compatibility and integration requirements."),
        _section("evidence_pack","Evidence Pack","ready" if "portable_evidence_pack" in ready else "blocked","Portable evidence with explicit provenance boundaries."),
        _section("security_legal_procurement","Security / Legal / Procurement Pack","ready","Current controls, data map, vendor questions and unresolved gates."),
        _section("pilot_scope_builder","Pilot Scope Builder","ready","Draft working scope only; no contract or admission mutation."),
        _section("raci","Responsibilities / RACI","ready","Default responsibility matrix for the working session."),
        _section("success_criteria","Pilot Success Criteria","ready","Metric framework; numeric targets require bilateral agreement."),
        _section("commercial_handoff","Commercial / Procurement Handoff","ready","Pre-contract checklist for legal, procurement and implementation."),
        _section("external_participation_acceptance","External Participation Acceptance","gated","Closed until a real non-demo institution supplies explicit attributable participation evidence."),
    ]

    return {
        "roomVersion":ROOM_VERSION,
        "generatedAt":now,
        "organization":readiness["organization"],
        "overallState":"demo_only_workthrough" if readiness["organization"].get("demoOnly") else "ready_for_facilitated_onboarding",
        "sections":sections,
        "readiness":readiness,
        "procurementEvidencePack":_procurement_pack(c,readiness,corp),
        "pilotScopeTemplate":{
            "fields":["business objective","institutional use case","users/teams","systems/integrations","data categories","workflows","pilot window","support model","explicit exclusions"],
            "guardrail":"Drafting scope does not create participation acceptance, a contract or production admission.",
        },
        "raci":[
            {"workstream":"Institution identity","Promomed":"A/R","Institution":"R","SecurityLegal":"C","Procurement":"I"},
            {"workstream":"Technical integration","Promomed":"R","Institution":"A/R","SecurityLegal":"C","Procurement":"I"},
            {"workstream":"Security & privacy diligence","Promomed":"R","Institution":"C","SecurityLegal":"A/R","Procurement":"C"},
            {"workstream":"Pilot scope & success criteria","Promomed":"R","Institution":"A/R","SecurityLegal":"C","Procurement":"C"},
            {"workstream":"Commercial/legal terms","Promomed":"R","Institution":"C","SecurityLegal":"C","Procurement":"A/R"},
        ],
        "successCriteria":[
            {"metric":"Required onboarding steps completed","formula":"ready required steps / total required steps","target":"to_agree"},
            {"metric":"Mandatory conformance scopes passed","formula":"passed mandatory scopes / mandatory scopes","target":"to_agree"},
            {"metric":"Portable evidence verification success","formula":"valid verifications / verification attempts","target":"to_agree"},
            {"metric":"Delivery acknowledgement success","formula":"acknowledged eligible events / eligible events","target":"to_agree_if_in_scope"},
            {"metric":"Material blockers closed with evidence","formula":"closed blockers / material blockers raised","target":"to_agree"},
        ],
        "commercialHandoff":{
            "state":"pre_contract",
            "requiredBeforeSignature":["agreed scope/exclusions","agreed success criteria","security/privacy disposition","vendor/DPA position","SLA/support terms","owners/dates","commercial approval","external participation acceptance"],
            "notClaimed":["signed pilot","customer commitment","purchase order","revenue","ARR/MRR","accreditation"],
        },
        "truthBoundary":{
            "readOnlyOrchestration":True,
            "draftScopeIsContract":False,
            "successTargetsAreAgreed":False,
            "externalParticipationAcceptance":"GATED",
            "realPilotClaimed":False,
            "commercialRelationshipClaimed":False,
        },
    }
