import hashlib
import json

from app import db, executive, investment_proof


MILESTONE_TEMPLATE = [
    {
        "id": "m0",
        "share_pct": 10,
        "title": "Scope + baseline lock",
        "responsible": "Business Owner + Finance + Product",
        "deliverable": "Signed scope, KPI dictionary, baseline pack, RACI and evidence-source register.",
        "kpi": "All contractual KPIs have formula, owner, source and pre-pilot target/treatment.",
        "evidence": "Scope pack + KPI schedule + Finance baseline acceptance.",
        "payment_rule": "Eligible only after scope/baseline acceptance.",
        "stop_go": "STOP if scope, ownership or finance baseline cannot be agreed.",
    },
    {
        "id": "m1",
        "share_pct": 20,
        "title": "Production core admission",
        "responsible": "Product / Engineering + IT / Security",
        "deliverable": "Durable production core, identity, exact-SHA release, restore and authenticated smoke.",
        "kpi": "production_ready == true",
        "evidence": "/ready + exact-SHA proof + backup/restore + authenticated smoke.",
        "payment_rule": "Eligible only after Phase 0 acceptance.",
        "stop_go": "STOP if production authority remains non-durable or recovery proof fails.",
    },
    {
        "id": "m2",
        "share_pct": 20,
        "title": "Pilot launch readiness",
        "responsible": "Product + Operations + Commercial + Legal/Privacy",
        "deliverable": "Configured flagship event, partner inventory, operating runbook and approved participant journeys.",
        "kpi": "Critical journeys executable; contracted partner inventory and recovery paths ready.",
        "evidence": "Browser evidence + runbook + partner scope + launch readiness checklist.",
        "payment_rule": "Eligible only after launch-readiness acceptance.",
        "stop_go": "ITERATE if non-critical gaps remain; STOP if critical participant/operations path is blocked.",
    },
    {
        "id": "m3",
        "share_pct": 25,
        "title": "Pilot delivery acceptance",
        "responsible": "Operations + Product + Commercial",
        "deliverable": "Executed pilot with attendance, operations, partner delivery, consent and post-event evidence.",
        "kpi": "Contractual delivery KPIs measured using pre-agreed definitions.",
        "evidence": "Event close report + audit trail + partner deliverable acceptance + KPI actuals.",
        "payment_rule": "Eligible only for accepted delivered scope; rejected items remain unpaid/rework.",
        "stop_go": "ITERATE or STOP when critical delivery/evidence obligations are not accepted.",
    },
    {
        "id": "m4",
        "share_pct": 15,
        "title": "Finance value acceptance",
        "responsible": "Finance + Analytics + Business Owner",
        "deliverable": "Reconciled actual cost and value ledger with double-count guardrail.",
        "kpi": "Finance-accepted annualized net value and actual delivery cost.",
        "evidence": "Baseline vs actual reconciliation + accepted_value_rub by value bucket.",
        "payment_rule": "Eligible only after Finance accepts the close pack.",
        "stop_go": "STOP/ITERATE if value cannot be reconciled or economics fail the agreed threshold.",
    },
    {
        "id": "m5",
        "share_pct": 10,
        "title": "Board decision certificate",
        "responsible": "Executive Sponsor / Investment Committee",
        "deliverable": "GO / ITERATE / STOP decision and next-capital instruction.",
        "kpi": "All required acceptance records resolved; unresolved risks explicitly documented.",
        "evidence": "Acceptance matrix + Evidence Room index + Finance acceptance + Board decision record.",
        "payment_rule": "Final milestone is eligible only after board-level acceptance of the contractual close pack.",
        "stop_go": "GO opens the next approved programme; ITERATE creates a remediation gate; STOP closes expansion.",
    },
]


def _tranche_map(proof):
    return {x["id"]: x for x in proof["tranches"]}


def _kpi_map(proof):
    return {x["id"]: x for x in proof["contractual_kpis"]}


def _amount(amount, pct):
    return int(round(float(amount) * float(pct) / 100.0))


def _evidence_room(c, proof, tranche):
    readiness = db.readiness()
    demo = proof["demo_evidence"]
    acceptance = proof["acceptance_state"].get(tranche["id"], {})
    return [
        {
            "id": "release",
            "title": "Exact release + production admission",
            "owner": "Product / Engineering + IT / Security",
            "status": "accepted_runtime" if readiness.get("production_ready") else "partial_ci_only",
            "required_for": ["m1"],
            "evidence": "Exact-SHA Render proof, /ready, production identity, backup/restore.",
        },
        {
            "id": "journeys",
            "title": "Golden-path product / operations evidence",
            "owner": "Product + Operations",
            "status": "demo_proven" if demo.get("golden_demo_complete") else "awaiting_demo_run",
            "required_for": ["m2", "m3"],
            "evidence": "Waitlist, promotion, schedule change, live recovery, check-in, partner action and replay audit trail.",
        },
        {
            "id": "partner",
            "title": "Partner delivery acceptance",
            "owner": "Commercial + Business Owner",
            "status": "demo_proven" if demo.get("partner_demo_complete") else "awaiting_delivery",
            "required_for": ["m3"],
            "evidence": "Contracted deliverable -> delivery evidence -> acceptance record.",
        },
        {
            "id": "finance",
            "title": "Finance value reconciliation",
            "owner": "Finance",
            "status": "awaiting_paid_pilot_actuals",
            "required_for": ["m0", "m4"],
            "evidence": "Locked baseline, actual cost, value buckets, double-count check, accepted_value_rub.",
        },
        {
            "id": "acceptance",
            "title": "Acceptance matrix",
            "owner": "Cross-functional owners",
            "status": "demo_complete" if acceptance.get("demo_complete") else "incomplete",
            "required_for": ["m5"],
            "evidence": f'{acceptance.get("accepted_demo_count",0)} / {acceptance.get("required_count",0)} demo acceptance records.',
        },
        {
            "id": "governance",
            "title": "Medical / legal governance",
            "owner": "Medical + Legal + Editorial",
            "status": "gated" if tranche["id"] != "t50" else "not_required_for_t50_core",
            "required_for": ["m2", "m5"] if tranche["id"] != "t50" else [],
            "evidence": "PROMO-INT-02+ versioned review / disclosure / approval evidence.",
        },
    ]


def snapshot(c):
    proof = investment_proof.snapshot(c)
    exe = executive.snapshot(c)
    tranches = _tranche_map(proof)
    kpis = _kpi_map(proof)
    packages = []

    for tranche_id in ("t50", "t75", "t100"):
        tranche = tranches[tranche_id]
        milestones = []
        for template in MILESTONE_TEMPLATE:
            row = dict(template)
            row["amount_rub"] = _amount(tranche["amount_rub"], template["share_pct"])
            row["commercial_state"] = "illustrative_template_not_quote"
            milestones.append(row)

        scope = {
            "objective": exe["pilot_contract"]["objective"] if tranche_id == "t50" else tranche["title"],
            "in_scope": tranche["what_is_built"],
            "out_of_scope": exe["pilot_contract"]["out_of_scope"],
            "client_inputs": exe["pilot_contract"]["client_inputs"],
        }
        contract_kpis = [kpis[k] for k in tranche["contract_kpis"] if k in kpis]
        acceptance = proof["acceptance_state"].get(tranche_id, {})
        evidence_room = _evidence_room(c, proof, tranche)

        blockers = []
        if tranche["state"] == "blocked_by_phase0":
            blockers.append("Phase 0 production admission")
        if tranche_id == "t75":
            blockers.extend(["50m contractual acceptance", "paid pilot actuals", "medical governance"])
        if tranche_id == "t100":
            blockers.extend(["75m contractual acceptance", "repeatable economics", "scale security/governance"])

        decision = "GO_TO_CONTRACT" if tranche["state"] == "ready_to_contract" else "HOLD"
        if tranche_id != "t50":
            decision = "HOLD"

        certificate_payload = {
            "tranche_id": tranche_id,
            "amount_rub": tranche["amount_rub"],
            "decision": decision,
            "state": tranche["state"],
            "acceptance_demo_complete": bool(acceptance.get("demo_complete")),
            "blockers": blockers,
            "milestone_template": [(x["id"], x["share_pct"]) for x in milestones],
        }
        digest = hashlib.sha256(json.dumps(certificate_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

        packages.append({
            "id": tranche_id,
            "title": tranche["title"],
            "amount_rub": tranche["amount_rub"],
            "contract_state": tranche["state"],
            "scope_of_work": scope,
            "deliverables": tranche["what_is_built"],
            "responsible_parties": proof["acceptance_roles"],
            "contractual_kpis": contract_kpis,
            "acceptance_matrix": acceptance,
            "payment_milestones": milestones,
            "evidence_room": evidence_room,
            "stop_go_rule": tranche["release_rule"],
            "board_decision_certificate": {
                "certificate_id": f"board-preview-{tranche_id}-{digest[:12]}",
                "certificate_hash": digest,
                "decision": decision,
                "blockers": blockers,
                "legal_effect": "NONE",
                "capital_release_effect": "NONE",
                "note": "Decision certificate preview. Binding decision requires approved governance, authorized signatories and contractual acceptance outside this demo.",
            },
        })

    return {
        "version": "contract-builder-v1",
        "selected_default": "t50",
        "packages": packages,
        "payment_template": {
            "shares_total_pct": sum(x["share_pct"] for x in MILESTONE_TEMPLATE),
            "commercial_state": "illustrative_template_not_quote",
            "editable_before_contract": True,
            "note": "Milestone percentages demonstrate the control model only. Final commercial terms require negotiated contract approval.",
        },
        "truth_boundary": {
            "is_legal_contract": False,
            "is_commercial_quote": False,
            "is_e_signature": False,
            "auto_releases_money": False,
            "binding_use_requires": [
                "Approved contract template",
                "Authorized signatory model",
                "Electronic-signature / document-workflow authority if required",
                "Finance and procurement approval",
            ],
        },
    }
