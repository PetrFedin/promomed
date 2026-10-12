"""Read-only scoped pilot-to-revenue evidence projection.

This is an evidence REQUEST ladder, NOT a finance ledger or booking authority.
No unverified contract, invoice, cash, cost, revenue or renewal is inferred from
demo Deal Room, programme counts or technical delivery acknowledgements.
"""
import hashlib
import json
import re
import time

VERSION = "promomed-pilot-to-revenue-evidence-ladder-v1"

STAGES = (
    {
        "id": "pilot_acceptance", "title": "01 · Accepted pilot",
        "owner": "Institutional signatory + Governance",
        "evidence": ("Verified non-demo counterparty identity", "Signed pilot scope and responsibilities",
                     "External Participation Acceptance with signer and scope version"),
        "gate": "An active organization record is not a signed participation acceptance.",
        "target": "/institutional-command-center.html",
    },
    {
        "id": "contract", "title": "02 · Contracted obligations",
        "owner": "Legal + Commercial",
        "evidence": ("Countersigned terms and DPA/SLA", "Agreed consideration and currency",
                     "Versioned obligations and acceptance criteria"),
        "gate": "Proposal Studio, package catalogue and demo Deal Room are not signed contracts.",
        "target": "/institutional-pilot-proposal.html",
    },
    {
        "id": "delivery", "title": "03 · Delivered and accepted",
        "owner": "Delivery Owner + External Buyer",
        "evidence": ("Executed obligations mapped to signed contract", "Scope-specific independent delivery acceptance",
                     "Disputes, rejects and credits reconciled"),
        "gate": "Technical syndication delivery ACK is not commercial fulfilment or buyer acceptance.",
        "target": "/institutional-commercial-workspace.html",
    },
    {
        "id": "invoice", "title": "04 · Invoice issued",
        "owner": "Accounts Receivable",
        "evidence": ("Unique invoice ID and approved legal entity", "Contract and accepted deliverable reference",
                     "Tax, currency, invoice date and credit-note status"),
        "gate": "A payment request preview or a capital tranche is not an invoice.",
        "target": "/institutional-command-center.html",
    },
    {
        "id": "cash", "title": "05 · Cash received",
        "owner": "Treasury + Finance",
        "evidence": ("Bank or PSP settlement receipt", "Payment allocated to invoice ID",
                     "Refund and chargeback reconciliation"),
        "gate": "Invoice face value is not cash collected.",
        "target": "/institutional-command-center.html",
    },
    {
        "id": "finance", "title": "06 · Finance acceptance",
        "owner": "Finance Controller",
        "evidence": ("Recognized revenue schedule and accounting policy",
                     "Actual direct cost by deliverable and allocation method",
                     "Credits, taxes, non-recurring items and double-count checks",
                     "Finance acceptance actor, date and evidence hash"),
        "gate": "Revenue recognition, cash and direct costs are distinct measures; operating profit is not a signed ROI.",
        "target": "/institutional-evidence-export.html",
    },
    {
        "id": "renewal", "title": "07 · Repeatable contract",
        "owner": "Account Owner + Finance",
        "evidence": ("New countersigned period, price and scope", "Linked original contract and account",
                     "Recognized renewal revenue and retention denominator"),
        "gate": "A follow-up, returning participant or proposal is not a contract renewal.",
        "target": "/institutional-commercial-workspace.html",
    },
)

IDENTIFIER = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9:_-]{0,99}\Z")


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _require_member(c, organization_id, actor_email):
    # Resolve organization identity only after verifying scoped membership.
    # Unknown and unauthorized organizations have the SAME external result.
    actor_email = str(actor_email or "").strip().lower()
    if not actor_email or len(actor_email) > 254:
        raise ValueError("organization_not_found")
    now = int(time.time())
    authorized = c.execute(
        """SELECT 1 FROM institutional_memberships m
           JOIN institutional_organizations o ON o.id=m.organization_id
           WHERE m.organization_id=? AND m.account_email=?
             AND m.member_role IN ('administrator','operator')
             AND m.status='active'
             AND m.effective_at<=?
             AND (m.expires_at IS NULL OR m.expires_at>?)
             AND m.demo_only=o.demo_only
             AND (o.demo_only=1 OR m.account_email NOT LIKE '%@demo.ru')
             AND o.status='active'
           LIMIT 1""",
        (organization_id, actor_email, now, now),
    ).fetchone()
    if authorized is None:
        raise ValueError("organization_not_found")


def _source_facts(c, organization_id):
    # Never query global commercial/demo records. Every fact has an exact
    # organization_id predicate, and facts are metadata, not accepted deals.
    org = c.execute(
        "SELECT id,name,organization_type,status,external_ref,credential_source,demo_only "
        "FROM institutional_organizations WHERE id=?", (organization_id,)
    ).fetchone()
    if org is None:
        raise ValueError("organization_not_found")

    non_demo = org["status"] == "active" and not bool(org["demo_only"])
    attributable = non_demo and bool(str(org["external_ref"] or "").strip()) and bool(
        str(org["credential_source"] or "").strip()
    )
    transport = c.execute(
        "SELECT COUNT(*) n FROM evidence_exchange_deliveries "
        "WHERE organization_id=? AND status='acknowledged' AND demo_only=0 AND acknowledged_at IS NOT NULL AND withdrawn_at IS NULL",
        (organization_id,)
    ).fetchone()
    return (
        {"id": org["id"], "name": org["name"], "type": org["organization_type"],
         "demoOnly": bool(org["demo_only"])},
        {"nonDemoIdentityMetadata": bool(attributable),
         "technicalEvidenceAcknowledgements": int(transport["n"]),
         "identityIsNotSignedPilot": True,
         "technicalAckIsNotCommercialAcceptance": True},
    )


def snapshot(c, organization_id, *, actor_email=None):
    organization_id = str(organization_id or "").strip()
    if not IDENTIFIER.fullmatch(organization_id):
        raise ValueError("organization_id_invalid" if organization_id else "organization_id_required")

    _require_member(c, organization_id, actor_email)
    organization, signals = _source_facts(c, organization_id)
    # No source in the currently admitted Promomed schema records independently
    # validated counterpart sign-off, invoice, bank reconciliation, finance
    # recognition or renewal by commercial contract / tenant. Fail CLOSED.
    stages = []
    for item in STAGES:
        stages.append({
            "id": item["id"], "title": item["title"], "owner": item["owner"],
            "state": "GATED", "requiredEvidence": list(item["evidence"]),
            "sourceState": "NO_ACCEPTED_COMMERCIAL_AUTHORITY",
            "whyBlocked": item["gate"], "target": item["target"],
            "commercialAcceptance": False, "amountRub": None,
        })
    required = sum(len(x["requiredEvidence"]) for x in stages)
    economics = {
        "contractedRub": None, "invoicedRub": None,
        "cashCollectedRub": None, "recognizedRevenueRub": None,
        "directCostsRub": None, "acceptedContributionRub": None,
        "renewalRevenueRub": None,
        "currency": "RUB",
        "nullSemantics": "NOT_VERIFIED_NOT_ZERO",
        "reconciliation": "NOT_AVAILABLE",
    }
    payload = {
        "version": VERSION, "organization": organization, "sourceSignals": signals,
        "stages": stages, "economics": economics,
        "acceptanceSummary": {
            "acceptedStages": 0, "totalStages": len(stages), "requiredEvidenceItems": required,
            "decision": "HOLD_EXTERNAL_PILOT_AND_FINANCE_GATES",
            "externalParticipationAccepted": False,
            "contractSigned": False, "financeAccepted": False,
            "capitalReleaseAuthorized": False, "productionRevenueClaimed": False,
        },
        "truthBoundary": {
            "readOnly": True, "moneyIsNotZero": True,
            "noDemoToActualPromotion": True, "noPaymentOrContractAuthority": True,
            "scope": "exact_organization_id",
            "requiresNonDemoPostgresAndIndependentAcceptance": True,
        },
    }
    digest = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
    return {**payload, "evidenceRequestPack": {"sha256": digest, "document": payload}}
