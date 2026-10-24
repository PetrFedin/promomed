"""Isolated real-browser client -> partner -> organizer acceptance and media.

Runs its own synthetic SQLite server; never writes into a deployed environment.
"""
import os
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tests.test_role_operations import RoleOperationsTests
from playwright.sync_api import expect,sync_playwright


def main():
    fixture=RoleOperationsTests('test_participant_partner_owner_share_records_and_queue')
    fixture.setUp()
    output=Path(os.environ.get('PROMOMED_SCREENSHOT_DIR','artifacts/browser-qa'))/'role-operations'
    output.mkdir(parents=True,exist_ok=True)
    server=None
    try:
        owner=fixture.owner();slot=fixture.create_slot()
        fixture.c.execute('UPDATE accounts SET password_hash=(SELECT password_hash FROM accounts WHERE email=?) WHERE email=?',(fixture.participant_a,owner));fixture.c.commit()
        with socket.socket() as socket_probe:
            socket_probe.bind(('127.0.0.1',0));port=socket_probe.getsockname()[1]
        base='http://127.0.0.1:'+str(port)
        with open(output/'server.log','w') as log:
            server=subprocess.Popen([sys.executable,'server.py'],cwd=ROOT,env=dict(os.environ,PORT=str(port)),stdout=log,stderr=log)
            for _ in range(100):
                try:urllib.request.urlopen(base+'/health',timeout=1);break
                except Exception:time.sleep(.2)
            else:raise RuntimeError('Synthetic browser server did not start')
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True)
                context=browser.new_context(viewport={'width':1440,'height':1000},locale='ru-RU',timezone_id='Europe/Moscow')
                recording=browser.new_context(viewport={'width':1440,'height':1000},locale='ru-RU',timezone_id='Europe/Moscow',record_video_dir=str(output/'raw-video'),record_video_size={'width':1440,'height':1000})
                errors=[]
                def login(page,email,path):
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(base+path,wait_until='domcontentloaded')
                    page.fill('#email',email);page.fill('#password','StrongAppointment!42')
                    page.click('#login' if path=='/partner/' else '#login-button')
                    expect(page.locator('#workspace')).to_be_visible(timeout=15000)
                try:
                    client=context.new_page();login(client,fixture.participant_a,'/personal/?partner=ORG-A')
                    selection=client.locator('.availableSlot[data-slot="'+slot+'"]')
                    expect(selection.locator('button')).to_be_disabled()
                    selection.locator('input').check();selection.locator('button').click()
                    expect(client.locator('#appointment-record-'+slot)).to_contain_text('Место подтверждено')
                    waiter=recording.new_page();started=time.monotonic()
                    login(waiter,fixture.participant_b,'/personal/?partner=ORG-A')
                    selection=waiter.locator('.availableSlot[data-slot="'+slot+'"]')
                    expect(selection.locator('button')).to_have_text('Встать в очередь')
                    selection.scroll_into_view_if_needed();selection.locator('input').check();selection.locator('button').click()
                    expect(waiter.locator('#appointment-record-'+slot)).to_contain_text('Лист ожидания')
                    partner=context.new_page();login(partner,fixture.partner_a,'/partner/')
                    partner.locator('.slotControls input').fill('2');partner.get_by_role('button',name='Сохранить места',exact=True).click()
                    expect(partner.locator('.slotCounts')).to_have_text('Подтверждено: 2 · Ожидают: 0 · Свободно: 0')
                    waiter.click('#refresh');expect(waiter.locator('#appointment-record-'+slot)).to_contain_text('Место подтверждено')
                    expect(waiter.locator('.agendaMetrics dd').first).to_have_text('1')
                    owner_page=context.new_page();login(owner_page,owner,'/partner/')
                    owner_page.fill('#owner-organization','ORG-A');owner_page.locator('#owner-form button').click()
                    expect(owner_page.locator('#owner-data')).to_be_visible()
                    expect(owner_page.locator('#owner-metrics div').filter(has_text='Заполненность, %').locator('strong')).to_have_text('100')
                    consent=client.locator('.contactRequest input');consent.check();client.get_by_role('button',name='Запросить связь',exact=True).click()
                    expect(client.locator('#partner-leads')).to_contain_text('Контакт передан')
                    partner.click('#refresh');expect(partner.locator('#lead-count')).to_have_text('Активных заявок: 1')
                    owner_page.click('#refresh');expect(owner_page.locator('#owner-metrics div').filter(has_text='Активные заявки').locator('strong')).to_have_text('1')
                    client.locator('#partner-leads button').click()
                    partner.click('#refresh');expect(partner.locator('#lead-count')).to_have_text('Активных заявок: 0')
                    expect(partner.locator('#leads')).not_to_contain_text(fixture.participant_a)
                    for page,label in ((client,'participant'),(partner,'partner'),(owner_page,'organizer')):
                        for width in (375,768,1440):
                            page.set_viewport_size({'width':width,'height':1000})
                            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),label+' overflow at '+str(width)
                            page.screenshot(path=str(output/(label+'-'+str(width)+'.png')),full_page=True)
                    waiter.locator('.agendaCard').scroll_into_view_if_needed()
                    waiter.wait_for_timeout(max(0,24-(time.monotonic()-started))*1000)
                    video=waiter.video
                    recording.close();video.save_as(str(output/'queue-to-confirmation.webm'))
                    if shutil.which('ffmpeg'):
                        subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(output/'queue-to-confirmation.webm'),'-t','24','-an','-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(output/'queue-to-confirmation-24s.mp4')],check=True)
                    partner.select_option('#placement-status','paused');partner.locator('#placement-form button').click()
                    expect(partner.locator('#placement-state')).to_have_text('Приостановлено')
                    client.click('#refresh');expect(client.locator('#appointment-record-'+slot)).to_contain_text('Встреча недоступна')
                    owner_page.click('#refresh');expect(owner_page.locator('#owner-metrics div').filter(has_text='Записи недоступного размещения').locator('strong')).to_have_text('2')
                    client.reload();expect(client.locator('#workspace')).to_be_hidden()
                    assert not errors,errors
                    print('PASS: participant/partner/organizer booking, queue, capacity, lead withdrawal, placement pause, 375/768/1440 layouts and video')
                finally:
                    context.close();browser.close()
    finally:
        if server is not None:server.terminate();server.wait(timeout=10)
        fixture.tearDown()


if __name__=='__main__':main()
