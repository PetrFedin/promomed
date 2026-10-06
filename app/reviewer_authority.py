import hashlib
import json
import time


DEFAULT_SCOPE="external_evidence.general"
VALID_CONFLICTS=("none","potential","material")
VALID_DECISIONS=("accept","reject","request_changes")


def _canonical(payload):
    return json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":"))


def _profile(c,email):
    return c.execute(
        "SELECT rp.*,a.role account_role,a.status account_status FROM reviewer_profiles rp "
        "JOIN accounts a ON a.email=rp.account_email WHERE rp.account_email=?",
        (str(email or "").lower(),),
    ).fetchone()


def _scope(c,reviewer_id,scope_key):
    return c.execute(
        "SELECT * FROM reviewer_scopes WHERE reviewer_id=? AND scope_key=? AND status='active'",
        (reviewer_id,scope_key),
    ).fetchone()


def validate_reviewer(c,email,scope_key=DEFAULT_SCOPE,production=False,now=None):
    now=int(time.time()) if now is None else int(now)
    p=_profile(c,email)
    if not p or p["account_role"]!="reviewer" or p["account_status"]!="active":
        raise ValueError("reviewer_identity_not_authorized")
    if p["status"]!="active":
        raise ValueError("reviewer_profile_inactive")
    if production:
        if p["credential_state"]!="verified":
            raise ValueError("reviewer_credential_not_verified")
        if not int(p["independent_attested"] or 0):
            raise ValueError("reviewer_independence_not_attested")
    elif p["credential_state"] not in ("verified","demo_attested"):
        raise ValueError("reviewer_credential_not_usable")
    if p["valid_until"] is not None and int(p["valid_until"])<=now:
        raise ValueError("reviewer_credential_expired")
    s=_scope(c,p["id"],scope_key)
    if not s:
        raise ValueError("reviewer_scope_not_authorized")
    if s["valid_until"] is not None and int(s["valid_until"])<=now:
        raise ValueError("reviewer_scope_expired")
    return p


def _append_event(c,event_type,actor,payload,candidate_id=None,assignment_id=None,demo_only=0):
    previous=c.execute(
        "SELECT event_hash FROM review_authority_events ORDER BY created_at DESC,id DESC LIMIT 1"
    ).fetchone()
    prev_hash=previous["event_hash"] if previous else ""
    created_at=time.time_ns()
    body={
        "event_type":event_type,
        "candidate_id":candidate_id or "",
        "assignment_id":assignment_id or "",
        "actor":actor,
        "payload":payload,
        "created_at":created_at,
        "prev_hash":prev_hash,
    }
    payload_json=_canonical(payload)
    event_hash=hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
    event_id="review-event:"+event_hash[:24]
    c.execute(
        "INSERT INTO review_authority_events(id,event_type,candidate_id,assignment_id,actor,payload_json,prev_hash,event_hash,created_at,demo_only) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        (event_id,event_type,candidate_id,assignment_id,actor,payload_json,prev_hash,event_hash,created_at,int(bool(demo_only))),
    )
    return event_hash


def verify_event_chain(c):
    prev=""
    for row in c.execute(
        "SELECT id,event_type,candidate_id,assignment_id,actor,payload_json,prev_hash,event_hash,created_at "
        "FROM review_authority_events ORDER BY created_at,id"
    ):
        try:
            payload=json.loads(row["payload_json"])
        except Exception:
            return False
        body={
            "event_type":row["event_type"],
            "candidate_id":row["candidate_id"] or "",
            "assignment_id":row["assignment_id"] or "",
            "actor":row["actor"],
            "payload":payload,
            "created_at":int(row["created_at"]),
            "prev_hash":row["prev_hash"] or "",
        }
        expected=hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
        if row["prev_hash"]!=prev or row["event_hash"]!=expected:
            return False
        prev=row["event_hash"]
    return True


def seed_demo(c):
    now=int(time.time())
    reviewer_id="REV-DEMO-MEDICAL"
    c.execute(
        "INSERT INTO reviewer_profiles(id,account_email,display_name,reviewer_kind,credential_state,credential_ref,credential_issuer,independent_attested,status,created_at,updated_at,demo_only) "
        "VALUES(?,?,?,'medical_scientific','demo_attested','DEMO-NOT-A-REAL-CREDENTIAL','Demo authority',0,'active',?,?,1) "
        "ON CONFLICT(account_email) DO NOTHING",
        (reviewer_id,"reviewer@demo.ru","Medical Reviewer · DEMO",now,now),
    )
    c.execute(
        "INSERT INTO reviewer_scopes(id,reviewer_id,scope_key,status,verified_by,verified_at,demo_only) "
        "VALUES(?,?,?,'active','system@demo',?,1) ON CONFLICT(reviewer_id,scope_key) DO NOTHING",
        ("scope:"+reviewer_id+":"+DEFAULT_SCOPE,reviewer_id,DEFAULT_SCOPE,now),
    )


def register_verified_reviewer(c,email,display_name,credential_ref,credential_issuer,scope_key,verified_by,valid_until=None,independent_attested=False):
    email=str(email or "").lower()
    account=c.execute("SELECT email,role,status FROM accounts WHERE email=?",(email,)).fetchone()
    if not account or account["role"]!="reviewer" or account["status"]!="active":
        raise ValueError("reviewer_account_required")
    verifier=c.execute("SELECT email,role,status FROM accounts WHERE email=?",(str(verified_by or "").lower(),)).fetchone()
    if not verifier or verifier["role"]!="governance" or verifier["status"]!="active":
        raise ValueError("governance_verifier_required")
    if not credential_ref or not credential_issuer:
        raise ValueError("credential_reference_required")
    now=int(time.time())
    reviewer_id="REV-"+hashlib.sha256(email.encode("utf-8")).hexdigest()[:16].upper()
    c.execute(
        "INSERT INTO reviewer_profiles(id,account_email,display_name,reviewer_kind,credential_state,credential_ref,credential_issuer,credential_verified_by,credential_verified_at,valid_until,independent_attested,status,created_at,updated_at,demo_only) "
        "VALUES(?,?,?,'medical_scientific','verified',?,?,?,?,? ,?,'active',?,?,0) "
        "ON CONFLICT(account_email) DO UPDATE SET display_name=excluded.display_name,credential_state='verified',credential_ref=excluded.credential_ref,credential_issuer=excluded.credential_issuer,credential_verified_by=excluded.credential_verified_by,credential_verified_at=excluded.credential_verified_at,valid_until=excluded.valid_until,independent_attested=excluded.independent_attested,status='active',updated_at=excluded.updated_at,demo_only=0",
        (reviewer_id,email,display_name,credential_ref,credential_issuer,verified_by,now,valid_until,int(bool(independent_attested)),now,now),
    )
    row=c.execute("SELECT id FROM reviewer_profiles WHERE account_email=?",(email,)).fetchone()
    reviewer_id=row["id"]
    c.execute(
        "INSERT INTO reviewer_scopes(id,reviewer_id,scope_key,status,verified_by,verified_at,valid_until,demo_only) "
        "VALUES(?,?,?,'active',?,?,?,0) ON CONFLICT(reviewer_id,scope_key) DO UPDATE SET status='active',verified_by=excluded.verified_by,verified_at=excluded.verified_at,valid_until=excluded.valid_until,demo_only=0",
        ("scope:"+reviewer_id+":"+scope_key,reviewer_id,scope_key,verified_by,now,valid_until),
    )
    _append_event(c,"reviewer_credential_attested",verified_by,{"reviewer_id":reviewer_id,"scope_key":scope_key,"issuer":credential_issuer,"independent_attested":bool(independent_attested)},demo_only=0)
    return reviewer_id


def assign_candidate(c,candidate_id,reviewer_email,assigned_by,scope_key=DEFAULT_SCOPE):
    candidate=c.execute(
        "SELECT id,status,demo_only FROM evidence_admission_candidates WHERE id=?",
        (candidate_id,),
    ).fetchone()
    if not candidate:
        raise ValueError("candidate_not_found")
    if candidate["status"] not in ("pending_review","review_ready"):
        raise ValueError("candidate_not_assignable")
    production=not bool(candidate["demo_only"])
    profile=validate_reviewer(c,reviewer_email,scope_key,production=production)
    editorial=c.execute(
        "SELECT reviewer,status FROM evidence_admission_reviews WHERE candidate_id=? AND review_role='editorial'",
        (candidate_id,),
    ).fetchone()
    accepted_editorial=("accepted_demo","accepted_editorial")
    if not editorial or editorial["status"] not in accepted_editorial:
        raise ValueError("editorial_review_required_before_assignment")
    if editorial["reviewer"] and editorial["reviewer"].lower()==reviewer_email.lower():
        raise ValueError("separation_of_duties_violation")
    conflict_history=c.execute(
        "SELECT 1 FROM review_conflict_disclosures rcd "
        "JOIN review_assignments ra ON ra.id=rcd.assignment_id "
        "WHERE ra.candidate_id=? AND ra.reviewer_id=? AND rcd.conflict_state IN ('potential','material') LIMIT 1",
        (candidate_id,profile["id"]),
    ).fetchone()
    if conflict_history:
        raise ValueError("reviewer_conflict_history_blocks_reassignment")
    active=c.execute(
        "SELECT id,status FROM review_assignments WHERE candidate_id=? AND review_role='scientific' AND status IN ('assigned','completed') ORDER BY assigned_at DESC LIMIT 1",
        (candidate_id,),
    ).fetchone()
    if active:
        raise ValueError("scientific_assignment_exists")
    now=time.time_ns()
    seed=f"{candidate_id}|{profile['id']}|{assigned_by}|{now}"
    assignment_id="review-assignment:"+hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    c.execute(
        "INSERT INTO review_assignments(id,candidate_id,review_role,reviewer_id,required_scope,status,assigned_by,assigned_at,demo_only) "
        "VALUES(?,?,'scientific',?,?,'assigned',?,?,?)",
        (assignment_id,candidate_id,profile["id"],scope_key,assigned_by,now,int(candidate["demo_only"])),
    )
    c.execute(
        "UPDATE evidence_admission_reviews SET reviewer=?,note=? WHERE candidate_id=? AND review_role='scientific'",
        (reviewer_email,"Assigned through Reviewer Authority.",candidate_id),
    )
    _append_event(c,"scientific_review_assigned",assigned_by,{"reviewer_id":profile["id"],"reviewer_email":reviewer_email,"scope_key":scope_key},candidate_id,assignment_id,candidate["demo_only"])
    return assignment_id


def declare_conflict(c,assignment_id,reviewer_email,conflict_state,details=""):
    if conflict_state not in VALID_CONFLICTS:
        raise ValueError("invalid_conflict_state")
    row=c.execute(
        "SELECT ra.*,rp.account_email FROM review_assignments ra JOIN reviewer_profiles rp ON rp.id=ra.reviewer_id WHERE ra.id=?",
        (assignment_id,),
    ).fetchone()
    if not row:
        raise ValueError("assignment_not_found")
    if row["account_email"].lower()!=str(reviewer_email or "").lower():
        raise ValueError("assignment_reviewer_mismatch")
    if row["status"]!="assigned":
        raise ValueError("assignment_not_active")
    now=time.time_ns()
    seed=f"{assignment_id}|{conflict_state}|{now}"
    disclosure_id="conflict:"+hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    c.execute(
        "INSERT INTO review_conflict_disclosures(id,assignment_id,reviewer_id,conflict_state,details,disclosed_at,demo_only) VALUES(?,?,?,?,?,?,?)",
        (disclosure_id,assignment_id,row["reviewer_id"],conflict_state,str(details or "")[:1200],now,int(row["demo_only"])),
    )
    if conflict_state=="material":
        c.execute("UPDATE review_assignments SET status='recused' WHERE id=?",(assignment_id,))
    elif conflict_state=="potential":
        c.execute("UPDATE review_assignments SET status='conflict_hold' WHERE id=?",(assignment_id,))
    _append_event(c,"conflict_disclosed",reviewer_email,{"state":conflict_state,"details":str(details or "")[:1200]},row["candidate_id"],assignment_id,row["demo_only"])
    return disclosure_id


def _latest_conflict(c,assignment_id):
    return c.execute(
        "SELECT conflict_state,details,disclosed_at FROM review_conflict_disclosures WHERE assignment_id=? ORDER BY disclosed_at DESC,id DESC LIMIT 1",
        (assignment_id,),
    ).fetchone()


def submit_decision(c,assignment_id,reviewer_email,decision,rationale=""):
    if decision not in VALID_DECISIONS:
        raise ValueError("invalid_review_decision")
    row=c.execute(
        "SELECT ra.*,rp.account_email,ac.snapshot_id,ac.demo_only candidate_demo,s.payload_hash "
        "FROM review_assignments ra JOIN reviewer_profiles rp ON rp.id=ra.reviewer_id "
        "JOIN evidence_admission_candidates ac ON ac.id=ra.candidate_id "
        "JOIN evidence_provider_snapshots s ON s.id=ac.snapshot_id WHERE ra.id=?",
        (assignment_id,),
    ).fetchone()
    if not row:
        raise ValueError("assignment_not_found")
    reviewer_email=str(reviewer_email or "").lower()
    if row["account_email"].lower()!=reviewer_email:
        raise ValueError("assignment_reviewer_mismatch")
    if row["status"]!="assigned":
        raise ValueError("assignment_not_active")
    validate_reviewer(c,reviewer_email,row["required_scope"],production=not bool(row["candidate_demo"]))
    conflict=_latest_conflict(c,assignment_id)
    if not conflict:
        raise ValueError("conflict_disclosure_required")
    if conflict["conflict_state"]!="none":
        raise ValueError("conflict_blocks_decision")
    if c.execute("SELECT 1 FROM review_decisions WHERE assignment_id=?",(assignment_id,)).fetchone():
        raise ValueError("decision_already_recorded")
    signed_at=time.time_ns()
    attestation={
        "assignment_id":assignment_id,
        "candidate_id":row["candidate_id"],
        "reviewer_id":row["reviewer_id"],
        "reviewer_email":reviewer_email,
        "decision":decision,
        "rationale":str(rationale or "")[:2400],
        "evidence_snapshot_hash":row["payload_hash"],
        "signed_at":signed_at,
        "method":"authenticated_session_digest_v1",
    }
    digest=hashlib.sha256(_canonical(attestation).encode("utf-8")).hexdigest()
    decision_id="review-decision:"+digest[:24]
    c.execute(
        "INSERT INTO review_decisions(id,assignment_id,candidate_id,reviewer_id,decision,rationale,evidence_snapshot_hash,attestation_method,decision_digest,signed_at,demo_only) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (decision_id,assignment_id,row["candidate_id"],row["reviewer_id"],decision,attestation["rationale"],row["payload_hash"],attestation["method"],digest,signed_at,int(row["candidate_demo"])),
    )
    c.execute("UPDATE review_assignments SET status='completed',completed_at=? WHERE id=?",(signed_at,assignment_id))
    if decision=="accept":
        c.execute(
            "UPDATE evidence_admission_reviews SET status='accepted_authority',reviewer=?,reviewed_at=?,note=? WHERE candidate_id=? AND review_role='scientific'",
            (reviewer_email,signed_at,"Reviewer Authority decision digest "+digest[:16],row["candidate_id"]),
        )
        editorial=c.execute(
            "SELECT status FROM evidence_admission_reviews WHERE candidate_id=? AND review_role='editorial'",
            (row["candidate_id"],),
        ).fetchone()
        accepted=("accepted_demo","accepted_editorial")
        if editorial and editorial["status"] in accepted:
            c.execute("UPDATE evidence_admission_candidates SET status='review_ready' WHERE id=?",(row["candidate_id"],))
    elif decision=="reject":
        c.execute(
            "UPDATE evidence_admission_reviews SET status='rejected_authority',reviewer=?,reviewed_at=?,note=? WHERE candidate_id=? AND review_role='scientific'",
            (reviewer_email,signed_at,attestation["rationale"],row["candidate_id"]),
        )
        c.execute("UPDATE evidence_admission_candidates SET status='rejected_review' WHERE id=?",(row["candidate_id"],))
    else:
        c.execute(
            "UPDATE evidence_admission_reviews SET status='changes_requested_authority',reviewer=?,reviewed_at=?,note=? WHERE candidate_id=? AND review_role='scientific'",
            (reviewer_email,signed_at,attestation["rationale"],row["candidate_id"]),
        )
        c.execute("UPDATE evidence_admission_candidates SET status='pending_review' WHERE id=?",(row["candidate_id"],))
    _append_event(c,"scientific_review_decision",reviewer_email,{"decision":decision,"decision_digest":digest,"snapshot_hash":row["payload_hash"]},row["candidate_id"],assignment_id,row["candidate_demo"])
    return {"decision_id":decision_id,"decision_digest":digest}



def record_governance_admission(c,candidate_id,actor,source_id,change_event_id=None):
    account=c.execute("SELECT role,status FROM accounts WHERE email=?",(str(actor or "").lower(),)).fetchone()
    if not account or account["role"]!="governance" or account["status"]!="active":
        raise ValueError("governance_admission_required")
    reviews=list(c.execute(
        "SELECT review_role,reviewer,status FROM evidence_admission_reviews WHERE candidate_id=?",
        (candidate_id,),
    ))
    reviewers={str(x["reviewer"] or "").lower() for x in reviews if x["review_role"] in ("editorial","scientific")}
    if str(actor or "").lower() in reviewers:
        raise ValueError("separation_of_duties_violation")
    _append_event(
        c,
        "governance_admission",
        str(actor or "").lower(),
        {"source_id":source_id,"change_event_id":change_event_id or ""},
        candidate_id,
        None,
        0,
    )


def snapshot(c):
    profiles=[dict(r) for r in c.execute("SELECT id,account_email,display_name,reviewer_kind,credential_state,credential_issuer,credential_verified_by,credential_verified_at,valid_until,independent_attested,status,demo_only FROM reviewer_profiles ORDER BY display_name")]
    scopes=[dict(r) for r in c.execute("SELECT reviewer_id,scope_key,status,verified_by,verified_at,valid_until,demo_only FROM reviewer_scopes ORDER BY reviewer_id,scope_key")]
    assignments=[dict(r) for r in c.execute("SELECT id,candidate_id,review_role,reviewer_id,required_scope,status,assigned_by,assigned_at,completed_at,demo_only FROM review_assignments ORDER BY assigned_at DESC LIMIT 50")]
    conflicts=[dict(r) for r in c.execute("SELECT id,assignment_id,reviewer_id,conflict_state,details,disclosed_at,demo_only FROM review_conflict_disclosures ORDER BY disclosed_at DESC LIMIT 50")]
    decisions=[dict(r) for r in c.execute("SELECT id,assignment_id,candidate_id,reviewer_id,decision,evidence_snapshot_hash,attestation_method,decision_digest,signed_at,demo_only FROM review_decisions ORDER BY signed_at DESC LIMIT 50")]
    return {
        "version":"medical-review-authority-v1",
        "profiles":profiles,
        "scopes":scopes,
        "assignments":assignments,
        "conflicts":conflicts,
        "decisions":decisions,
        "event_chain_valid":verify_event_chain(c),
        "separation_rule":"Production scientific reviewer must be separately authorized; governance admission must be performed by an actor distinct from editorial and scientific reviewers.",
        "truth_boundary":{
            "independent_reviewer_authority_model":True,
            "credential_registry_integration":False,
            "legal_e_signature":False,
            "decision_attestation_digest":True,
            "db_append_only_audit":True,
            "tamper_evident_hash_chain":True,
        },
    }
