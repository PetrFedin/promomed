"""Real private-workspace calendar screenshot and import proof.

Synthetic fixture is written into the isolated GitHub browser CI SQLite only.
"""
import os
import secrets
import sqlite3
import sys
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.auth import hash_password

BASE=os.environ.get("PROMOMED_BASE_URL","http://127.0.0.1:10000").rstrip("/")
DB=os.environ.get("PROMOMED_BROWSER_QA_SQLITE_PATH","/tmp/promomed-browser-qa.db")
OUT=Path(os.environ.get("PROMOMED_SCREENSHOT_DIR","artifacts/browser-qa"))/"agenda"


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    suffix=secrets.token_hex(5)
    email="agenda-browser-"+suffix+"@example.test"
    password="CI-only-"+secrets.token_urlsafe(18)+"Aa1!"
    event="AGENDA-B-"+suffix
    waitlist="AGENDA-W-"+suffix
    org="AGENDA-ORG-"+suffix
    slot=secrets.token_hex(16)
    now=int(time.time())
    c=sqlite3.connect(DB,timeout=20)
    try:
        c.execute(
            "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
            "VALUES(?,?,'participant','Agenda QA','active',?,?)",
            (email,hash_password(password),now,now),
        )
        for item,title,status in (
            (event,"Synthetic confirmed session","confirmed"),
            (waitlist,"Synthetic waiting session","waitlist"),
        ):
            c.execute(
                "INSERT INTO event_editions_v1("
                "id,title,starts_at,registration_status,capacity,demo_only,created_at,updated_at"
                ") VALUES(?,?,?,'open',10,0,?,?)",
                (item,title,now+86400,now,now),
            )
            c.execute(
                "INSERT INTO participant_event_registrations_v1("
                "event_id,email,status,requested_at,updated_at,source"
                ") VALUES(?,?,?,?,?,'participant')",
                (item,email,status,now,now),
            )
        c.execute(
            "INSERT INTO institutional_organizations("
            "id,name,organization_type,status,external_ref,credential_source,partner_id,"
            "created_at,created_by,demo_only) VALUES(?,?,?,'active','ci','ci','ci-partner',?, 'governance-ci',0)",
            (org,"Synthetic Agenda Partner","strategic_partner",now),
        )
        c.execute(
            "INSERT INTO partner_commercial_placements_v1("
            "organization_id,status,version,updated_at,updated_by,demo_only"
            ") VALUES(?,'enabled',1,?,'ci',0)",
            (org,now),
        )
        c.execute(
            "INSERT INTO partner_appointment_slots_v1("
            "id,organization_id,starts_at,ends_at,capacity,status,version,"
            "created_at,updated_at,created_by,demo_only"
            ") VALUES(?,?,?, ?,2,'open',1,?,?,'ci',0)",
            (slot,org,now+7200,now+9000,now,now),
        )
        c.execute(
            "INSERT INTO participant_partner_appointments_v1("
            "slot_id,email,status,contact_consent_at,requested_at,updated_at"
            ") VALUES(?,?,'booked',?,?,?)",
            (slot,email,now,now,now),
        )
        c.commit()

        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                for name,width,height in (
                    ("phone",375,812),("tablet",820,1180),("desktop",1440,900),
                ):
                    context=browser.new_context(
                        viewport={"width":width,"height":height},locale="ru-RU",
                        accept_downloads=True,
                    )
                    page=context.new_page()
                    errors=[]
                    page.on("pageerror",lambda error: errors.append(str(error)))
                    page.goto(BASE+"/personal/",wait_until="domcontentloaded")
                    page.fill("#email",email)
                    page.fill("#password",password)
                    page.click("#login-button")
                    expect(page.locator("#workspace")).to_be_visible(timeout=15000)
                    expect(page.locator("#participant-agenda .agendaItem")).to_have_count(
                        3,timeout=15000,
                    )
                    expect(page.locator("#participant-agenda")).to_contain_text(
                        "Synthetic confirmed session",
                    )
                    expect(page.locator("#participant-agenda")).to_contain_text(
                        "Лист ожидания",
                    )
                    expect(page.locator("#participant-agenda")).to_contain_text(
                        "Synthetic Agenda Partner",
                    )
                    expect(page.locator("#agenda-export")).to_be_enabled()
                    assert not errors,errors
                    page.screenshot(
                        path=str(OUT/(name+"-private-agenda.png")),full_page=True,
                    )
                    assert page.evaluate(
                        "document.documentElement.scrollWidth-document.documentElement.clientWidth"
                    )<=1,name
                    if name=="phone":
                        with page.expect_download() as downloaded:
                            page.click("#agenda-export")
                        file=downloaded.value
                        assert file.suggested_filename.endswith(".ics")
                        calendar=Path(file.path()).read_text(encoding="utf-8")
                        assert calendar.count("BEGIN:VEVENT")==2
                        assert "Synthetic confirmed session" in calendar
                        assert "Synthetic waiting session" not in calendar
                        assert email not in calendar
                    page.reload(wait_until="domcontentloaded")
                    expect(page.locator("#workspace")).to_be_hidden()
                    expect(page.locator("body")).not_to_contain_text(
                        "Synthetic confirmed session",
                    )
                    context.close()
            finally:
                browser.close()
    finally:
        try:
            c.execute(
                "DELETE FROM participant_partner_appointments_v1 WHERE slot_id=?",(slot,),
            )
            c.execute("DELETE FROM partner_appointment_slots_v1 WHERE id=?",(slot,))
            c.execute(
                "DELETE FROM partner_commercial_placements_v1 WHERE organization_id=?",
                (org,),
            )
            c.execute("DELETE FROM institutional_organizations WHERE id=?",(org,))
            c.execute(
                "DELETE FROM participant_event_registrations_v1 "
                "WHERE event_id IN (?,?)",(event,waitlist),
            )
            c.execute("DELETE FROM event_editions_v1 WHERE id IN (?,?)",(event,waitlist))
            c.execute("DELETE FROM auth_sessions WHERE email=?",(email,))
            c.execute("DELETE FROM accounts WHERE email=?",(email,))
            c.commit()
        finally:
            c.close()


if __name__=="__main__":
    main()
