from app.domain import audit, consent, hash_text, now, uid

def workspace(c,partner_id):
    partner=c.execute("SELECT * FROM partners WHERE id=?",(partner_id,)).fetchone()
    if not partner:return None
    return {
        "partner":dict(partner),
        "contacts":[dict(r) for r in c.execute("SELECT * FROM partner_contacts WHERE partner_id=? ORDER BY name",(partner_id,))],
        "commitments":[dict(r) for r in c.execute("SELECT * FROM partner_commitments WHERE partner_id=? ORDER BY updated_at DESC",(partner_id,))],
        "deliverables":[dict(r) for r in c.execute("SELECT * FROM partner_workspace_deliverables WHERE partner_id=? ORDER BY updated_at DESC",(partner_id,))],
        "evidence":[dict(r) for r in c.execute("SELECT * FROM partner_evidence WHERE partner_id=? ORDER BY created_at DESC",(partner_id,))],
        "leads":[dict(r) for r in c.execute("SELECT id,purpose,state,created_at FROM participant_consented_leads WHERE partner_id=? ORDER BY created_at DESC",(partner_id,))],
        "renewals":[dict(r) for r in c.execute("SELECT * FROM partner_renewals WHERE partner_id=? ORDER BY updated_at DESC",(partner_id,))]
    }

def upsert_contact(c,partner_id,data,actor):
    cid=str(data.get("id") or uid("contact"))
    c.execute("""INSERT INTO partner_contacts(id,partner_id,name,role,email,phone,state,updated_at) VALUES(?,?,?,?,?,?,'active',?)
                 ON CONFLICT(id) DO UPDATE SET name=excluded.name,role=excluded.role,email=excluded.email,phone=excluded.phone,state=excluded.state,updated_at=excluded.updated_at""",
              (cid,partner_id,str(data.get("name") or ""),str(data.get("role") or ""),str(data.get("email") or ""),str(data.get("phone") or ""),now()))
    audit(c,"partner_contact_upserted",actor,{"partner_id":partner_id,"contact_id":cid})
    return cid

def create_commitment(c,partner_id,data,actor):
    cid=uid("commitment")
    c.execute("INSERT INTO partner_commitments(id,partner_id,package_id,commitment,state,owner,deadline,updated_at) VALUES(?,?,?,?,?,?,?,?)",
              (cid,partner_id,str(data.get("package_id") or ""),str(data.get("commitment") or ""),"committed",str(data.get("owner") or actor),str(data.get("deadline") or ""),now()))
    audit(c,"partner_commitment_created",actor,{"partner_id":partner_id,"commitment_id":cid})
    return cid

def add_evidence(c,partner_id,data,actor):
    eid=uid("partner_evidence")
    ref=str(data.get("ref") or ""); summary=str(data.get("summary") or "")
    c.execute("INSERT INTO partner_evidence(id,partner_id,kind,ref,summary,checksum,created_at) VALUES(?,?,?,?,?,?,?)",
              (eid,partner_id,str(data.get("kind") or "delivery"),ref,summary,hash_text(ref+"|"+summary),now()))
    audit(c,"partner_evidence_added",actor,{"partner_id":partner_id,"evidence_id":eid})
    return eid

def create_consented_lead(c,email,partner_id,purpose,consent_version):
    lid=uid("partner_lead")
    c.execute("INSERT INTO participant_consented_leads(id,partner_id,email,purpose,consent_version,state,created_at) VALUES(?,?,?,?,?,'new',?)",
              (lid,partner_id,email,purpose,consent_version,now()))
    consent(c,email,"partner_lead",consent_version,True,"participant_action",partner_id)
    audit(c,"partner_consented_lead",email,{"partner_id":partner_id,"lead_id":lid,"purpose":purpose})
    return lid
