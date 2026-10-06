def _held(c,partner_id):
    try:
        row=c.execute("SELECT reason FROM publication_holds WHERE artifact_kind='partner' AND artifact_ref=? AND status='active' ORDER BY placed_at DESC LIMIT 1",(partner_id,)).fetchone()
        return (True,row["reason"]) if row else (False,"")
    except Exception:
        return False,""


def snapshot(c, email=None):
    placement = c.execute("SELECT status,name FROM placements WHERE id=1").fetchone()
    d = {
        "partners": [dict(r)|{"publication_hold":_held(c,r["id"])[0],"publication_hold_reason":_held(c,r["id"])[1]} for r in c.execute("SELECT * FROM partners ORDER BY name")],
        "partner_packages": [dict(r) for r in c.execute("SELECT * FROM partner_packages ORDER BY id")],
        "appointment_slots": [dict(r) for r in c.execute(
            'SELECT a.*,p.name partner_name FROM appointment_slots a LEFT JOIN partners p ON p.id=a.partner_id ORDER BY a.start'
        )],
        "placement_status": placement["status"] if placement else "contracted",
    }
    if email:
        d["meeting_items"] = [dict(r) for r in c.execute(
            "SELECT id,target,slot,place,status,ts FROM meetings WHERE requester=? ORDER BY id DESC LIMIT 8", (email,)
        )]
        d["product_interests"] = [dict(r) for r in c.execute(
            "SELECT id,track,context,consent_version,status,ts FROM product_interests WHERE email=? ORDER BY id DESC LIMIT 8", (email,)
        )]
        d["appointment_bookings"] = [dict(r) for r in c.execute(
            'SELECT b.slot_id,b.status,a.item_id,a.start,a."end",p.name partner_name FROM appointment_bookings b JOIN appointment_slots a ON a.id=b.slot_id LEFT JOIN partners p ON p.id=a.partner_id WHERE b.email=? ORDER BY a.start',
            (email,),
        )]
        d["appointment_history"] = [dict(r) for r in c.execute(
            "SELECT action,from_slot,to_slot,ts FROM appointment_history WHERE email=? ORDER BY id DESC LIMIT 10", (email,)
        )]
        d["partner_engagement"] = [dict(r) for r in c.execute(
            "SELECT partner,kind,ref_id,consent,ts FROM partner_engagement WHERE email=? ORDER BY id DESC LIMIT 12", (email,)
        )]
        d["meetings"] = c.execute(
            "SELECT COUNT(*) n FROM meetings WHERE requester=? AND status IN ('requested','confirmed')", (email,)
        ).fetchone()["n"]
    return d
