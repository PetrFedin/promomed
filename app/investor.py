from app import db


STATUS = {
    "live": {
        "label": "LIVE",
        "meaning": "Работает в текущем runtime-контуре.",
    },
    "ci_proven": {
        "label": "CI-PROVEN",
        "meaning": "Воспроизводимо доказано в CI, но ещё не admitted в production.",
    },
    "demo": {
        "label": "DEMO",
        "meaning": "Рабочая продуктовая механика на демонстрационных данных.",
    },
    "gated": {
        "label": "GATED",
        "meaning": "Намеренно не активировано до выполнения зависимостей.",
    },
}


def _count(c, table, where=""):
    suffix = (" " + where.strip()) if where.strip() else ""
    return int(c.execute(f"SELECT COUNT(*) n FROM {table}{suffix}").fetchone()["n"])


def snapshot(c):
    readiness = db.readiness()
    production = bool(readiness.get("production_ready"))
    non_demo_accounts = _count(c, "accounts", "WHERE email NOT LIKE '%@demo.ru'")

    counts = {
        "program_items": _count(c, "program_items"),
        "content_items": _count(c, "content_catalog"),
        "speakers": _count(c, "speakers"),
        "partner_packages": _count(c, "partner_packages"),
        "partners": _count(c, "partners"),
        "community_threads": _count(c, "community_threads"),
        "learning_tracks": _count(c, "learning_tracks"),
        "venues": _count(c, "venue_state"),
        "institutional_organizations": _count(c, "institutional_organizations"),
        "evidence_exchange_packages": _count(c, "evidence_exchange_packages"),
        "evidence_exchange_deliveries": _count(c, "evidence_exchange_deliveries"),
        "qualified_syndication_partners": _count(c, "syndication_partner_qualifications", "WHERE status='qualified' AND demo_only=0"),
        "external_contributions_admitted": _count(c, "external_contributions", "WHERE status='admitted' AND demo_only=0"),
        "production_webhook_endpoints": _count(c, "syndication_delivery_endpoints", "WHERE status='active' AND demo_only=0"),
        "production_delivery_events": _count(c, "syndication_delivery_events", "WHERE demo_only=0"),
        "production_delivery_acks": _count(c, "syndication_delivery_acknowledgements", "WHERE demo_only=0"),
        "production_trust_snapshots": _count(c, "institutional_status_snapshots", "WHERE demo_only=0"),
        "production_trust_bundles": _count(c, "institutional_trust_bundles", "WHERE demo_only=0"),
        "production_external_trust_verifications": _count(c, "institutional_trust_verifications", "WHERE demo_only=0"),
        "production_federated_anchors": _count(c, "institutional_federated_anchors", "WHERE demo_only=0"),
        "production_institution_signed_receipts": _count(c, "institutional_signed_verification_receipts", "WHERE demo_only=0"),
        "production_federation_profile_evaluations": _count(c, "federation_profile_evaluations", "WHERE demo_only=0"),
        "production_federation_discovery_bundles": _count(c, "federation_discovery_bundles", "WHERE demo_only=0"),
    }

    capabilities = [
        {
            "id": "experience",
            "title": "iPhone / iPad / desktop experience",
            "status": "live",
            "proof": "Responsive browser contract and current Render runtime.",
        },
        {
            "id": "event_ops",
            "title": "Conference operations",
            "status": "demo",
            "proof": "Capacity, waitlist, check-in, venue, incidents, stream and recovery are executable in Golden Demo.",
        },
        {
            "id": "partner",
            "title": "Partner commercial loop",
            "status": "demo",
            "proof": "Deliverable -> placement -> consented action -> post-event evidence.",
        },
        {
            "id": "postgres",
            "title": "Durable PostgreSQL authority",
            "status": "live" if production else "ci_proven",
            "proof": (
                "Live PostgreSQL production readiness admitted."
                if production
                else "PostgreSQL 17 migrations, clean admission, backup/restore and fingerprint match are CI-proven."
            ),
        },
        {
            "id": "identity",
            "title": "Production identity bootstrap",
            "status": "live" if production and non_demo_accounts > 0 else "ci_proven",
            "proof": (
                "Non-demo production identity exists in admitted PostgreSQL."
                if production and non_demo_accounts > 0
                else "Create -> authenticate -> session -> rotate -> revoke is CI-proven on clean PostgreSQL."
            ),
        },
        {
            "id": "medical_review",
            "title": "Editorial & Medical Review Authority",
            "status": "gated",
            "proof": "Starts only after Phase 0 COMPLETE; current editor surface remains demonstrational.",
        },
        {
            "id": "evidence_claim",
            "title": "Evidence / Claim / Expert authorities",
            "status": "gated",
            "proof": "Sequenced after Editorial & Medical Review Authority in the master plan.",
        },
        {
            "id": "medical_info",
            "title": "Medical Information Request Desk",
            "status": "gated",
            "proof": "Commercial enterprise module reserved for later governed evidence stack.",
        },
        {
            "id": "institutional_evidence_network",
            "title": "Institutional Evidence Distribution Network",
            "status": "ci_proven",
            "proof": (
                "Versioned interchange schema, signed-checkpoint binding, publisher/consumer roles, "
                "immutable package delivery and withdrawal propagation are repository-contract proven. "
                "No external institution or commercial adoption is claimed."
            ),
        },
        {
            "id": "certified_syndication_network",
            "title": "Certified Syndication Partner Network",
            "status": "ci_proven",
            "proof": (
                "Scope-specific conformance qualification, subscriptions, withdrawal/update SLA obligations, "
                "external contribution review separation and signed admission receipts are repository-contract proven. "
                "No qualified production partner or external contribution adoption is claimed."
            ),
        },
        {
            "id": "partner_delivery_protocol",
            "title": "Partner Delivery Protocol v2",
            "status": "ci_proven",
            "proof": (
                "Signed webhook events, endpoint verification, retry/backoff, append-only delivery attempts, "
                "partner-signed acknowledgements, contiguous cursors and behaviour-driven requalification are repository-contract proven. "
                "No production endpoint, external delivery traffic or production SLA achievement is claimed."
            ),
        },
        {
            "id": "partner_trust_bundle",
            "title": "Partner Trust Bundle & Cross-Organisation Verification",
            "status": "ci_proven",
            "proof": (
                "Signed institutional status snapshots, immutable trust bundles, fresh revocation/status material "
                "and independent portable verification are repository-contract proven. "
                "No production trust snapshot, external verifier organisation or institutional adoption is claimed."
            ),
        },
        {
            "id": "federated_trust_anchors",
            "title": "Federated Trust Anchors & Institution-Signed Verification",
            "status": "ci_proven",
            "proof": (
                "Proof-of-possession, governance-admitted institutional public keys, DID/JWKS-compatible publication, "
                "rotation/revocation lineage and institution-signed verification receipts are repository-contract proven. "
                "No production external anchor, consortium, accreditation relationship or institution-signed production receipt is claimed."
            ),
        },
        {
            "id": "federation_interoperability",
            "title": "Federation Interoperability Profile & Trust Anchor Discovery",
            "status": "ci_proven",
            "proof": (
                "Versioned interoperability profile, scoped public discovery, deterministic compatibility evaluation "
                "and signed portable discovery bundles are repository-contract proven. "
                "Discovery never admits a key and no real external pilot or federation adoption is claimed."
            ),
        },
    ]

    revenue_architecture = [
        {
            "id": "platform_pilot",
            "title": "Platform pilot",
            "model": "Design + implementation + controlled pilot",
            "status": "demo",
            "evidence": "Participant, event, operations, partner and post-event paths are connected in one product.",
        },
        {
            "id": "event_layer",
            "title": "Event operating layer",
            "model": "Annual conference / event technology + operations",
            "status": "demo",
            "evidence": "Golden Demo exercises live operational state rather than static presentation screens.",
        },
        {
            "id": "partner_layer",
            "title": "Partner activation",
            "model": "Packages + deliverables + appointments + consented continuation",
            "status": "demo",
            "evidence": "Partner package and contract-evidence surfaces exist in the MVP.",
        },
        {
            "id": "media_studio",
            "title": "Media & Studio",
            "model": "Year-round content / expert / topic continuation",
            "status": "demo",
            "evidence": "Content, Studio, expert, community and learning surfaces are linked.",
        },
        {
            "id": "enterprise_information",
            "title": "Governed scientific information",
            "model": "Enterprise Medical Information / scientific-engagement module",
            "status": "gated",
            "evidence": "Commercial concept is defined but cannot activate before Evidence/Claim/Review authorities.",
        },
        {
            "id": "evidence_intelligence",
            "title": "Evidence intelligence",
            "model": "Evidence radar / editorial intelligence / re-review workflow",
            "status": "gated",
            "evidence": "Roadmap defined; no efficacy or safety inference is activated in Phase 0.",
        },
        {
            "id": "knowledge_licensing",
            "title": "Institutional knowledge distribution",
            "model": "Evidence API / governed knowledge packs / partner syndication infrastructure",
            "status": "ci_proven",
            "evidence": (
                "Machine-readable evidence packages can be bound to signed checkpoints, delivered to scoped "
                "institutional publisher/consumer roles and withdrawn when source authority changes. "
                "No external institution, commercial contract or external adoption is claimed."
            ),
        },
    ]

    defensibility = [
        {
            "title": "One measurable journey",
            "status": "demo",
            "detail": "Content -> event -> attendance -> consent -> partner action -> replay / return in one audit trail.",
        },
        {
            "title": "Consent-first relationship graph",
            "status": "demo",
            "detail": "Direct continuation and partner actions are designed around explicit permission, not silent contact export.",
        },
        {
            "title": "Operations + commercial evidence",
            "status": "demo",
            "detail": "The same authority links service execution and partner deliverables, making the product more than a media shell.",
        },
        {
            "title": "Governed modular architecture",
            "status": "ci_proven",
            "detail": "Bounded contexts, migration checks, restore proof, durable identity and fail-closed production readiness are regression-tested.",
        },
        {
            "title": "Evidence governance + institutional portability",
            "status": "ci_proven",
            "detail": (
                "Claim/source provenance, review state, Evidence Seal, signed checkpoints, public-key verification "
                "and institutional package withdrawal propagation now form a machine-checkable distribution rail."
            ),
        },
        {
            "title": "Qualified institutional participation",
            "status": "ci_proven",
            "detail": (
                "Partner conformance is scope-specific and revocable; subscriptions carry measurable update/withdrawal SLAs; "
                "external contributors cannot self-review or mutate canonical claims and receive signed admission receipts only after review."
            ),
        },
        {
            "title": "Observed partner delivery behaviour",
            "status": "ci_proven",
            "detail": (
                "Immutable delivery events, signed attempts, acknowledgement evidence, cursor continuity and SLA observations "
                "can feed requalification decisions without granting the automation authority to suspend or revoke a partner."
            ),
        },
        {
            "title": "Portable institutional trust state",
            "status": "ci_proven",
            "detail": (
                "Partner qualification, delivery cursor and observed process status can be frozen into signed snapshots, "
                "verified without database access and cross-checked against fresh revocation/status material."
            ),
        },
        {
            "title": "Federated institutional trust chain",
            "status": "ci_proven",
            "detail": (
                "Promomed governance can bind independently controlled institutional public keys after proof-of-possession, "
                "publish DID/JWKS-compatible status and verify institution-signed receipts without taking custody of external private keys."
            ),
        },
        {
            "title": "Discoverable federation without auto-trust",
            "status": "ci_proven",
            "detail": (
                "A versioned federation profile and scoped discovery bundle make public trust capabilities machine-discoverable "
                "while keeping compatibility separate from governance admission, accreditation and external adoption."
            ),
        },
    ]

    capital_milestones = [
        {
            "id": "phase0",
            "title": "Phase 0 · Durable Core",
            "status": "live" if production else "ci_proven",
            "decision": "Admit isolated PostgreSQL source + restore capacity and prove exact-main production readiness.",
        },
        {
            "id": "phase1",
            "title": "Phase 1 · Editorial & Medical Review",
            "status": "gated",
            "decision": "Open only after Phase 0 COMPLETE; establish versioned review, disclosure and approval authority.",
        },
        {
            "id": "phase2",
            "title": "Phase 2 · Evidence / Claim / Expert",
            "status": "gated",
            "decision": "Turn reviewed scientific context into durable, auditable enterprise assets.",
        },
        {
            "id": "phase3",
            "title": "Phase 3 · Scientific Information",
            "status": "gated",
            "decision": "Activate governed request/response workflow and an approved response library.",
        },
        {
            "id": "scale",
            "title": "Scale · Repeatable Health Platform",
            "status": "gated",
            "decision": "Prove a repeatable operating and commercial model before broader white-label expansion.",
        },
    ]

    investor_thesis = {
        "category": "Health relationship + event operating system",
        "statement": (
            "СОСТОЯНИЕ соединяет year-round media, live event operations, consent-first partner activation "
            "и измеримый post-event relationship loop в одном управляемом продукте."
        ),
        "what_is_not": "Не агентский лендинг, не приложение-афиша и не медицинский сервис.",
        "value_creation_logic": [
            "Repeatable platform capability instead of one-off event production.",
            "Commercial evidence and first-party consent signals instead of vanity reach.",
            "Governed health-content roadmap instead of unbounded AI claims.",
            "Operational authority + audit trail create switching cost and diligence evidence.",
        ],
    }

    public_company_context = {
        "basis": "Public PROMOMED FY2025 IFRS scale reference",
        "period": "FY2025",
        "revenue_rub": 37_600_000_000,
        "adjusted_ebitda_rub": 15_269_777_000,
        "net_profit_rub": 7_167_850_000,
        "sources": [
            {
                "label": "PROMOMED FY2025 IFRS financial statements",
                "published": "2026-04-20",
                "url": "https://promomed.ru/upload/iblock/814/uszvgetwqkl33qk501ngas66yy0jubu6/%D0%A4%D0%B8%D0%BD%D0%B0%D0%BD%D1%81%D0%BE%D0%B2%D0%B0%D1%8F%20%D0%BE%D1%82%D1%87%D0%B5%D1%82%D0%BD%D0%BE%D1%81%D1%82%D1%8C%20%D0%BF%D0%BE%20%D0%9C%D0%A1%D0%A4%D0%9E%20%D0%B7%D0%B0%202025.pdf",
            }
        ],
        "boundary": (
            "Public company scale is used only to contextualize the size of a 50-100m RUB programme. "
            "It is not evidence that the programme will produce a specific return."
        ),
    }

    investment_envelopes = [
        {
            "id": "controlled_50",
            "amount_rub": 50_000_000,
            "label": "50m · Controlled Platform Pilot",
            "purpose": "Buy the smallest credible enterprise proof cycle rather than a one-off event build.",
            "includes": [
                "Production core admission and release evidence",
                "One flagship conference operating contour",
                "Participant / agenda / QR / booking / waitlist / live-replay journey",
                "Partner delivery + consented continuation + evidence report",
                "365 media / Studio MVP using the existing product surfaces",
                "Finance-ready pilot close pack with actual delivery cost and KPI evidence",
            ],
            "excludes": [
                "Full multi-brand rollout",
                "White-label commercialization",
                "Unbounded medical/claim automation",
            ],
            "commercial_state": "illustrative_envelope_not_quote",
        },
        {
            "id": "operating_75",
            "amount_rub": 75_000_000,
            "label": "75m · Operating Health Relationship Platform",
            "purpose": "Fund the controlled pilot plus the governance and operating capabilities needed for repeatability.",
            "includes": [
                "Everything in the 50m envelope",
                "Editorial & Medical Review Authority implementation",
                "Evidence / claim / expert foundation",
                "Partner CRM / delivery workflow hardening",
                "Studio / replay / learning continuation workflow",
                "Production observability, operating runbooks and multi-event readiness",
            ],
            "excludes": [
                "Nationwide white-label scale before paid-pilot evidence",
                "Guaranteed revenue or product-sales uplift",
            ],
            "commercial_state": "illustrative_envelope_not_quote",
        },
        {
            "id": "strategic_100",
            "amount_rub": 100_000_000,
            "label": "100m · Strategic Platform Programme",
            "purpose": "Fund a reusable enterprise platform and the first scale-ready year, not just a pilot delivery.",
            "includes": [
                "Everything in the 75m envelope",
                "Search / explainable personalization / knowledge discovery",
                "Evidence-governance and syndication foundations",
                "Multi-event / multi-partner configuration",
                "White-label readiness without claiming market demand",
                "Twelve-month operating, measurement and scale-hardening programme",
            ],
            "excludes": [
                "Paid traction claims before actual contracts",
                "Clinical decision support or personalized treatment",
            ],
            "commercial_state": "illustrative_envelope_not_quote",
        },
    ]

    payback_reference = []
    for envelope in investment_envelopes:
        amount = float(envelope["amount_rub"])
        thresholds = []
        for months in (6, 12, 18, 24):
            annual_value = amount * 12.0 / months
            thresholds.append({
                "months": months,
                "annual_verified_value_rub": round(annual_value),
                "pct_fy2025_revenue": round(annual_value / public_company_context["revenue_rub"] * 100.0, 3),
                "pct_fy2025_adjusted_ebitda": round(annual_value / public_company_context["adjusted_ebitda_rub"] * 100.0, 3),
            })
        payback_reference.append({
            "id": envelope["id"],
            "amount_rub": envelope["amount_rub"],
            "amount_pct_fy2025_revenue": round(amount / public_company_context["revenue_rub"] * 100.0, 3),
            "amount_pct_fy2025_adjusted_ebitda": round(amount / public_company_context["adjusted_ebitda_rub"] * 100.0, 3),
            "thresholds": thresholds,
        })

    value_levers = [
        {
            "id": "budget_substitution",
            "priority": 1,
            "title": "Replace fragmented external spend",
            "logic": "Move already-budgeted event-tech, agency, content-production and reporting work into one reusable platform where finance can verify avoided spend.",
            "evidence_needed": "Finance-approved current supplier / agency / event-tech baseline and like-for-like scope.",
            "base_case": True,
        },
        {
            "id": "contracted_partner_value",
            "priority": 2,
            "title": "Contract partner inventory before the event",
            "logic": "Turn partner packages into contracted deliverables with fulfillment evidence instead of post-hoc sponsorship reporting.",
            "evidence_needed": "Signed partner contracts, contracted deliverables, recognized contribution and delivery cost.",
            "base_case": True,
        },
        {
            "id": "reuse",
            "priority": 3,
            "title": "Reuse one platform across 365 media + multiple events",
            "logic": "Amortize product, content and operating capability across repeated launches instead of rebuilding event microsites and workflows each time.",
            "evidence_needed": "Historic cost per event/content launch versus actual platform run cost.",
            "base_case": True,
        },
        {
            "id": "operations",
            "priority": 4,
            "title": "Reduce manual operations and recovery cost",
            "logic": "Automate registration, QR, waitlist, venue changes, notifications, partner evidence and reporting; measure hours and outsourced cost removed.",
            "evidence_needed": "Baseline staff/vendor hours and actual post-pilot operating hours/cost.",
            "base_case": True,
        },
        {
            "id": "owned_relationship",
            "priority": 5,
            "title": "Increase return through an owned consent-first audience",
            "logic": "Measure whether the same audience returns to content, replay and future events without repurchasing the relationship from scratch.",
            "evidence_needed": "Agreed attribution window, returning-user denominator and marketing acquisition baseline.",
            "base_case": False,
        },
        {
            "id": "product_sales",
            "priority": 99,
            "title": "Product-sales uplift",
            "logic": "Do not include in the base ROI case unless legal/compliance approve the attribution model and finance validates incremental contribution.",
            "evidence_needed": "Approved attribution methodology, compliant data basis and finance-approved incremental contribution.",
            "base_case": False,
            "gated": True,
        },
    ]

    value_capture_map = [
        {
            "id": "budget_baseline",
            "order": 1,
            "title": "Current budget baseline",
            "owner": "Finance + Marketing + Event owner",
            "status": "input_required",
            "counting": "discovery_only",
            "baseline": "Current annual spend by agency, event-tech, media/content production, reporting and event operations scope.",
            "formula": "baseline_pool = sum(finance-approved comparable current spend)",
            "proof": "Budget ledger + contracts + purchase orders + actual invoices for the agreed comparison period.",
            "decision": "Defines the addressable cost pool; it is not counted as value by itself.",
            "input_id": None,
        },
        {
            "id": "external_substitution",
            "order": 2,
            "title": "Replace fragmented external spend",
            "owner": "Finance + Procurement + Marketing",
            "status": "base_case",
            "counting": "counts_once",
            "baseline": "Like-for-like spend that the platform actually replaces, not the whole marketing/event budget.",
            "formula": "verified_avoided_spend = replaced_external_cost - replacement_run_cost_allocated_here",
            "proof": "Cancelled/reduced supplier scope + approved new scope + finance reconciliation.",
            "decision": "Fastest value source because it converts an existing budget into measurable avoided spend.",
            "input_id": "valueAvoided",
        },
        {
            "id": "partner_inventory",
            "order": 3,
            "title": "Partner inventory and contracted contribution",
            "owner": "Partnerships + Commercial + Finance",
            "status": "base_case",
            "counting": "counts_once",
            "baseline": "Partner packages, placements, appointments, content inventory and contracted deliverables.",
            "formula": "partner_net_value = recognized_partner_contribution - direct_partner_delivery_cost",
            "proof": "Signed contract + deliverable ledger + acceptance evidence + finance-recognized contribution.",
            "decision": "Turns sponsorship from a logo package into auditable commercial inventory.",
            "input_id": "valuePartner",
        },
        {
            "id": "content_reuse",
            "order": 4,
            "title": "Reuse content and platform capability",
            "owner": "Marketing + Medical/Editorial + Product",
            "status": "base_case",
            "counting": "counts_once",
            "baseline": "Historic cost of recreating microsites, content packages, video/replay assets and event workflows.",
            "formula": "reuse_saving = comparable_rebuild_cost - incremental_reuse_cost",
            "proof": "Historic launch/event cost cards + new incremental production cost + reuse ledger.",
            "decision": "One governed asset is reused across 365 media, event, replay, education and partner surfaces.",
            "input_id": "valueReuse",
        },
        {
            "id": "operations",
            "order": 5,
            "title": "Operations productivity and recovery",
            "owner": "Event Operations + Product + Finance",
            "status": "base_case",
            "counting": "counts_once",
            "baseline": "Manual hours, outsourced support and recovery cost for registration, QR, waitlist, communications and reporting.",
            "formula": "ops_saving = baseline_people_and_vendor_cost - actual_platform_operating_cost",
            "proof": "Pre-pilot time/cost baseline + post-pilot actuals + incident/recovery ledger.",
            "decision": "Measures whether orchestration removes work rather than simply moving it to another team.",
            "input_id": "valueOps",
        },
        {
            "id": "owned_365_audience",
            "order": 6,
            "title": "365 owned relationship value",
            "owner": "Marketing + CRM + Analytics + Finance",
            "status": "upside_until_proven",
            "counting": "finance_approved_only",
            "baseline": "Cost to reacquire comparable audience and observed return/consented continuation behavior.",
            "formula": "approved_relationship_value = finance-approved avoided_reacquisition_or_incremental_contribution",
            "proof": "Consent log + return cohort + agreed attribution window + acquisition baseline + finance approval.",
            "decision": "Strategic upside; excluded from base case until attribution and finance treatment are agreed.",
            "input_id": "valueAudience",
        },
    ]

    value_evidence_protocol = {
        "steps": [
            "LOCK BASELINE · agree comparison scope and source documents before the pilot",
            "CAPTURE ACTUALS · platform, vendor, partner and operating actuals are recorded during delivery",
            "RECONCILE · finance maps each economic effect to exactly one value bucket",
            "ACCEPT · accountable owner signs the evidence pack for each counted value line",
            "DECIDE · GO / ITERATE / STOP and next capital tranche use accepted value, not presentation metrics",
        ],
        "minimum_fields": [
            "owner",
            "baseline_period",
            "baseline_source",
            "formula",
            "actual_source",
            "accepted_value_rub",
            "accepted_by",
            "accepted_at",
        ],
        "guardrail": "No value line enters payback twice; audience/product-sales effects stay outside base case until Finance approves attribution.",
    }

    value_case_truth = {
        "price_claim": "50-100m RUB is presented as a scoped programme envelope, not an asserted valuation.",
        "payback_formula": "payback_months = investment / annual_verified_net_value * 12",
        "annual_verified_net_value_formula": (
            "verified avoided spend + recognized partner contribution + verified operating savings "
            "+ other finance-approved incremental contribution - recurring platform run cost"
        ),
        "double_count_guardrail": "The same economic effect may appear in one value bucket only.",
        "fastest_path": (
            "Prioritize already-budgeted spend substitution and contracted partner value first; "
            "treat retention and product-sales uplift as upside until real pilot evidence exists."
        ),
    }

    diligence_domains = [
        {
            "id": "product_experience",
            "title": "Product experience",
            "status": "live",
            "question": "Есть ли цельный пользовательский продукт, а не набор экранов?",
            "evidence": "Participant journey, Inbox, event, community and investor surfaces run in the current responsive web runtime.",
        },
        {
            "id": "technical_architecture",
            "title": "Technical architecture",
            "status": "ci_proven",
            "question": "Можно ли масштабировать код без возврата к HTTP-монолиту?",
            "evidence": "Bounded read/write contexts, architecture regression gates and PostgreSQL compatibility are CI-proven.",
        },
        {
            "id": "persistence",
            "title": "Durable production state",
            "status": "live" if production else "ci_proven",
            "question": "Есть ли admitted production data authority?",
            "evidence": (
                "Durable PostgreSQL is admitted live."
                if production
                else "Clean PostgreSQL admission and restore are CI-proven; external live source/restore capacity remains the Phase 0 blocker."
            ),
        },
        {
            "id": "commercial_loop",
            "title": "Commercial execution",
            "status": "demo",
            "question": "Можно ли связать партнёрское обещание с измеримым исполнением?",
            "evidence": "Partner package -> deliverable -> appointment/placement -> consented action -> evidence is executable in Golden Demo.",
        },
        {
            "id": "market_traction",
            "title": "Market traction",
            "status": "gated",
            "question": "Есть ли доказанная готовность рынка платить и возвращаться?",
            "evidence": "Not claimed in MVP. Requires a paid pilot and agreed success criteria.",
        },
        {
            "id": "medical_governance",
            "title": "Medical / editorial governance",
            "status": "gated",
            "question": "Можно ли безопасно масштабировать governed health content?",
            "evidence": "Not activated before Phase 0 COMPLETE and PROMO-INT-02 review authority.",
        },
        {
            "id": "economics",
            "title": "Commercial economics",
            "status": "demo",
            "question": "Проверена ли unit economics?",
            "evidence": "Scenario calculator is assumption-only. Real pricing, delivery cost and conversion require the funded pilot.",
        },
    ]

    risk_register = [
        {
            "id": "infra_capacity",
            "severity": "blocking" if not production else "controlled",
            "title": "Durable PostgreSQL capacity",
            "mitigation": (
                "Admit an isolated source + restore PostgreSQL and run the existing fail-closed workflow."
                if not production
                else "Live admission proof is green; keep restore evidence current."
            ),
        },
        {
            "id": "governance",
            "severity": "gated",
            "title": "Medical / editorial authority",
            "mitigation": "Do not activate medical claims, evidence intelligence or scientific-information delivery before PROMO-INT-02 and later authorities.",
        },
        {
            "id": "traction",
            "severity": "unproven",
            "title": "Paid market traction",
            "mitigation": "Use the first funded pilot to validate willingness to pay, partner renewal intent and participant return rather than projecting them.",
        },
        {
            "id": "concentration",
            "severity": "measure",
            "title": "Revenue concentration",
            "mitigation": "Use the scenario lab and pilot actuals to measure dependence on platform fee vs partner/media/experience lines.",
        },
        {
            "id": "execution",
            "severity": "demo_proven",
            "title": "Event operating execution",
            "mitigation": "Golden Demo already exercises capacity, waitlist, venue change, stream recovery, check-in and partner evidence; paid pilot must prove the same under real load.",
        },
    ]

    scale_paths = [
        {
            "title": "Flagship annual event + 365 relationship",
            "status": "demo",
            "why": "Existing participant, event, media, community and post-event journeys already connect in one product.",
        },
        {
            "title": "Partner activation platform",
            "status": "demo",
            "why": "Packages, appointments, deliverables, consent and evidence can form a repeatable B2B layer.",
        },
        {
            "title": "Studio / expert / topic network",
            "status": "demo",
            "why": "Content, speakers, Studio, learning and community provide a year-round return loop.",
        },
        {
            "title": "Governed scientific-information platform",
            "status": "gated",
            "why": "High-value enterprise path, but it opens only after review, evidence, claim and expert authorities exist.",
        },
        {
            "title": "White-label operating system",
            "status": "gated",
            "why": "Potential scale path only after a repeatable paid pilot proves configuration, operations and commercial economics.",
        },
    ]

    committee_state = {
        "evidence_state": "pilot_diligence_ready" if not production else "production_core_admitted",
        "current_scope": (
            "Investor diligence + controlled pilot preparation"
            if not production
            else "Production-core pilot preparation"
        ),
        "next_gate": (
            "Phase 0 COMPLETE: live durable PostgreSQL + production account + authenticated smoke"
            if not production
            else "PROMO-INT-02 Editorial & Medical Review Authority"
        ),
        "not_claimed": [
            "Paid market traction",
            "Validated unit economics",
            "Production medical governance",
            "Revenue forecast or valuation",
        ],
    }

    blockers = []
    if not production:
        blockers.append({
            "id": "durable_postgres",
            "title": "External durable PostgreSQL",
            "state": "blocking",
            "detail": "Repository proof tooling is ready; live source + restore capacity is not yet admitted.",
        })

    return {
        "status_taxonomy": STATUS,
        "runtime": {
            "backend": readiness.get("backend"),
            "durable": bool(readiness.get("durable")),
            "production_ready": production,
            "demo_seed_enabled": bool(readiness.get("demo_seed_enabled")),
            "demo_accounts": int(readiness.get("demo_accounts", 0)),
            "non_demo_accounts": non_demo_accounts,
        },
        "counts": counts,
        "capabilities": capabilities,
        "revenue_architecture": revenue_architecture,
        "defensibility": defensibility,
        "capital_milestones": capital_milestones,
        "investor_thesis": investor_thesis,
        "public_company_context": public_company_context,
        "investment_envelopes": investment_envelopes,
        "payback_reference": payback_reference,
        "value_levers": value_levers,
        "value_capture_map": value_capture_map,
        "value_evidence_protocol": value_evidence_protocol,
        "value_case_truth": value_case_truth,
        "diligence_domains": diligence_domains,
        "risk_register": risk_register,
        "scale_paths": scale_paths,
        "committee_state": committee_state,
        "blockers": blockers,
        "disclaimers": [
            "MVP metrics are demo/runtime evidence, not market traction.",
            "No revenue, valuation, audience or medical-outcome forecast is implied by this proof layer.",
            "GATED modules are roadmap scope, not delivered production capability.",
        ],
    }
