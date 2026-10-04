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
            "title": "Future evidence governance",
            "status": "gated",
            "detail": "Evidence, claims, experts and scientific-information workflows become the enterprise moat only after review authority exists.",
        },
    ]

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
        "blockers": blockers,
        "disclaimers": [
            "MVP metrics are demo/runtime evidence, not market traction.",
            "No revenue, valuation, audience or medical-outcome forecast is implied by this proof layer.",
            "GATED modules are roadmap scope, not delivered production capability.",
        ],
    }
