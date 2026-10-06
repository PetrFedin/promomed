def _held(c,track_id):
    try:
        row=c.execute("SELECT reason FROM publication_holds WHERE artifact_kind='learning' AND artifact_ref=? AND status='active' ORDER BY placed_at DESC LIMIT 1",(track_id,)).fetchone()
        return (True,row["reason"]) if row else (False,"")
    except Exception:
        return False,""


def snapshot(c, email=None):
    d = {
        "learning_tracks": [dict(r)|{"publication_hold":_held(c,r["id"])[0],"publication_hold_reason":_held(c,r["id"])[1]} for r in c.execute("SELECT * FROM learning_tracks ORDER BY id")],
        "learning_steps": [dict(r) for r in c.execute("SELECT * FROM learning_steps ORDER BY track_id,step_no")],
    }
    if email:
        d["challenges"] = [dict(r) for r in c.execute(
            "SELECT challenge_id,status,days_required,started,verified,reward FROM challenges WHERE email=?", (email,)
        )]
        d["challenge_actions"] = [dict(r) for r in c.execute(
            "SELECT challenge_id,action_id,label,status,ts FROM challenge_actions WHERE email=? ORDER BY action_id", (email,)
        )]
        d["learning_enrollments"] = [dict(r) for r in c.execute(
            "SELECT e.track_id,e.status,e.current_step,e.started,e.updated,t.title,t.duration_days,t.topic,(SELECT COUNT(*) FROM learning_steps ls WHERE ls.track_id=e.track_id) total_steps FROM learning_enrollments e JOIN learning_tracks t ON t.id=e.track_id WHERE e.email=? ORDER BY e.updated DESC",
            (email,),
        )]
    return d
