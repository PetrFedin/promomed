"""One own-account availability policy for management, agenda and invitations."""
from app import db


def positive_time(value):
    return value if type(value) is int and 0 < value <= 253402300799 else None


def owned(c,email,now):
    seed=db.demo_seed_enabled()
    rows=list(c.execute(
        "SELECT b.slot_id,b.status,b.contact_consent_at,b.requested_at,b.updated_at,"
        "s.organization_id,s.starts_at,s.ends_at,s.status slot_status,s.demo_only,"
        "o.name organization_name,o.status org_status,o.partner_id,"
        "o.demo_only org_demo,p.status placement_status,p.demo_only placement_demo "
        "FROM participant_partner_appointments_v1 b "
        "JOIN partner_appointment_slots_v1 s ON s.id=b.slot_id "
        "JOIN institutional_organizations o ON o.id=s.organization_id "
        "LEFT JOIN partner_commercial_placements_v1 p ON p.organization_id=o.id "
        "WHERE b.email=? AND (?=1 OR s.demo_only=0) "
        "ORDER BY CASE WHEN s.ends_at>? THEN 0 ELSE 1 END,s.starts_at,b.slot_id LIMIT 201",
        (email,int(seed),now)))
    result=[]
    for source in rows[:200]:
        row=dict(source)
        if not positive_time(row['starts_at']) or not positive_time(row['ends_at']) or row['ends_at']<=row['starts_at']:
            continue
        admitted=(row['org_status']=='active' and isinstance(row['partner_id'],str)
                  and bool(row['partner_id'].strip()) and row['demo_only']==row['org_demo']
                  and row['placement_status']=='enabled' and row['placement_demo']==row['demo_only']
                  and row['slot_status'] in ('open','closed'))
        row['effective_status']=('cancelled' if row['status']=='cancelled' else row['status'] if admitted else 'unavailable')
        row['can_cancel']=row['status'] in ('booked','waitlist')
        row['temporal_state']='past' if row['ends_at']<=now else 'upcoming' if row['starts_at']>now else 'ongoing'
        for key in ('partner_id','org_status','org_demo','placement_status','placement_demo','demo_only'):
            row.pop(key)
        result.append(row)
    return result,len(rows)>200
