"""Cross-role source-backed appointment and reporting regression."""
import unittest
from tests import test_partner_appointments as fixtures
from app import partner_appointments as appt,partner_commercial as commercial
from app import organization_operations as operations,participant_agenda as agenda


class RoleOperationsTests(unittest.TestCase):
    setUp=fixtures.PartnerAppointmentTests.setUp
    tearDown=fixtures.PartnerAppointmentTests.tearDown
    enable=fixtures.PartnerAppointmentTests.enable
    cmd=fixtures.PartnerAppointmentTests.cmd
    create_slot=fixtures.PartnerAppointmentTests.create_slot
    booking_status=fixtures.PartnerAppointmentTests.booking_status

    def available(self,email=None,org='ORG-A'):
        return appt.read(self.c,appt.AVAILABLE_ROUTE+'?organization_id='+org,'participant',email or self.participant_a)

    def owner(self):
        email='owner@example.test'
        self.c.execute("INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) VALUES(?,'unused','organizer','Owner','active',?,?)",(email,self.now,self.now))
        self.c.execute("INSERT INTO institutional_memberships(id,organization_id,account_email,member_role,status,effective_at,verified_by,verification_ref,demo_only) VALUES('OWNER','ORG-A',?,'administrator','active',?,'governance','test',0)",(email,self.now-1))
        self.c.commit()
        return email

    def report(self,email,org='ORG-A'):
        return operations.read(self.c,operations.ROUTE+'?organization_id='+org,'organizer',email)

    def book(self,slot,email=None,version=1):
        return self.cmd('participant',email or self.participant_a,action='book',slot_id=slot,contact_consent=True,expected_version=version)

    def test_participant_partner_owner_share_records_and_queue(self):
        owner=self.owner();slot=self.create_slot()
        self.assertEqual(self.available()[0]['slots'][0]['version'],1)
        self.assertEqual(self.book(slot).payload['appointment']['status'],'booked')
        self.assertEqual(self.book(slot,self.participant_b).payload['appointment']['status'],'waitlist')
        before,status=self.report(owner)
        self.assertEqual(status,200);self.assertEqual(before['metrics']['booked'],1)
        self.assertEqual(before['metrics']['waitlist'],1)
        promoted=self.cmd('partner',self.partner_a,action='slot_update',slot_id=slot,expected_version=1,starts_at=self.now+3600,ends_at=self.now+5400,capacity=2,status='open')
        self.assertEqual(promoted.payload['queuePromotions'],1)
        own=appt.read(self.c,appt.ROUTE,'participant',self.participant_b)[0]['myAppointments'][0]
        self.assertEqual(own['effective_status'],'booked')
        self.assertEqual(agenda.snapshot(self.c,self.participant_b)['summary']['confirmedAppointments'],1)
        metrics=self.report(owner)[0]['metrics']
        self.assertEqual((metrics['booked'],metrics['waitlist'],metrics['occupancyPercent']),(2,0,100.0))
        self.cmd('participant',self.participant_a,action='cancel',slot_id=slot)
        self.assertEqual(self.report(owner)[0]['metrics']['occupancyPercent'],50.0)

    def test_stale_version_does_not_create_booking(self):
        slot=self.create_slot()
        self.cmd('partner',self.partner_a,action='slot_update',slot_id=slot,expected_version=1,starts_at=self.now+3600,ends_at=self.now+5400,capacity=2,status='open')
        result=self.book(slot)
        self.assertEqual((result.status,result.payload['error']),(409,'version_conflict'))
        self.assertIsNone(self.booking_status(slot,self.participant_a))
        self.assertEqual(self.book(slot,version=2).status,201)

    def test_malformed_booking_versions_rejected(self):
        slot=self.create_slot()
        for version in (True,False,None,0,-1,1.0,'1'):
            with self.subTest(version=version):self.assertEqual(self.book(slot,version=version).status,422)

    def test_invitation_privacy_overlap_and_query_boundary(self):
        slot=self.create_slot();self.book(slot)
        other=self.create_slot(org='ORG-B',partner=self.partner_b)
        data,status=self.available(org='ORG-B');self.assertEqual(status,200)
        self.assertEqual(data['slots'][0]['knownConflicts'][0]['overlapSeconds'],1800)
        self.assertNotIn(self.participant_a,str(data));self.assertNotIn(self.partner_b,str(data))
        self.assertEqual(self.available(email=self.participant_b)[0]['slots'][0]['availableSeats'],0)
        for suffix in ('','?organization_id=ORG-A&email=x','?organization_id=ORG-A&organization_id=ORG-B','?organization_id=ORG-A#x'):
            self.assertEqual(appt.read(self.c,appt.AVAILABLE_ROUTE+suffix,'participant',self.participant_a)[1],422)
        self.assertEqual(appt.read(self.c,appt.AVAILABLE_ROUTE+'?organization_id=ORG-A','partner',self.partner_a)[1],403)

    def test_pause_unifies_all_effective_states_and_keeps_cancellation(self):
        owner=self.owner();slot=self.create_slot();self.book(slot)
        result=commercial.handle_command(self.c,commercial.ROUTE,'partner',self.partner_a,{'action':'placement_update','organization_id':'ORG-A','status':'paused','expected_version':1})
        self.assertEqual(result.status,200);self.c.commit()
        self.assertEqual(self.available()[1],404)
        row=appt.read(self.c,appt.ROUTE,'participant',self.participant_a)[0]['myAppointments'][0]
        self.assertEqual(row['effective_status'],'unavailable');self.assertTrue(row['can_cancel'])
        self.assertEqual(agenda.snapshot(self.c,self.participant_a)['summary']['confirmedAppointments'],0)
        metrics=self.report(owner)[0]['metrics']
        self.assertEqual(metrics['booked'],0);self.assertEqual(metrics['unavailableBookings'],1)
        self.assertIsNone(metrics['occupancyPercent'])
        self.assertEqual(self.cmd('participant',self.participant_a,action='cancel',slot_id=slot).status,200)

    def test_owner_scope_revocation_and_contact_minimization(self):
        owner=self.owner();slot=self.create_slot();self.book(slot)
        self.assertEqual(self.report(owner,'ORG-B')[1],404)
        data,status=self.report(owner);self.assertEqual(status,200)
        self.assertNotIn(self.participant_a,str(data));self.assertNotIn(self.partner_a,str(data))
        for role in ('partner','participant','sales','staff'):
            self.assertEqual(operations.read(self.c,operations.ROUTE+'?organization_id=ORG-A',role,owner)[1],403)
        self.c.execute("UPDATE institutional_memberships SET status='revoked' WHERE id='OWNER'");self.c.commit()
        self.assertEqual(self.report(owner)[1],404)

    def test_counts_do_not_use_contact_page_length(self):
        slot=self.create_slot(capacity=1000)
        for index in range(501):
            self.c.execute("INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) VALUES(?,'unused','participant','Synthetic','active',?,?)",(f'synthetic-{index}@example.test',self.now,self.now))
            self.c.execute("INSERT INTO participant_partner_appointments_v1(slot_id,email,status,contact_consent_at,requested_at,updated_at) VALUES(?,?,'booked',?,?,?)",(slot,f'synthetic-{index}@example.test',self.now,self.now,self.now))
        self.c.commit()
        snapshot=appt.read(self.c,appt.ROUTE,'partner',self.partner_a)[0]
        row=snapshot['organizations'][0]['slots'][0]
        self.assertEqual(len(row['bookings']),500);self.assertTrue(row['bookingsTruncated'])
        self.assertEqual(row['counts']['booked'],501);self.assertEqual(row['counts']['available'],499)

    def test_closed_slot_does_not_promote_until_opened(self):
        slot=self.create_slot();self.book(slot);self.book(slot,self.participant_b)
        for version,status,expected in ((1,'closed',0),(2,'open',1)):
            result=self.cmd('partner',self.partner_a,action='slot_update',slot_id=slot,expected_version=version,starts_at=self.now+3600,ends_at=self.now+5400,capacity=2,status=status)
            self.assertEqual(result.payload['queuePromotions'],expected)

    def test_lead_submission_withdrawal_updates_partner_and_owner(self):
        owner=self.owner()
        body={'action':'lead_submit','organization_id':'ORG-A','kind':'contact_request','consent':True,'request_id':'e'*32}
        result=commercial.handle_command(self.c,commercial.ROUTE,'participant',self.participant_a,body)
        self.assertEqual(result.status,201);self.c.commit()
        self.assertEqual(self.report(owner)[0]['metrics']['activeLeads'],1)
        partner=commercial.read(self.c,commercial.ROUTE,'partner',self.partner_a)[0]['organizations'][0]
        self.assertEqual(partner['activeLeadCount'],1);self.assertEqual(partner['leads'][0]['email'],self.participant_a)
        lead=partner['leads'][0]['id']
        result=commercial.handle_command(self.c,commercial.ROUTE,'participant',self.participant_a,{'action':'lead_withdraw','lead_id':lead})
        self.assertEqual(result.status,200);self.c.commit()
        self.assertEqual(self.report(owner)[0]['metrics']['activeLeads'],0)
        partner=commercial.read(self.c,commercial.ROUTE,'partner',self.partner_a)[0]['organizations'][0]
        self.assertEqual(partner['leads'],[]);self.assertEqual(partner['activeLeadCount'],0)


class WorkloadMathTests(unittest.TestCase):
    def test_triple_overlap_counts_union_not_pairs(self):
        items=[{'kind':'partner_appointment','calendarEligible':True,'startsAt':a,'endsAt':b,'state':'booked'} for a,b in ((10,50),(20,40),(30,60))]
        result=agenda._workload(items,15)
        self.assertEqual(result['scheduledSeconds'],85)
        self.assertEqual(result['occupiedSeconds'],45)
        self.assertEqual(result['overlapSeconds'],30)

    def test_adjacent_intervals_do_not_overlap(self):
        items=[{'kind':'partner_appointment','calendarEligible':True,'startsAt':a,'endsAt':b,'state':'booked'} for a,b in ((10,20),(20,30))]
        self.assertEqual(agenda._workload(items,0)['overlapSeconds'],0)


if __name__=='__main__':unittest.main()
