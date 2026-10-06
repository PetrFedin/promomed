from app import db


def _count(c, table, where=""):
    suffix = (" " + where.strip()) if where.strip() else ""
    return int(c.execute(f"SELECT COUNT(*) n FROM {table}{suffix}").fetchone()["n"])


def _event_kinds(c):
    return {str(r["kind"]) for r in c.execute("SELECT DISTINCT kind FROM events")}


def snapshot(c):
    readiness = db.readiness()
    production = bool(readiness.get("production_ready"))
    event_kinds = _event_kinds(c)
    delivered = _count(c, "deliverables", "WHERE status='delivered'")
    deliverable_total = _count(c, "deliverables")

    golden_required = {
        "venue_full",
        "booking_waitlist",
        "waitlist_promoted",
        "schedule_changed",
        "checkin",
        "placement_active",
        "voluntary_lead",
        "journey_replay",
    }
    golden_demo_complete = golden_required.issubset(event_kinds)
    partner_demo_complete = delivered > 0 and {"placement_active", "voluntary_lead"}.issubset(event_kinds)

    acceptance_roles = [
        {
            "id": "product",
            "label": "Product Owner",
            "accepts": "Functional scope and user journeys",
            "evidence": "Release SHA + browser regression + acceptance checklist",
        },
        {
            "id": "operations",
            "label": "Event / Operations Owner",
            "accepts": "Operational run and recovery paths",
            "evidence": "Runbook + incident/recovery ledger + event close report",
        },
        {
            "id": "finance",
            "label": "Finance",
            "accepts": "Recognized economic value and delivery cost",
            "evidence": "Baseline pack + actuals + reconciliation + signed value acceptance",
        },
        {
            "id": "security",
            "label": "IT / Security / Procurement",
            "accepts": "Production architecture and vendor controls",
            "evidence": "Production readiness + restore proof + security/procurement pack",
        },
        {
            "id": "medical",
            "label": "Medical / Legal / Editorial",
            "accepts": "Governed health-content scope",
            "evidence": "Versioned review / disclosure / approval record",
        },
        {
            "id": "sponsor",
            "label": "Executive Sponsor / IC",
            "accepts": "Capital release",
            "evidence": "Signed tranche decision using accepted evidence only",
        },
    ]

    contractual_kpis = [
        {
            "id": "phase0",
            "name": "Production core admission",
            "formula": "production_ready == true",
            "source": "/ready + exact-SHA release evidence",
            "target": "required",
            "owner": "IT / Security",
        },
        {
            "id": "operational_recovery",
            "name": "Operational recovery coverage",
            "formula": "critical scenarios with verified recovery path / critical scenarios",
            "source": "incident + venue + live audit trail",
            "target": "proposed 100%; agree in contract",
            "owner": "Event / Operations",
        },
        {
            "id": "partner_delivery",
            "name": "Partner contracted delivery",
            "formula": "accepted contractual deliverables / contracted deliverables",
            "source": "deliverable authority + acceptance documents",
            "target": "to_agree_before_pilot",
            "owner": "Commercial + Finance",
        },
        {
            "id": "consented_continuation",
            "name": "Consented continuation",
            "formula": "eligible participants with explicit continuation / eligible participants",
            "source": "consent + partner/community actions",
            "target": "to_agree_before_pilot",
            "owner": "Marketing / CRM",
        },
        {
            "id": "post_event_return",
            "name": "Post-event return",
            "formula": "returning participants in agreed window / attended participants",
            "source": "journey + replay + follow-up",
            "target": "to_agree_before_pilot",
            "owner": "Marketing / Analytics",
        },
        {
            "id": "accepted_net_value",
            "name": "Finance-accepted annualized net value",
            "formula": "accepted avoided spend + accepted partner contribution + accepted savings + other finance-approved value - recurring run cost",
            "source": "Finance Evidence Ledger",
            "target": "compare against tranche payback threshold",
            "owner": "Finance",
        },
    ]

    tranche_50_state = "ready_to_contract" if production else "blocked_by_phase0"
    tranche_75_state = "gated_by_50m_acceptance"
    tranche_100_state = "gated_by_75m_acceptance"

    tranches = [
        {
            "id": "t50",
            "amount_rub": 50_000_000,
            "title": "50m · Controlled Platform Pilot",
            "state": tranche_50_state,
            "what_is_built": [
                "Production-core admission and identity",
                "Flagship event operating contour",
                "Participant + agenda + QR + booking + waitlist + live/replay journey",
                "Partner deliverable / consent / evidence loop",
                "365 media / Studio MVP",
                "Pilot close pack with actual delivery cost and KPI evidence",
            ],
            "required_acceptance": ["product", "operations", "finance", "security", "sponsor"],
            "contract_kpis": ["phase0", "operational_recovery", "partner_delivery", "consented_continuation", "post_event_return", "accepted_net_value"],
            "evidence_documents": [
                "Exact-SHA production readiness record",
                "Signed pilot scope + KPI schedule",
                "Event operations close report",
                "Partner delivery acceptance pack",
                "Finance baseline / actuals / value reconciliation",
                "Investment Committee tranche decision",
            ],
            "release_rule": (
                "Release 75m expansion only after Phase 0 is live, pilot KPIs were fixed before execution, "
                "required deliverables are accepted and Finance signs the value/economics close pack."
            ),
            "current_evidence": {
                "production_core": "live" if production else "ci_proven_not_live",
                "golden_demo": "demo_proven" if golden_demo_complete else "demo_not_completed_in_current_state",
                "partner_delivery": f"{delivered}/{deliverable_total} delivered in current demo state",
                "finance_actuals": "not_available_before_paid_pilot",
            },
        },
        {
            "id": "t75",
            "amount_rub": 75_000_000,
            "title": "75m · Operating Health Relationship Platform",
            "state": tranche_75_state,
            "what_is_built": [
                "Everything accepted from the 50m tranche",
                "Editorial & Medical Review Authority",
                "Evidence / claim / expert foundation",
                "Partner CRM and delivery hardening",
                "Studio / replay / learning continuation",
                "Production observability and repeatable multi-event operations",
            ],
            "required_acceptance": ["product", "operations", "finance", "security", "medical", "sponsor"],
            "contract_kpis": ["accepted_net_value", "partner_delivery", "post_event_return"],
            "evidence_documents": [
                "50m tranche acceptance certificate",
                "Editorial / medical workflow acceptance pack",
                "Evidence / claim governance proof",
                "Second-cycle operating actuals",
                "Finance-accepted repeatability economics",
                "Investment Committee tranche decision",
            ],
            "release_rule": (
                "Release 100m scale programme only after the 50m pilot is accepted, governance is operational "
                "and a repeated cycle shows finance-accepted economics rather than one-off event effects."
            ),
            "current_evidence": {
                "prior_tranche_acceptance": "not_available_before_paid_pilot",
                "medical_governance": "gated",
                "repeatability": "unproven",
                "finance_actuals": "not_available_before_paid_pilot",
            },
        },
        {
            "id": "t100",
            "amount_rub": 100_000_000,
            "title": "100m · Strategic Platform Programme",
            "state": tranche_100_state,
            "what_is_built": [
                "Everything accepted from the 75m tranche",
                "Search and explainable personalization",
                "Evidence-governance / syndication foundations",
                "Multi-event / multi-partner configuration",
                "White-label readiness",
                "Twelve-month scale-hardening and operating programme",
            ],
            "required_acceptance": ["product", "operations", "finance", "security", "medical", "sponsor"],
            "contract_kpis": ["accepted_net_value", "partner_delivery", "post_event_return"],
            "evidence_documents": [
                "75m tranche acceptance certificate",
                "Repeatability and multi-event proof",
                "Governance / syndication acceptance pack",
                "Scale operating model and run-cost actuals",
                "Finance-accepted 12-month value case",
                "Investment Committee scale decision",
            ],
            "release_rule": (
                "Approve strategic scale only after repeatability, governance and finance-accepted value are proven; "
                "white-label demand and product-sales uplift are not assumed."
            ),
            "current_evidence": {
                "prior_tranche_acceptance": "not_available_before_paid_pilot",
                "repeatability": "unproven",
                "white_label_demand": "not_claimed",
                "validated_unit_economics": "not_claimed",
            },
        },
    ]

    evidence_ledger = [
        {
            "id": "baseline",
            "stage": "LOCK BASELINE",
            "owner": "Finance + accountable business owner",
            "required_record": "Comparison period, current spend, scope, source documents and exclusions",
            "acceptance": "Signed before pilot execution",
        },
        {
            "id": "delivery",
            "stage": "CAPTURE DELIVERY",
            "owner": "Product + Operations + Commercial",
            "required_record": "Release SHA, event operations, partner deliverables, incidents, actual run cost",
            "acceptance": "Evidence attached to contractual deliverables",
        },
        {
            "id": "kpi",
            "stage": "MEASURE KPI",
            "owner": "Analytics + accountable KPI owner",
            "required_record": "Formula, denominator, window, source and actual value",
            "acceptance": "No metric accepted if formula/source changed after execution",
        },
        {
            "id": "finance",
            "stage": "FINANCE ACCEPTANCE",
            "owner": "Finance",
            "required_record": "Value line, source, reconciliation, accepted RUB amount and double-count check",
            "acceptance": "Only accepted value enters payback",
        },
        {
            "id": "committee",
            "stage": "TRANCHE DECISION",
            "owner": "Executive Sponsor / Investment Committee",
            "required_record": "GO / ITERATE / STOP decision with unresolved risks and next gate",
            "acceptance": "Next capital is released only against accepted evidence",
        },
    ]

    decision_state = {
        "current": "CONTROLLED PILOT ONLY" if not production else "READY TO CONTRACT 50M PILOT",
        "can_release_50m": production,
        "can_release_75m": False,
        "can_release_100m": False,
        "reason": (
            "Phase 0 production admission is still required before the first contractual tranche."
            if not production
            else "Production core is admitted; commercial/KPI terms must be signed before the paid pilot."
        ),
        "truth_boundary": [
            "Demo evidence is product proof, not contractual acceptance.",
            "No tranche is auto-released by a presentation metric.",
            "Finance acceptance is required for every RUB amount used in payback.",
            "Medical governance and white-label scale stay gated until their prior dependencies are accepted.",
        ],
    }

    return {
        "version": "investment-proof-v1",
        "decision_state": decision_state,
        "acceptance_roles": acceptance_roles,
        "contractual_kpis": contractual_kpis,
        "tranches": tranches,
        "evidence_ledger": evidence_ledger,
        "demo_evidence": {
            "golden_demo_complete": golden_demo_complete,
            "partner_demo_complete": partner_demo_complete,
            "delivered_partner_items": delivered,
            "contracted_partner_items": deliverable_total,
            "event_kinds_present": sorted(event_kinds),
        },
    }
