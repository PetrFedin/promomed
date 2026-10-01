from app.domain import audit, now

DEFAULT_GATES = {
    "community_scale": ("deferred", "Native community remains canonical; reconsider only when moderation/trust requirements exceed it."),
    "learning_lms": ("deferred", "Native learning tracks remain canonical; full LMS requires accredited or complex assessment scope."),
    "wellness_routines": ("reference", "Extend native challenges/actions only; no imported medical or nutrition prescriptions."),
    "clinical_fhir": ("deferred", "Requires an authorised clinical provider use case, legal basis, controller roles and security architecture."),
    "public_web_analytics": ("optional", "Anonymous acquisition telemetry only; never replaces Customer Intelligence or Owner Control Tower."),
}

def ensure_defaults(c):
    ts=now()
    for key,(status,rationale) in DEFAULT_GATES.items():
        c.execute("""INSERT INTO integration_gates(gate_key,status,rationale,updated_at) VALUES(?,?,?,?)
                     ON CONFLICT(gate_key) DO NOTHING""",(key,status,rationale,ts))

def list_gates(c):
    ensure_defaults(c)
    return [dict(r) for r in c.execute("SELECT * FROM integration_gates ORDER BY gate_key")]

def set_gate(c,key,status,rationale,actor):
    ensure_defaults(c)
    if key not in DEFAULT_GATES:
        raise ValueError("unknown_gate")
    allowed={"deferred","reference","optional","approved","rejected"}
    if status not in allowed:
        raise ValueError("bad_gate_status")
    c.execute("UPDATE integration_gates SET status=?,rationale=?,updated_at=? WHERE gate_key=?",
              (status,str(rationale)[:1000],now(),key))
    audit(c,"integration_gate_changed",actor,{"gate":key,"status":status})
    return dict(c.execute("SELECT * FROM integration_gates WHERE gate_key=?",(key,)).fetchone())
