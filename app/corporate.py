from app import db, investor


def snapshot(c):
    readiness = db.readiness()
    production = bool(readiness.get("production_ready"))
    proof = investor.snapshot(c)

    controls = [
        {
            "id": "password_storage",
            "domain": "Identity",
            "title": "Password storage",
            "status": "ci_proven",
            "evidence": "Salted scrypt password hashes with constant-time comparison.",
            "source": "app/auth.py + persistence CI",
            "owner": "Engineering / Security",
        },
        {
            "id": "session_security",
            "domain": "Identity",
            "title": "Session lifecycle",
            "status": "ci_proven",
            "evidence": "Random bearer token, SHA-256 token hash at rest, TTL, revocation and expired-session cleanup.",
            "source": "app/auth.py + account rotation CI",
            "owner": "Engineering / Security",
        },
        {
            "id": "production_identity",
            "domain": "Identity",
            "title": "Production identity bootstrap",
            "status": "live" if production else "ci_proven",
            "evidence": (
                "Non-demo production identity is admitted on durable runtime."
                if production
                else "Create -> authenticate -> session -> rotate -> revoke is proven on clean PostgreSQL CI."
            ),
            "source": "ops/provision_account.py + persistence CI",
            "owner": "Engineering / Security",
        },
        {
            "id": "role_gates",
            "domain": "Authorization",
            "title": "Role-gated command boundaries",
            "status": "ci_proven",
            "evidence": "Negative tests reject unauthorized participant/organizer/editor/demo-control operations.",
            "source": "tests/test_command_boundaries.py",
            "owner": "Engineering / Product",
        },
        {
            "id": "consent_partner",
            "domain": "Privacy",
            "title": "Consent before partner continuation",
            "status": "ci_proven",
            "evidence": "Lead/product-interest commands reject consent=false and record only explicit allowed actions.",
            "source": "tests/test_command_boundaries.py",
            "owner": "Product / Privacy",
        },
        {
            "id": "consent_messaging",
            "domain": "Privacy",
            "title": "Direct-message relationship boundary",
            "status": "ci_proven",
            "evidence": "Participant-to-participant messaging requires a confirmed mutual relationship; organizer contact remains an explicit exception.",
            "source": "app/community_commands.py + browser/command tests",
            "owner": "Product / Privacy",
        },
        {
            "id": "migration_integrity",
            "domain": "Data integrity",
            "title": "Versioned migration integrity",
            "status": "ci_proven",
            "evidence": "Applied migration checksums are stored and checksum drift fails the migration/readiness path.",
            "source": "app/db.py",
            "owner": "Engineering",
        },
        {
            "id": "backup_restore",
            "domain": "Continuity",
            "title": "Backup / isolated restore",
            "status": "live" if production else "ci_proven",
            "evidence": (
                "Live durable backup/restore evidence admitted."
                if production
                else "PostgreSQL 17 backup -> isolated restore -> catalog/count/migration fingerprint equality is CI-proven."
            ),
            "source": ".github/workflows/persistence-authority.yml",
            "owner": "Engineering / Operations",
        },
        {
            "id": "fail_closed_readiness",
            "domain": "Release",
            "title": "Fail-closed production readiness",
            "status": "ci_proven",
            "evidence": "Production readiness requires durable PostgreSQL, complete schema, no checksum drift, demo seed off and zero demo accounts.",
            "source": "app/db.py + live proof workflows",
            "owner": "Engineering / Operations",
        },
        {
            "id": "exact_sha_release",
            "domain": "Release",
            "title": "Exact-SHA release proof",
            "status": "demo",
            "evidence": "Public live proof checks deployed git_commit, UI markers and fail-closed readiness. Render auto-deploy latency remains operationally monitored.",
            "source": ".github/workflows/live-render-proof.yml",
            "owner": "Engineering / Operations",
        },
        {
            "id": "incident_runbook",
            "domain": "Operations",
            "title": "Production incident-response runbook",
            "status": "to_prepare",
            "evidence": "Demo incident mechanics exist; production severity, escalation, on-call, comms and evidence-retention procedures are not yet approved.",
            "source": "future corporate security pack",
            "owner": "Engineering / Operations / Security",
        },
        {
            "id": "rto_rpo",
            "domain": "Continuity",
            "title": "RTO / RPO commitments",
            "status": "to_prepare",
            "evidence": "Restore mechanics are proven; contractual recovery objectives are intentionally not invented.",
            "source": "future SLA / BCP approval",
            "owner": "Operations / Legal / Business",
        },
        {
            "id": "vendor_terms",
            "domain": "Vendor",
            "title": "Hosting / subprocessors / DPA / SLA approval",
            "status": "to_prepare",
            "evidence": "Current infrastructure can be inspected, but production vendor terms and data-processing agreements are not yet approved.",
            "source": "future vendor due-diligence pack",
            "owner": "Procurement / Legal / Privacy",
        },
        {
            "id": "encryption_evidence",
            "domain": "Security",
            "title": "Encryption control evidence",
            "status": "to_prepare",
            "evidence": "Do not claim application-owned encryption-at-rest or key-management controls until hosting/database evidence is documented and approved.",
            "source": "future security architecture pack",
            "owner": "Security / Engineering",
        },
        {
            "id": "dependency_security",
            "domain": "Supply chain",
            "title": "SBOM / dependency vulnerability scanning",
            "status": "to_prepare",
            "evidence": "Runtime dependencies are declared; formal SBOM, CVE scanning and remediation SLA are not yet production evidence.",
            "source": "future CI security gate",
            "owner": "Engineering / Security",
        },
        {
            "id": "retention_deletion",
            "domain": "Privacy",
            "title": "Retention / deletion policy",
            "status": "to_prepare",
            "evidence": "Data categories are identifiable in the application model; approved retention periods, deletion SLA and DSAR process remain to be defined.",
            "source": "future privacy pack",
            "owner": "Privacy / Legal / Product",
        },
        {
            "id": "central_audit",
            "domain": "Observability",
            "title": "Centralized audit / SIEM evidence",
            "status": "to_prepare",
            "evidence": "Application audit/event records exist for demo workflows; centralized production log retention, alerting and tamper-evidence are not claimed.",
            "source": "future observability pack",
            "owner": "Security / Operations",
        },
    ]

    data_inventory = [
        {
            "category": "Identity & access",
            "examples": "email, display name, role, password hash, session token hash, expiry/revocation",
            "purpose": "authentication and authorized account access",
            "sensitivity": "personal / security",
            "production_retention": "to_define",
        },
        {
            "category": "Participant profile",
            "examples": "intent, interests, visibility/networking choices",
            "purpose": "personalized event/content experience",
            "sensitivity": "personal",
            "production_retention": "to_define",
        },
        {
            "category": "Event participation",
            "examples": "registration, bookings, waitlist, check-in, attendance, replay",
            "purpose": "event operation and participant journey",
            "sensitivity": "personal / behavioral",
            "production_retention": "to_define",
        },
        {
            "category": "Consent-first commercial actions",
            "examples": "product interest, partner lead, follow-up enrollment, appointments",
            "purpose": "explicit participant-requested continuation",
            "sensitivity": "personal / commercial",
            "production_retention": "to_define",
        },
        {
            "category": "Community & communication",
            "examples": "posts, direct messages, meetings, feedback",
            "purpose": "community, networking and service support",
            "sensitivity": "personal / communication content",
            "production_retention": "to_define",
        },
        {
            "category": "Operational evidence",
            "examples": "incidents, venue state, staff assignments, broadcasts, audit events",
            "purpose": "service operation, recovery and evidence",
            "sensitivity": "operational",
            "production_retention": "to_define",
        },
    ]

    privacy_principles = [
        {
            "title": "Explicit continuation",
            "status": "ci_proven",
            "detail": "Partner lead/product-interest actions reject missing consent in the command boundary.",
        },
        {
            "title": "No silent health-data export",
            "status": "gated",
            "detail": "Strategic-partner model explicitly excludes hidden access to sensitive health data; production data-sharing terms still require legal/privacy approval.",
        },
        {
            "title": "Purpose-limited pilot",
            "status": "to_prepare",
            "detail": "Pilot data purposes and legal basis must be fixed in the signed pilot/privacy pack before real participant data is admitted.",
        },
        {
            "title": "Retention & deletion",
            "status": "to_prepare",
            "detail": "Retention periods, user deletion/DSAR operations and archive exceptions require approved policy before production.",
        },
        {
            "title": "Medical data boundary",
            "status": "gated",
            "detail": "The current product is not a medical-record system and must not silently expand into collection of clinical data.",
        },
    ]

    vendor_questions = [
        {
            "id": "hosting",
            "question": "Where is production hosted and which subprocessors handle data?",
            "answer_state": "to_prepare",
            "answer": "Current demo infrastructure is known, but production hosting/subprocessor approval is not yet the contracted authority.",
        },
        {
            "id": "access",
            "question": "How are privileged users authenticated and revoked?",
            "answer_state": "ci_proven",
            "answer": "Database-backed accounts, scrypt password hashes, hashed sessions, TTL and revocation are implemented and CI-proven.",
        },
        {
            "id": "recovery",
            "question": "Can the system be restored after database loss?",
            "answer_state": "ci_proven",
            "answer": "Clean PostgreSQL backup/isolated restore/fingerprint equivalence is CI-proven; contractual RTO/RPO remain to be agreed.",
        },
        {
            "id": "security_incident",
            "question": "What is the breach/incident notification procedure?",
            "answer_state": "to_prepare",
            "answer": "Production incident and notification runbook is not yet approved.",
        },
        {
            "id": "deletion",
            "question": "How quickly can personal data be deleted or exported?",
            "answer_state": "to_prepare",
            "answer": "Production DSAR/export/deletion SLA and implementation are not yet claimed.",
        },
        {
            "id": "medical",
            "question": "Does the platform automate medical decisions or claims?",
            "answer_state": "gated",
            "answer": "No production medical decision/claim authority is active. PROMO-INT-02 and later evidence/claim authorities remain gated.",
        },
        {
            "id": "security_certifications",
            "question": "Is the product ISO 27001 / SOC 2 / otherwise certified?",
            "answer_state": "not_claimed",
            "answer": "No security certification is claimed by this product proof layer.",
        },
    ]

    procurement_gates = [
        {
            "id": "product_demo",
            "title": "Product / executive demo",
            "status": "complete",
            "evidence": "Executive/CVC and Investor Proof surfaces are executable and responsive.",
        },
        {
            "id": "technical_diligence",
            "title": "Technical diligence",
            "status": "ci_proven",
            "evidence": "Architecture, auth, PostgreSQL compatibility, backup/restore and role/consent boundaries are test-backed.",
        },
        {
            "id": "production_persistence",
            "title": "Production persistence admission",
            "status": "complete" if production else "blocking",
            "evidence": "Requires live isolated PostgreSQL source + restore authority and production authenticated smoke.",
        },
        {
            "id": "security_privacy_approval",
            "title": "Security & privacy approval",
            "status": "to_prepare",
            "evidence": "Requires approved data map, retention/deletion, vendor/subprocessor, incident and security-control evidence.",
        },
        {
            "id": "commercial_legal",
            "title": "Commercial / legal pilot terms",
            "status": "to_prepare",
            "evidence": "Requires signed pilot scope, KPI definitions, responsibilities, SLA/support and data-processing terms.",
        },
        {
            "id": "medical_governance",
            "title": "Medical/editorial governance",
            "status": "gated",
            "evidence": "Starts only after Phase 0 COMPLETE through PROMO-INT-02.",
        },
    ]

    security_truth = {
        "current_state": "production_security_review" if production else "pre_production_security_review",
        "can_claim_certification": False,
        "can_claim_approved_rto_rpo": False,
        "can_claim_approved_dpa_sla": False,
        "can_claim_central_siem": False,
        "can_claim_live_postgres": production,
        "can_claim_auth_restore_controls_ci_proven": True,
    }

    return {
        "runtime": proof["runtime"],
        "controls": controls,
        "data_inventory": data_inventory,
        "privacy_principles": privacy_principles,
        "vendor_questions": vendor_questions,
        "procurement_gates": procurement_gates,
        "security_truth": security_truth,
        "disclaimers": [
            "This is an evidence-backed readiness pack, not a security certification.",
            "TO PREPARE means the control/policy/evidence must exist before production approval.",
            "CI-PROVEN describes repository/test evidence and does not equal contractual or regulator approval.",
        ],
    }
