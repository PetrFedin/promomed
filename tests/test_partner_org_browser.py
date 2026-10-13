"""Responsive browser proof of tenant choice and revocation, synthetic SQLite only."""
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import expect,sync_playwright

BASE=os.getenv("PROMOMED_BASE_URL","http://127.0.0.1:10000").rstrip("/")
OUT=Path(os.getenv("PROMOMED_SCREENSHOT_DIR","artifacts/browser-qa"))/"tenant-scope"


def create_synthetic_institution():
    os.environ["SQLITE_PATH"]=os.getenv("PROMOMED_BROWSER_QA_SQLITE_PATH",
                                         "/tmp/promomed-browser-qa.db")
    os.environ.pop("DATABASE_URL",None)
    from app import db,evidence_interchange,syndication_network
    c=db.connect()
    org="ORG-BROWSER-"+secrets.token_hex(5)
    try:
        evidence_interchange.register_organization(
            c,organization_id=org,name="Synthetic Tenant Browser",
            organization_type="strategic_partner",
            actor="governance@demo.ru",
            external_ref="urn:synthetic:"+org,
            credential_source="CI browser demo fixture",
            demo_only=True)
        syndication_network.bind_member(
            c,org,"partner@demo.ru","operator",
            "governance@demo.ru",
            verification_ref="synthetic-browser-proof",
            demo_only=True)
        c.commit()
        return org
    finally:c.close()


def revoke(org):
    from app import db
    c=db.connect()
    try:
        c.execute("UPDATE institutional_memberships SET status='revoked' "
                  "WHERE organization_id=? AND account_email=?",
                  (org,"partner@demo.ru"))
        c.commit()
    finally:c.close()


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    org=create_synthetic_institution()
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={"width":375,"height":812},locale="ru-RU")
            page.goto(BASE+"/partner-collaboration.html",wait_until="domcontentloaded")
            expect(page.locator("#workspace")).to_be_hidden()
            page.locator("#email").fill("partner@demo.ru")
            page.locator("#password").fill("demo2027")
            page.get_by_role("button",name="Войти").click()
            expect(page.locator("#workspace")).to_be_visible()
            expect(page.locator("#organization")).to_contain_text("Synthetic Tenant Browser")
            page.locator("#organization").select_option(org)
            name="Tenant browser QA "+secrets.token_hex(3)
            page.locator("#title").fill(name)
            page.locator("#objective").fill("Synthetic tenant-only Studio content planning")
            page.locator("#format").select_option("studio")
            page.get_by_role("button",name="Создать черновик").click()
            expect(page.locator("#projectTitle")).to_have_text(name)
            expect(page.locator("#projectObjective")).to_contain_text(org)
            expect(page.locator("#projects")).to_contain_text(name)
            # Synthetic demo membership can create a task, but not a contract.
            page.locator("#taskTitle").fill("Synthetic scoped task")
            page.get_by_role("button",name="Добавить задачу").click()
            expect(page.locator("#tasks")).to_contain_text("Synthetic scoped task")
            page.screenshot(path=str(OUT/"phone-org-scoped.png"),full_page=True)
            token_resp=page.request.post(BASE+"/api/login",
                     data={"email":"partner@demo.ru","password":"demo2027"})
            assert token_resp.status==200
            token=token_resp.json()["token"]
            project_data=page.request.get(BASE+"/api/partner-collaboration",
                        headers={"Authorization":"Bearer "+token}).json()
            pid=next(x["id"] for x in project_data["projects"] if x["title"]==name)
            page.set_viewport_size({"width":820,"height":1180})
            page.screenshot(path=str(OUT/"tablet-org-scoped.png"),full_page=True)
            assert page.evaluate("document.documentElement.scrollWidth-document.documentElement.clientWidth")<=1
            revoke(org)
            resp=page.request.get(BASE+"/api/partner-collaboration?project_id="+pid,
                       headers={"Authorization":"Bearer "+token})
            assert resp.status==404,resp.text()
            page.get_by_role("button",name="Обновить").click()
            expect(page.locator("#projects")).not_to_contain_text(name)
            expect(page.locator("#detail")).to_be_hidden()
            expect(page.locator("#placeholder")).to_be_visible()
            page.screenshot(path=str(OUT/"revoked-tenant-no-data.png"),full_page=True)
        finally:
            browser.close()


if __name__=="__main__":main()
