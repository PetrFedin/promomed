def snapshot(c, email=None):
    d = {
        "learning_tracks": [dict(r) for r in c.execute("SELECT * FROM learning_tracks ORDER BY id")],
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
