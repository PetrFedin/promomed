from app import investor


def snapshot(c):
    proof = investor.snapshot(c)
    production = bool(proof["runtime"]["production_ready"])

    audience_modes = [
        {
            "id": "ceo",
            "label": "CEO",
            "question": "Почему компании стоит финансировать следующий доказательный цикл?",
            "focus": ["strategic_fit", "value_creation", "decision", "next_gate"],
        },
        {
            "id": "cvc",
            "label": "CVC / IC",
            "question": "Как капитал превращается в проверяемую capability и когда открывается следующий транш?",
            "focus": ["funding", "risk", "economics", "scale"],
        },
        {
            "id": "partner",
            "label": "Strategic partner",
            "question": "Какую ценность получает партнёр и где проходят границы данных и влияния?",
            "focus": ["value_exchange", "commercial_proof", "data_boundary", "renewal_evidence"],
        },
        {
            "id": "procurement",
            "label": "Procurement / Security",
            "question": "Что уже можно проверить технически и что ещё нельзя считать production-ready?",
            "focus": ["architecture", "security", "continuity", "governance"],
        },
    ]

    board_summary = {
        "decision_state": "production_core_pilot" if production else "controlled_pilot_only",
        "decision_label": (
            "PRODUCTION-CORE PILOT"
            if production
            else "CONTROLLED PILOT ONLY"
        ),
        "thesis": (
            "Финансировать следующий доказательный цикл health relationship platform: "
            "year-round media + event operations + consent-first partner activation + post-event relationship evidence."
        ),
        "ask": (
            "Одобрить ограниченный пилот с заранее зафиксированными evidence gates; "
            "не одобрять масштабирование до подтверждения traction, economics и governance."
        ),
        "next_gate": proof["committee_state"]["next_gate"],
        "production_ready": production,
    }

    funding_tranches = [
        {
            "id": "t0",
            "title": "Tranche 0 · Durable Core",
            "status": "complete" if production else "blocking",
            "capital_use": "Production persistence, restore authority, production identity and authenticated smoke.",
            "release_gate": "Phase 0 COMPLETE",
            "evidence": (
                "Live durable PostgreSQL + production account + authenticated smoke."
                if production
                else "Repository/CI proof is green; external durable PostgreSQL source + restore capacity remains outstanding."
            ),
        },
        {
            "id": "t1",
            "title": "Tranche 1 · Controlled Pilot",
            "status": "eligible_after_t0" if not production else "eligible",
            "capital_use": "Pilot configuration, real event operation, partner delivery and post-event measurement.",
            "release_gate": "Phase 0 COMPLETE + signed pilot success criteria",
            "evidence": "Real attendance, operational recovery, consented partner actions, post-event return and actual delivery cost.",
        },
        {
            "id": "t2",
            "title": "Tranche 2 · Governed Health Content",
            "status": "gated",
            "capital_use": "Editorial & Medical Review Authority and then evidence/claim/expert authorities.",
            "release_gate": "PROMO-INT-02 accepted",
            "evidence": "Versioned review, disclosure, approval, audit and re-review proof.",
        },
        {
            "id": "t3",
            "title": "Tranche 3 · Scale",
            "status": "gated",
            "capital_use": "Repeatable multi-event / partner / white-label expansion.",
            "release_gate": "Paid pilot economics + repeatability + governance",
            "evidence": "Actual commercial economics, renewal intent, repeatable configuration and operational performance.",
        },
    ]

    programme_value_case = {
        "headline": "50-100m RUB buys a governed operating platform and a measurable proof cycle, not a microsite.",
        "envelopes": proof.get("investment_envelopes", []),
        "payback_reference": proof.get("payback_reference", []),
        "value_levers": proof.get("value_levers", []),
        "public_company_context": proof.get("public_company_context", {}),
        "truth": proof.get("value_case_truth", {}),
    }

    pilot_contract = {
        "objective": "Prove that СОСТОЯНИЕ can operate as a measurable year-round health relationship platform, not just an event interface.",
        "in_scope": [
            "Participant experience and agenda",
            "Live event operations and recovery",
            "Partner deliverables and appointments",
            "Consent-first continuation",
            "Post-event replay / return",
            "Actual pilot cost and delivery evidence",
        ],
        "out_of_scope": [
            "Personalized medical advice",
            "Production medical-claim automation",
            "Unreviewed evidence scoring",
            "White-label scale before repeatability proof",
            "Guaranteed commercial uplift",
        ],
        "client_inputs": [
            "Named pilot owner and decision rights",
            "Approved pilot scope and success criteria",
            "Required legal/privacy/security reviews",
            "Partner roster and approved deliverables",
            "Production infrastructure decision",
        ],
        "exit_decision": "GO / ITERATE / STOP based on agreed evidence, not presentation quality.",
    }

    kpi_dictionary = [
        {
            "id": "attendance",
            "name": "Attendance conversion",
            "formula": "verified attendance / registered participants",
            "source": "registration + check-in authority",
            "target": "to_agree_before_pilot",
        },
        {
            "id": "operational_recovery",
            "name": "Operational recovery",
            "formula": "critical scenarios with verified recovery path / critical scenarios",
            "source": "incident + venue + live audit trail",
            "target": "proposed: 100% recovery-path coverage",
        },
        {
            "id": "partner_delivery",
            "name": "Partner delivery completion",
            "formula": "delivered contractual items / contracted items",
            "source": "partner deliverable authority",
            "target": "to_agree_before_pilot",
        },
        {
            "id": "consented_continuation",
            "name": "Consented continuation",
            "formula": "participants with explicit follow-up action / eligible participants",
            "source": "consent + partner/community actions",
            "target": "to_agree_before_pilot",
        },
        {
            "id": "return",
            "name": "Post-event return",
            "formula": "unique returning participants in agreed window / attended participants",
            "source": "journey + replay + follow-up",
            "target": "to_agree_before_pilot",
        },
        {
            "id": "delivery_cost",
            "name": "Actual delivery cost",
            "formula": "verified direct pilot delivery cost",
            "source": "finance-approved pilot cost ledger",
            "target": "measure_actual",
        },
        {
            "id": "contribution",
            "name": "Contribution scenario vs actual",
            "formula": "recognized pilot commercial value - verified direct delivery cost",
            "source": "finance-approved actuals",
            "target": "measure_after_pilot",
        },
    ]

    corporate_readiness = [
        {
            "id": "architecture",
            "title": "Architecture boundaries",
            "status": "ci_proven",
            "owner": "Product / Engineering",
            "evidence": "Bounded read/write contexts, regression gates and PostgreSQL compatibility.",
        },
        {
            "id": "identity",
            "title": "Authentication & production identity",
            "status": "live" if production else "ci_proven",
            "owner": "Engineering / Security",
            "evidence": (
                "Production identity is admitted on durable runtime."
                if production
                else "scrypt credentials, sessions, rotation and revocation are CI-proven; live production identity waits for Phase 0."
            ),
        },
        {
            "id": "continuity",
            "title": "Backup / restore continuity",
            "status": "live" if production else "ci_proven",
            "owner": "Engineering / Operations",
            "evidence": (
                "Live durable restore evidence is admitted."
                if production
                else "Clean PostgreSQL backup -> isolated restore -> fingerprint match is CI-proven."
            ),
        },
        {
            "id": "privacy",
            "title": "Consent-first data boundary",
            "status": "demo",
            "owner": "Product / Legal / Privacy",
            "evidence": "Partner continuation and direct messaging require explicit allowed relationship paths in the demo authority.",
        },
        {
            "id": "vendor",
            "title": "Vendor / procurement diligence",
            "status": "gated",
            "owner": "Procurement / Legal / Security",
            "evidence": "Production vendor assessment, DPAs, SLAs, hosting and support terms are not yet approved.",
        },
        {
            "id": "medical",
            "title": "Medical / editorial governance",
            "status": "gated",
            "owner": "Medical / Legal / Editorial",
            "evidence": "PROMO-INT-02 and later evidence/claim authorities are intentionally not active.",
        },
        {
            "id": "observability",
            "title": "Production observability & incident response",
            "status": "gated",
            "owner": "Engineering / Operations",
            "evidence": "Demo operations are instrumented; production SLO/on-call/alerting evidence is not yet claimed.",
        },
    ]

    strategic_partner_exchange = {
        "partner_provides": [
            "Approved category role / offer",
            "Named accountable owner",
            "Contracted deliverables",
            "Approved content / disclosure inputs",
            "Service capacity and fulfillment rules",
        ],
        "platform_provides": [
            "Contextual discovery inside participant journey",
            "Appointments / placements / activation mechanics",
            "Consent-first continuation",
            "Delivery evidence",
            "Post-event performance evidence",
        ],
        "never_implied": [
            "Access to sensitive health data",
            "Silent participant contact export",
            "Influence over medical/editorial approval",
            "Guaranteed leads or revenue",
        ],
    }

    data_room = [
        {
            "id": "architecture",
            "title": "Architecture & bounded contexts",
            "status": "available",
            "reference": "docs/IMPLEMENTED_SCOPE.md",
            "purpose": "What is implemented and which authorities are separated.",
        },
        {
            "id": "master_plan",
            "title": "Integration master plan",
            "status": "available",
            "reference": "docs/PROMOMED_INTEGRATION_MASTER_PLAN_2026-10-01.md",
            "purpose": "Dependency order, acceptance gates and future modules.",
        },
        {
            "id": "deployment",
            "title": "Deployment evidence ledger",
            "status": "available",
            "reference": "docs/DEPLOYMENT_STATE.md",
            "purpose": "Exact-SHA deploy and workflow proof history.",
        },
        {
            "id": "investor_research",
            "title": "Investor readiness rationale",
            "status": "available",
            "reference": "docs/INVESTOR_READINESS_2026-10-05.md",
            "purpose": "Positioning logic and external research used by the investor layer.",
        },
        {
            "id": "executive_room",
            "title": "Executive / CVC decision specification",
            "status": "available",
            "reference": "docs/EXECUTIVE_CVC_ROOM_2026-10-05.md",
            "purpose": "Decision state, milestone funding, pilot contract, KPI and truth-boundary specification.",
        },
        {
            "id": "security_pack",
            "title": "Security / privacy / vendor readiness pack",
            "status": "available",
            "reference": "docs/CORPORATE_SECURITY_PRIVACY_VENDOR_PACK_2026-10-05.md",
            "purpose": "Evidence-backed current controls, data inventory, procurement gaps and production security exit criteria. Not a certification or approval.",
        },
        {
            "id": "pilot_actuals",
            "title": "Paid pilot actuals",
            "status": "gated",
            "reference": "future pilot close pack",
            "purpose": "Finance-approved cost, delivery, traction and renewal evidence.",
        },
    ]

    return {
        "board_summary": board_summary,
        "audience_modes": audience_modes,
        "funding_tranches": funding_tranches,
        "programme_value_case": programme_value_case,
        "pilot_contract": pilot_contract,
        "kpi_dictionary": kpi_dictionary,
        "corporate_readiness": corporate_readiness,
        "strategic_partner_exchange": strategic_partner_exchange,
        "data_room": data_room,
        "truth_boundary": {
            "can_show_to_executives": True,
            "can_claim_production_ready": production,
            "can_claim_market_traction": False,
            "can_claim_validated_unit_economics": False,
            "can_claim_medical_governance": False,
        },
    }
