"""Candidate contract-to-cash evidence custody (NO financial posting authority).

This module is *not* registered as a public HTTP command. It stores immutable
candidate documents only in an isolated, explicitly operated database. It
cannot sign contracts, collect cash, recognize revenue or release capital.

All money is integer minor units of ONE contract currency; taxes are separate.
Cumulative checks apply to latest revisions, not superseded event versions.
"""
import hashlib
import json
import re
import time

from app import db, pilot_revenue_ladder

VERSION = "promomed-contract-cash-candidate-ledger-v1"
ID = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9:_.-]{0,127}\Z")
ORG_ID = pilot_revenue_ladder.IDENTIFIER
CURRENCY = re.compile(r"\A[A-Z]{3}\Z")
SHA = re.compile(r"\A[a-f0-9]{64}\Z")
PERIOD = re.compile(r"\A\d{4}-(0[1-9]|1[0-2])\Z")
ALLOWED_TYPES = (
    "obligation", "delivery", "invoice", "credit_note", "settlement",
    "allocation", "refund", "direct_cost", "recognition",
    "finance_review", "renewal",
)
PARENT_TYPE = {
    "delivery": "obligation",
    "invoice": "delivery",
    "credit_note": "invoice",
    "allocation": "invoice",
    "refund": "settlement",
    "direct_cost": "delivery",
    "recognition": "invoice",
    "finance_review": "recognition",
}
RELATED_TYPE = {"allocation": "settlement", "renewal": "recognition"}
ZERO_TYPES = {"finance_review", "renewal"}
NONZERO_TYPES = set(ALLOWED_TYPES) - ZERO_TYPES
MAX_MINOR = 9_000_000_000_000_000


def _canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(data):
    return hashlib.sha256(_canonical(data).encode("utf-8")).hexdigest()


def _txt(value, *, maxlen=128, field="reference"):
    s = str(value or "").strip()
    if not s or len(s) > maxlen or not ID.fullmatch(s):
        raise ValueError(field + "_invalid")
    return s


def _hash(value):
    s = str(value or "").strip()
    if not SHA.fullmatch(s):
        raise ValueError("source_sha256_invalid")
    return s


def _minor(value, name, *, allow_zero=False):
    if type(value) is not int or not (0 if allow_zero else 1) <= value <= MAX_MINOR:
        raise ValueError(name + "_invalid")
    return value


def _currency(value):
    s = str(value or "").strip()
    if not CURRENCY.fullmatch(s):
        raise ValueError("currency_invalid")
    return s


def _org(c, organization_id):
    if not ORG_ID.fullmatch(str(organization_id or "")):
        raise ValueError("organization_id_invalid")
    row = c.execute(
        "SELECT id,status,demo_only FROM institutional_organizations WHERE id=?",
        (organization_id,)
    ).fetchone()
    if row is None or row["status"] != "active":
        raise ValueError("organization_not_found")
    return dict(row)


def _member(c, organization_id, actor):
    actor = str(actor or "").lower().strip()
    pilot_revenue_ladder._require_member(c, organization_id, actor)
    return actor


def _candidate_authority(c, org):
    # No candidate may ever be confused with an accepted commercial item.
    if db.backend_name() != "sqlite" and db.backend_name() != "postgres":
        raise ValueError("unknown_storage_backend")
    if not bool(org["demo_only"]) and (
        db.backend_name() != "postgres" or db.demo_seed_enabled()
    ):
        raise ValueError("non_demo_candidate_requires_admitted_postgres")
    # Even with PostgreSQL no finance recognition / commercial acceptance is given.


def _contract(c, organization_id, contract_id):
    row = c.execute(
        "SELECT * FROM commercial_contract_versions WHERE organization_id=? AND id=?",
        (organization_id, contract_id)
    ).fetchone()
    if row is None:
        raise ValueError("contract_not_found")
    return dict(row)


def _event(c, organization_id, event_id):
    row = c.execute(
        "SELECT * FROM commercial_evidence_events WHERE organization_id=? AND id=?",
        (organization_id, event_id)
    ).fetchone()
    if row is None:
        raise ValueError("event_not_found")
    return dict(row)


def _events(c, organization_id, contract_id):
    rows = c.execute(
        """SELECT * FROM commercial_evidence_events
           WHERE organization_id=? AND contract_id=?
           ORDER BY recorded_at,id""",
        (organization_id, contract_id)
    )
    # Only newest version of each event/type/external source is counted.
    grouped = {}
    for row in rows:
        item = dict(row)
        key = (item["event_type"], item["external_ref"])
        if key not in grouped or grouped[key]["version"] < item["version"]:
            grouped[key] = item
    return list(grouped.values())


def _audit(c, organization_id, actor, kind, entity_id, payload_sha256):
    last = c.execute(
        """SELECT entry_no,entry_sha256 FROM commercial_evidence_audit
           WHERE organization_id=? ORDER BY entry_no DESC LIMIT 1""",
        (organization_id,)
    ).fetchone()
    seq = int(last["entry_no"]) + 1 if last else 1
    previous = last["entry_sha256"] if last else None
    recorded_at = int(time.time())
    raw = {
        "organization": organization_id, "entryNo": seq,
        "previous": previous, "entityKind": kind,
        "entityId": entity_id, "payloadSha256": payload_sha256,
        "recordedBy": actor, "recordedAt": recorded_at
    }
    digest = _digest(raw)
    record_id = "ca:" + digest[:28]
    c.execute(
        """INSERT INTO commercial_evidence_audit
        (id,organization_id,entry_no,entity_kind,entity_id,entry_sha256,
         previous_sha256,recorded_by,recorded_at)
        VALUES(?,?,?,?,?,?,?,?,?)""",
        (record_id, organization_id, seq, kind, entity_id, digest,
         previous, actor, recorded_at),
    )
    return digest


def _existing_request(c, organization_id, key, payload_hash, *, table):
    row = c.execute(
        "SELECT id,payload_sha256 FROM " + table +
        " WHERE organization_id=? AND idempotency_key=?",
        (organization_id, key),
    ).fetchone()
    if row is None:
        return None
    if row["payload_sha256"] != payload_hash:
        raise ValueError("idempotency_conflict")
    return row["id"]


def _begin(c):
    # The candidate CLI serializes writes; no remote API accepts these commands.
    # Lock the local database before reading the audit tail / event limits.
    if db.backend_name() == "sqlite":
        if not c.in_transaction:
            c.execute("BEGIN IMMEDIATE")
    else:
        # Serialize per org at transaction level before any upsert or totals.
        # The advisory lock is additionally keyed by org in the write functions.
        pass


def _org_lock(c, organization_id):
    if db.backend_name() == "postgres":
        c.execute("SELECT pg_advisory_xact_lock(hashtext(?))", (organization_id,))


def record_contract(
    c, *, organization_id, actor, external_ref, version, currency_code,
    net_amount_minor, source_ref, source_sha256, idempotency_key,
    previous_contract_id=None,
):
    _begin(c)
    actor = _member(c, organization_id, actor)
    org = _org(c, organization_id)
    _candidate_authority(c, org)
    _org_lock(c, organization_id)
    external_ref = _txt(external_ref, field="external_ref")
    source_ref = _txt(source_ref, field="source_ref")
    key = _txt(idempotency_key, field="idempotency_key")
    currency_code = _currency(currency_code)
    evidence_sha256 = _hash(source_sha256)
    net_amount_minor = _minor(net_amount_minor, "net_amount_minor")
    if type(version) is not int or not 1 <= version <= 10000:
        raise ValueError("contract_version_invalid")

    previous = None
    if previous_contract_id is not None:
        previous = _contract(c, organization_id, _txt(previous_contract_id))
        if previous["currency_code"] != currency_code:
            raise ValueError("contract_currency_mismatch")
        if bool(previous["demo_only"]) != bool(org["demo_only"]):
            raise ValueError("demo_boundary_mismatch")
    if version != 1:
        if not previous or previous["external_ref"] != external_ref or previous["version"] != version - 1:
            raise ValueError("contract_revision_parent_required")
    elif previous and previous["external_ref"] == external_ref:
        raise ValueError("contract_new_version_required")

    payload = {
        "organizationId": organization_id, "externalRef": external_ref,
        "version": version, "currency": currency_code,
        "netAmountMinor": net_amount_minor, "sourceRef": source_ref,
        "sourceSha256": evidence_sha256,
        "previousContractId": previous["id"] if previous else None,
        "demoOnly": bool(org["demo_only"]),
    }
    payload_hash = _digest(payload)
    existing = _existing_request(
        c, organization_id, key, payload_hash, table="commercial_contract_versions"
    )
    if existing:
        return {"id": existing, "created": False, "state": "candidate"}
    cid = "cc:" + _digest([organization_id, external_ref, version])[:26]
    c.execute(
        """INSERT INTO commercial_contract_versions
           (id,organization_id,external_ref,version,previous_contract_id,
            currency_code,net_amount_minor,source_ref,evidence_sha256,state,
            recorded_by,recorded_at,demo_only,idempotency_key,payload_sha256)
           VALUES(?,?,?,?,?,?,?,?,?,'candidate',?,?,?,?,?)""",
        (cid, organization_id, external_ref, version,
         previous["id"] if previous else None, currency_code, net_amount_minor,
         source_ref, evidence_sha256, actor, int(time.time()),
         int(bool(org["demo_only"])), key, payload_hash),
    )
    audit_sha = _audit(c, organization_id, actor, "contract", cid, payload_hash)
    return {"id": cid, "created": True, "state": "candidate", "auditSha256": audit_sha}


def _current(event, current):
    return all(
        item["id"] != event["id"]
        for item in current
        if item["event_type"] == event["event_type"]
        and item["external_ref"] == event["external_ref"]
        and item["version"] > event["version"]
    )


def _require_parent(typ, parent, related, contract):
    if typ in PARENT_TYPE:
        if parent is None or parent["event_type"] != PARENT_TYPE[typ]:
            raise ValueError("event_parent_type_invalid")
        if typ != "renewal" and parent["contract_id"] != contract["id"]:
            raise ValueError("event_parent_contract_mismatch")
    elif typ in ("obligation", "settlement"):
        if parent is not None:
            raise ValueError("event_parent_not_applicable")
    elif typ == "renewal":
        if parent is not None:
            raise ValueError("event_parent_not_applicable")
    if typ in RELATED_TYPE:
        if related is None or related["event_type"] != RELATED_TYPE[typ]:
            raise ValueError("event_related_type_invalid")
        if typ == "allocation" and related["contract_id"] != contract["id"]:
            raise ValueError("event_related_contract_mismatch")
        if typ == "renewal":
            if related["contract_id"] != contract["previous_contract_id"]:
                raise ValueError("renewal_previous_contract_required")
            if contract["version"] != 1 or contract["previous_contract_id"] is None:
                raise ValueError("renewal_distinct_contract_required")
    elif related is not None:
        raise ValueError("event_related_not_applicable")


def _latest(c, organization_id, contract_id):
    return _events(c, organization_id, contract_id)


def _sum(rows, typ, key, field="amount_minor"):
    return sum(r[field] for r in rows if r["event_type"] == typ and r[key[0]] == key[1])


def _constraints(c, contract, typ, amount, tax, parent, related, replace):
    org = contract["organization_id"]
    rows = _latest(c, org, contract["id"])
    if replace is not None:
        rows = [r for r in rows if r["id"] != replace["id"]]
    if parent is not None and not _current(parent, _latest(c, org, parent["contract_id"])):
        raise ValueError("superseded_parent_invalid")
    if related is not None and not _current(related, _latest(c, org, related["contract_id"])):
        raise ValueError("superseded_related_invalid")
    if typ == "obligation":
        total = sum(r["amount_minor"] for r in rows if r["event_type"] == "obligation")
        if total + amount > contract["net_amount_minor"]:
            raise ValueError("obligation_exceeds_contract")
    if typ == "delivery":
        current = _sum(rows, "delivery", ("parent_event_id", parent["id"]))
        if current + amount > parent["amount_minor"]:
            raise ValueError("delivery_exceeds_obligation")
    if typ == "invoice":
        current = _sum(rows, "invoice", ("parent_event_id", parent["id"]))
        if current + amount > parent["amount_minor"]:
            raise ValueError("invoice_exceeds_delivery")
    if typ == "credit_note":
        existing = [r for r in rows if r["event_type"] == "credit_note"
                    and r["parent_event_id"] == parent["id"]]
        net = sum(r["amount_minor"] for r in existing)
        vat = sum(r["tax_minor"] for r in existing)
        if net + amount > parent["amount_minor"] or vat + tax > parent["tax_minor"]:
            raise ValueError("credit_exceeds_invoice")
        if _sum(rows, "recognition", ("parent_event_id", parent["id"])):
            raise ValueError("credit_requires_recognition_reversal")
        allocated = _sum(rows, "allocation", ("parent_event_id", parent["id"]))
        if allocated > parent["amount_minor"] + parent["tax_minor"] - net - vat - amount - tax:
            raise ValueError("credit_requires_cash_reallocation")
    if typ == "allocation":
        invoice_gross = parent["amount_minor"] + parent["tax_minor"]
        credited_gross = sum(
            r["amount_minor"] + r["tax_minor"] for r in rows
            if r["event_type"] == "credit_note" and r["parent_event_id"] == parent["id"]
        )
        already = _sum(rows, "allocation", ("parent_event_id", parent["id"]))
        if already + amount > invoice_gross - credited_gross:
            raise ValueError("allocation_exceeds_receivable")
        settled = related["amount_minor"]
        allocated = _sum(rows, "allocation", ("related_event_id", related["id"]))
        refunded = _sum(rows, "refund", ("parent_event_id", related["id"]))
        if allocated + refunded + amount > settled:
            raise ValueError("allocation_exceeds_settlement")
    if typ == "refund":
        refunded = _sum(rows, "refund", ("parent_event_id", parent["id"]))
        allocated = _sum(rows, "allocation", ("related_event_id", parent["id"]))
        if refunded + allocated + amount > parent["amount_minor"]:
            raise ValueError("refund_exceeds_unallocated_cash")
    if typ == "recognition":
        used = _sum(rows, "recognition", ("parent_event_id", parent["id"]))
        credits_net = _sum(rows, "credit_note", ("parent_event_id", parent["id"]))
        if used + amount > parent["amount_minor"] - credits_net:
            raise ValueError("recognition_exceeds_invoice_net")
    # If an invoice or settlement is revised, downstream docs may need a
    # correction event. Conservative v1 forbids revision once referenced.
    if replace is not None:
        dependents = c.execute(
            """SELECT COUNT(*) n FROM commercial_evidence_events
               WHERE organization_id=? AND (parent_event_id=? OR related_event_id=?)
            """, (org, replace["id"], replace["id"])
        ).fetchone()
        if int(dependents["n"]) > 0:
            raise ValueError("revision_has_downstream_evidence")


def record_event(
    c, *, organization_id, actor, contract_id, event_type, external_ref,
    amount_minor, source_ref, source_sha256, idempotency_key, version=1,
    tax_minor=0, accounting_period=None, parent_event_id=None,
    related_event_id=None, replaces_event_id=None, decision=None,
):
    _begin(c)
    actor = _member(c, organization_id, actor)
    org = _org(c, organization_id)
    _candidate_authority(c, org)
    _org_lock(c, organization_id)
    contract = _contract(c, organization_id, _txt(contract_id, field="contract_id"))
    if bool(contract["demo_only"]) != bool(org["demo_only"]):
        raise ValueError("contract_demo_boundary_mismatch")
    typ = str(event_type or "").strip()
    if typ not in ALLOWED_TYPES:
        raise ValueError("event_type_invalid")
    external_ref = _txt(external_ref, field="external_ref")
    source_ref = _txt(source_ref, field="source_ref")
    key = _txt(idempotency_key, field="idempotency_key")
    evidence_sha256 = _hash(source_sha256)
    amount = _minor(amount_minor, "amount_minor", allow_zero=typ in ZERO_TYPES)
    tax = _minor(tax_minor, "tax_minor", allow_zero=True)
    if typ in ZERO_TYPES and amount != 0:
        raise ValueError("zero_amount_event_required")
    if typ not in ("invoice", "credit_note") and tax != 0:
        raise ValueError("tax_not_applicable")
    if type(version) is not int or not 1 <= version <= 10000:
        raise ValueError("event_version_invalid")
    period = str(accounting_period or "").strip() or None
    if period is not None and not PERIOD.fullmatch(period):
        raise ValueError("accounting_period_invalid")
    if typ == "recognition" and period is None:
        raise ValueError("recognition_period_required")
    if typ == "finance_review":
        if decision not in ("hold", "request_changes", "rejected"):
            raise ValueError("finance_review_not_authority")
    elif decision is not None:
        raise ValueError("decision_not_applicable")

    parent = _event(c, organization_id, _txt(parent_event_id)) if parent_event_id is not None else None
    related = _event(c, organization_id, _txt(related_event_id)) if related_event_id is not None else None
    replace = _event(c, organization_id, _txt(replaces_event_id)) if replaces_event_id is not None else None
    if version > 1:
        if replace is None or replace["version"] != version - 1 or (
            replace["external_ref"], replace["event_type"], replace["contract_id"]
        ) != (external_ref, typ, contract_id):
            raise ValueError("revision_parent_required")
    elif replace is not None:
        raise ValueError("initial_event_cannot_replace")
    _require_parent(typ, parent, related, contract)

    payload = {
        "organizationId": organization_id, "contractId": contract_id,
        "eventType": typ, "externalRef": external_ref, "version": version,
        "amountMinor": amount, "taxMinor": tax, "currency": contract["currency_code"],
        "accountingPeriod": period, "parentEventId": parent["id"] if parent else None,
        "relatedEventId": related["id"] if related else None,
        "replacesEventId": replace["id"] if replace else None,
        "sourceRef": source_ref, "sourceSha256": evidence_sha256,
        "decision": decision, "demoOnly": bool(org["demo_only"]),
    }
    digest = _digest(payload)
    existing = _existing_request(
        c, organization_id, key, digest, table="commercial_evidence_events"
    )
    if existing:
        return {"id": existing, "created": False, "state": "candidate"}
    _constraints(c, contract, typ, amount, tax, parent, related, replace)
    eid = "ce:" + _digest([organization_id, contract_id, typ, external_ref, version])[:26]
    c.execute(
        """INSERT INTO commercial_evidence_events(
         id,organization_id,contract_id,event_type,external_ref,version,
         replaces_event_id,parent_event_id,related_event_id,amount_minor,tax_minor,
         currency_code,accounting_period,decision,source_ref,evidence_sha256,
         state,recorded_by,recorded_at,demo_only,idempotency_key,payload_sha256
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'candidate',?,?,?,?,?)""",
        (eid, organization_id, contract_id, typ, external_ref, version,
         replace["id"] if replace else None, parent["id"] if parent else None,
         related["id"] if related else None, amount, tax, contract["currency_code"],
         period, decision, source_ref, evidence_sha256, actor,
         int(time.time()), int(bool(org["demo_only"])), key, digest),
    )
    chain_hash = _audit(c, organization_id, actor, "event", eid, digest)
    return {"id": eid, "created": True, "state": "candidate", "auditSha256": chain_hash}


def snapshot(c, organization_id, *, actor):
    _member(c, organization_id, actor)
    org = _org(c, organization_id)
    rows = list(c.execute(
        "SELECT * FROM commercial_contract_versions WHERE organization_id=? ORDER BY external_ref,version",
        (organization_id,),
    ))
    contracts = []
    for row in rows:
        doc = dict(row)
        events = _events(c, organization_id, doc["id"])
        docs = {typ: 0 for typ in ALLOWED_TYPES}
        for event in events:
            docs[event["event_type"]] += 1
        contracts.append({
            "id": doc["id"], "externalRef": doc["external_ref"],
            "version": doc["version"], "currency": doc["currency_code"],
            "state": "candidate", "demoOnly": bool(doc["demo_only"]),
            "documentCounts": docs,
            "totalCandidateDocuments": sum(docs.values()),
        })
    tail = c.execute(
        """SELECT entry_no,entry_sha256 FROM commercial_evidence_audit
        WHERE organization_id=? ORDER BY entry_no DESC LIMIT 1""",
        (organization_id,)
    ).fetchone()
    return {
        "version": VERSION, "organizationId": org["id"],
        "contractCandidates": contracts, "auditTailSha256": tail["entry_sha256"] if tail else None,
        "auditLength": int(tail["entry_no"]) if tail else 0,
        "financialAuthority": "NONE", "capitalAuthority": "NONE",
        "contracted": None, "invoiced": None, "cashCollected": None,
        "recognizedRevenue": None, "directCosts": None, "renewals": None,
        "amountSemantics": "NOT_VERIFIED_NOT_ZERO",
    }


def verify_chain(c, organization_id, *, actor):
    _member(c, organization_id, actor)
    _org(c, organization_id)
    rows = list(c.execute(
        "SELECT * FROM commercial_evidence_audit WHERE organization_id=? ORDER BY entry_no",
        (organization_id,)
    ))
    previous = None
    for idx, row in enumerate(rows, 1):
        if row["entry_no"] != idx or row["previous_sha256"] != previous:
            return {"valid": False, "checked": idx-1}
        table = ("commercial_contract_versions" if row["entity_kind"] == "contract"
                 else "commercial_evidence_events")
        document = c.execute(
            "SELECT payload_sha256 FROM " + table + " WHERE organization_id=? AND id=?",
            (organization_id, row["entity_id"]),
        ).fetchone()
        if not document:
            return {"valid": False, "checked": idx-1}
        raw = {
            "organization": organization_id, "entryNo": idx, "previous": previous,
            "entityKind": row["entity_kind"], "entityId": row["entity_id"],
            "payloadSha256": document["payload_sha256"],
            "recordedBy": row["recorded_by"], "recordedAt": row["recorded_at"],
        }
        if _digest(raw) != row["entry_sha256"]:
            return {"valid": False, "checked": idx-1}
        previous = row["entry_sha256"]
    return {"valid": True, "checked": len(rows), "headSha256": previous}
