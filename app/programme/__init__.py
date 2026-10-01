from app.domain import audit, dump, hash_text, now, uid

def create_proposal(c,data,actor):
    pid=str(data.get("id") or uid("proposal"))
    title=str(data.get("title") or "").strip()
    if not title: raise ValueError("title_required")
    c.execute("INSERT INTO programme_proposals(id,topic,title,format,proposer,state,disclosure,created_at,updated_at) VALUES(?,?,?,?,?,'proposal',?,?,?)",
              (pid,str(data.get("topic") or ""),title,str(data.get("format") or "talk"),str(data.get("proposer") or actor),str(data.get("disclosure") or ""),now(),now()))
    for item in ("speaker_confirmation","materials","moderator_brief","room_requirements","production_readiness"):
        c.execute("INSERT INTO production_checklists(id,proposal_id,item_key,status,owner,deadline,updated_at) VALUES(?,?,?,'pending','','',?) ON CONFLICT(proposal_id,item_key) DO NOTHING",
                  (uid("check"),pid,item,now()))
    audit(c,"programme_proposal_created",actor,{"proposal_id":pid})
    return get_proposal(c,pid)

def get_proposal(c,pid):
    row=c.execute("SELECT * FROM programme_proposals WHERE id=?",(pid,)).fetchone()
    if not row:return None
    d=dict(row)
    d["checklist"]=[dict(x) for x in c.execute("SELECT * FROM production_checklists WHERE proposal_id=? ORDER BY item_key",(pid,))]
    d["invitations"]=[dict(x) for x in c.execute("SELECT * FROM speaker_invitations WHERE proposal_id=? ORDER BY id",(pid,))]
    return d

def set_proposal_state(c,pid,state,actor):
    allowed={"proposal","editorial_accepted","speaker_confirmed","materials_ready","production_ready","approved","rejected"}
    if state not in allowed: raise ValueError("bad_state")
    c.execute("UPDATE programme_proposals SET state=?,updated_at=? WHERE id=?",(state,now(),pid))
    audit(c,"programme_proposal_state",actor,{"proposal_id":pid,"state":state})
    return get_proposal(c,pid)

def checklist(c,pid,item_key,status,actor,owner="",deadline=""):
    c.execute("""INSERT INTO production_checklists(id,proposal_id,item_key,status,owner,deadline,updated_at) VALUES(?,?,?,?,?,?,?)
                 ON CONFLICT(proposal_id,item_key) DO UPDATE SET status=excluded.status,owner=excluded.owner,deadline=excluded.deadline,updated_at=excluded.updated_at""",
              (uid("check"),pid,item_key,status,owner,deadline,now()))
    audit(c,"production_checklist_updated",actor,{"proposal_id":pid,"item_key":item_key,"status":status})

def invite_speaker(c,pid,data,actor):
    iid=uid("invite")
    c.execute("INSERT INTO speaker_invitations(id,proposal_id,speaker_id,email,state,conflict_disclosure,updated_at) VALUES(?,?,?,?,?,?,?)",
              (iid,pid,str(data.get("speaker_id") or ""),str(data.get("email") or ""),"invited",str(data.get("conflict_disclosure") or ""),now()))
    audit(c,"speaker_invited",actor,{"proposal_id":pid,"invitation_id":iid})
    return iid

def create_revision(c,actor):
    proposals=[dict(r) for r in c.execute("SELECT * FROM programme_proposals WHERE state='approved' ORDER BY id")]
    snapshot=dump(proposals)
    num=(c.execute("SELECT COUNT(*) n FROM programme_revisions").fetchone()["n"] or 0)+1
    rid=uid("revision")
    c.execute("INSERT INTO programme_revisions(id,revision_no,state,snapshot_json,snapshot_hash,approved_by,created_at) VALUES(?,?,'approved',?,?,?,?)",
              (rid,num,snapshot,hash_text(snapshot),actor,now()))
    audit(c,"programme_revision_approved",actor,{"revision_id":rid,"revision_no":num})
    return dict(c.execute("SELECT * FROM programme_revisions WHERE id=?",(rid,)).fetchone())

def add_qualification(c,speaker_id,data,actor):
    qid=uid("qual")
    c.execute("INSERT INTO expert_qualifications(id,speaker_id,qualification,organisation,source_id,review_state,created_at) VALUES(?,?,?,?,?,'pending_review',?)",
              (qid,speaker_id,str(data.get("qualification") or ""),str(data.get("organisation") or ""),str(data.get("source_id") or ""),now()))
    audit(c,"expert_qualification_added",actor,{"speaker_id":speaker_id,"qualification_id":qid})
    return qid

def add_disclosure(c,speaker_id,data,actor):
    did=uid("disclosure")
    c.execute("INSERT INTO expert_disclosures(id,speaker_id,declaration,state,valid_from,valid_to,updated_at) VALUES(?,?,?,'reviewed',?,?,?)",
              (did,speaker_id,str(data.get("declaration") or ""),str(data.get("valid_from") or ""),str(data.get("valid_to") or ""),now()))
    audit(c,"expert_disclosure_added",actor,{"speaker_id":speaker_id,"disclosure_id":did})
    return did

def profile(c,speaker_id):
    base=c.execute("SELECT * FROM speakers WHERE id=?",(speaker_id,)).fetchone()
    if not base:return None
    d=dict(base)
    d["qualifications"]=[dict(r) for r in c.execute("SELECT * FROM expert_qualifications WHERE speaker_id=? ORDER BY created_at DESC",(speaker_id,))]
    d["disclosures"]=[dict(r) for r in c.execute("SELECT * FROM expert_disclosures WHERE speaker_id=? ORDER BY updated_at DESC",(speaker_id,))]
    d["publications"]=[dict(r) for r in c.execute("""SELECT ep.*,s.title,s.identifier,s.url FROM expert_publications ep
                                                    JOIN evidence_sources s ON s.id=ep.source_id WHERE ep.speaker_id=?""",(speaker_id,))]
    d["appearances"]=[dict(r) for r in c.execute("""SELECT p.id,p.title,p.start,p.venue,p.track FROM session_speakers ss
                                                   JOIN program_items p ON p.id=ss.item_id WHERE ss.speaker_id=? ORDER BY p.start""",(speaker_id,))]
    return d

def version_profile(c,speaker_id,actor):
    p=profile(c,speaker_id)
    if not p: raise LookupError("speaker_not_found")
    snapshot=dump(p)
    version=(c.execute("SELECT COUNT(*) n FROM expert_profile_versions WHERE speaker_id=?",(speaker_id,)).fetchone()["n"] or 0)+1
    vid=uid("expertver")
    c.execute("INSERT INTO expert_profile_versions(id,speaker_id,version,state,snapshot_json,snapshot_hash,reviewed_by,created_at) VALUES(?,?,?,'reviewed',?,?,?,?)",
              (vid,speaker_id,version,snapshot,hash_text(snapshot),actor,now()))
    audit(c,"expert_profile_versioned",actor,{"speaker_id":speaker_id,"version":version})
    return {"id":vid,"version":version,"snapshot_hash":hash_text(snapshot)}
