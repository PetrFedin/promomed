import hashlib
import json
import time

from app import institutional_buyer_fit, institutional_outreach_pack, institutional_pilot_proposal

VERSION="promomed-institutional-evidence-export-pack-v1"


def _canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)


def _sha(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def snapshot(c,archetype,now=None):
    now=int(now or time.time())
    proposal=institutional_pilot_proposal.snapshot(c,archetype,now=now)
    fit=institutional_buyer_fit.snapshot(c,now=now)
    outreach=institutional_outreach_pack.snapshot(c,archetype,now=now)
    fit_row=next((row for row in fit["rows"] if row["archetype"]==archetype),None)
    if fit_row is None:
        raise ValueError("unsupported_archetype")

    artifact_catalog=[
        {
            "id":"commercial_workspace",
            "title":"Institutional Commercial Workspace",
            "surface":"/institutional-commercial-workspace.html",
            "purpose":"guided navigation across the commercial institutional stack",
            "authority":"planning_only",
            "sourceSha256":None,
        },
        {
            "id":"buyer_fit",
            "title":"Institutional Buyer Fit Matrix",
            "surface":"/institutional-buyer-fit.html",
            "purpose":"capability match and buyer validation questions",
            "authority":"planning_only",
            "sourceSha256":fit["export"]["sha256"],
        },
        {
            "id":"pilot_proposal",
            "title":"Institutional Pilot Proposal Studio",
            "surface":"/institutional-pilot-proposal.html",
            "purpose":"bounded archetype-specific pilot proposal",
            "authority":"proposal_only",
            "sourceSha256":proposal["export"]["sha256"],
        },
        {
            "id":"outreach_pack",
            "title":"Institutional Outreach Pack",
            "surface":"/institutional-outreach-pack.html",
            "purpose":"first-meeting agenda, discovery and evidence-to-show",
            "authority":"planning_only",
            "sourceSha256":outreach["export"]["sha256"],
        },
        {
            "id":"command_center",
            "title":"Institutional Diligence Command Center",
            "surface":"/institutional-command-center.html",
            "purpose":"organization-specific diligence after attributable institutional evidence exists",
            "authority":"requires_real_organization_context",
            "sourceSha256":None,
        },
    ]

    executive_summary={
        "archetype":archetype,
        "archetypeLabel":proposal["archetypeLabel"],
        "proposalHeadline":proposal["positioning"]["headline"],
        "primaryUseCases":proposal["positioning"]["useCases"],
        "strongCapabilityDimensions":[key for key,value in fit_row["fit"].items() if value=="strong"],
        "conditionalCapabilityDimensions":[key for key,value in fit_row["fit"].items() if value=="conditional"],
        "stakeholders":proposal["stakeholders"],
        "customerInputsRequired":proposal["customerInputsRequired"],
        "firstMeetingMinutes":sum(item["minutes"] for item in outreach["agenda"]),
    }

    evidence_manifest={
        "version":VERSION,
        "archetype":archetype,
        "archetypeLabel":proposal["archetypeLabel"],
        "generatedFrom":{
            "buyerFitExportSha256":fit["export"]["sha256"],
            "proposalExportSha256":proposal["export"]["sha256"],
            "outreachExportSha256":outreach["export"]["sha256"],
        },
        "artifactCatalog":artifact_catalog,
        "executiveSummary":executive_summary,
        "validationQuestions":fit_row["validationQuestions"],
        "claimsNotToMake":outreach["claimsNotToMake"],
        "meetingOutputsExpected":outreach["meetingOutputsExpected"],
        "commercialBoundary":proposal["commercial"],
        "productEvidence":proposal["currentProductEvidence"],
        "diligenceBoundary":{
            "organizationSpecificCommandCenterIncluded":False,
            "reason":"No named institution is inferred from an archetype-only export.",
            "nextStep":"Open the organization-specific diligence surfaces only after attributable institutional evidence exists.",
        },
        "truthBoundary":{
            "planningPackageOnly":True,
            "namedCustomerClaimed":False,
            "meetingOccurredClaimed":False,
            "buyerInterestClaimed":False,
            "pipelineClaimed":False,
            "pilotClaimed":False,
            "pricingAgreed":False,
            "targetsAgreed":False,
            "contractClaimed":False,
            "purchaseOrderClaimed":False,
            "revenueClaimed":False,
            "externalParticipationAcceptance":"GATED",
        },
    }

    package_sha=_sha(evidence_manifest)
    return {
        **evidence_manifest,
        "generatedAt":now,
        "export":{
            "sha256":package_sha,
            "document":evidence_manifest,
            "contentType":"application/json",
            "suggestedFilename":f"promomed-institutional-evidence-pack-{archetype}.json",
        },
    }
