"""Read-only operations for a verified institutional administrator; no contacts."""
import time
from urllib.parse import parse_qs,urlparse
from app import db,partner_org_scope

ROUTE='/api/organization-operations/v1'


def read(c,path,role,email):
    parsed=urlparse(path)
    args=parse_qs(parsed.query,keep_blank_values=True)
    if parsed.fragment or set(args)!={'organization_id'} or len(args['organization_id'])!=1:
        return {'error':'unsupported_query'},422
    org=partner_org_scope.org_id(args['organization_id'][0])
    if not org:return {'error':'invalid_organization'},422
    if role!='organizer' or (not db.demo_seed_enabled() and email.lower().endswith('@demo.ru')):
        return {'error':'forbidden'},403
    now=int(time.time())
    admitted=c.execute("SELECT o.id,o.name,o.demo_only FROM institutional_organizations o "
        "JOIN institutional_memberships m ON m.organization_id=o.id "
        "JOIN accounts a ON a.email=m.account_email "
        "WHERE o.id=? AND o.status='active' AND LENGTH(TRIM(o.partner_id))>0 "
        "AND a.email=? AND a.role='organizer' AND a.status='active' "
        "AND m.status='active' AND m.member_role='administrator' "
        "AND m.effective_at<=? AND (m.expires_at IS NULL OR m.expires_at>?) "
        "AND LENGTH(TRIM(m.verification_ref))>0 AND m.demo_only=o.demo_only "
        "AND (?=1 OR o.demo_only=0) LIMIT 1",(org,email,now,now,int(db.demo_seed_enabled()))).fetchone()
    if not admitted:return {'error':'organization_not_found'},404
    counts=c.execute("SELECT COUNT(*) slots,COALESCE(SUM(s.capacity),0) capacity,"
        "COALESCE(SUM((SELECT COUNT(*) FROM participant_partner_appointments_v1 b WHERE b.slot_id=s.id AND b.status='booked')),0) booked,"
        "COALESCE(SUM((SELECT COUNT(*) FROM participant_partner_appointments_v1 b WHERE b.slot_id=s.id AND b.status='waitlist')),0) waitlist "
        "FROM partner_appointment_slots_v1 s WHERE s.organization_id=? AND s.demo_only=? "
        "AND s.status IN ('open','closed') AND s.ends_at>?",(org,admitted['demo_only'],now)).fetchone()
    placement=c.execute('SELECT status FROM partner_commercial_placements_v1 WHERE organization_id=? AND demo_only=?',(org,admitted['demo_only'])).fetchone()
    leads=c.execute("SELECT COUNT(*) n FROM participant_partner_leads_v1 WHERE organization_id=? AND status='submitted'",(org,)).fetchone()['n']
    capacity,booked=int(counts['capacity']),int(counts['booked'])
    enabled=bool(placement and placement['status']=='enabled')
    return {'organization':{'id':org,'name':admitted['name']},'asOf':now,
        'placementStatus':placement['status'] if placement else None,
        'metrics':{'upcomingSlots':int(counts['slots']),'capacity':capacity,'booked':booked if enabled else 0,
                   'unavailableBookings':0 if enabled else booked,
                   'waitlist':int(counts['waitlist']),'activeLeads':int(leads),
                   'occupancyPercent':round(100*booked/capacity,1) if capacity and enabled else None},
        'truthBoundary':{'organizationOnly':True,'contactsExported':False,'bookingsAreNotAttendance':True,
                         'revenueClaimed':False,'includesOngoingSlots':True}},200


def serve(actor,path):
    if not actor:return {'error':'unauthorized'},401
    c=db.connect()
    try:return read(c,path,actor[0],actor[2])
    finally:c.close()
