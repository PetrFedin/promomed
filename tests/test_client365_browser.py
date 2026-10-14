"""Read-only Client 365: own-account UI, no inferred retention or leaks."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

BASE=os.environ.get("PROMOMED_BASE_URL","http://127.0.0.1:10000").rstrip("/")
OUT=Path(os.environ.get("PROMOMED_SCREENSHOT_DIR","artifacts/browser-qa"))/"client365"


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            for name,width,height in (("phone",375,812),("tablet",820,1180),("desktop",1440,900)):
                page=browser.new_page(viewport={"width":width,"height":height},locale="ru-RU")
                errors=[]
                page.on("pageerror",lambda e:errors.append(str(e)))
                page.goto(BASE,wait_until="domcontentloaded")
                page.evaluate("async () => await demoLogin('participant@demo.ru')")
                page.evaluate("show('me')")
                expect(page.locator("#me")).to_have_class("screen participant on")
                expect(page.locator("#client365Detail")).to_contain_text("PERSONAL EVIDENCE",timeout=12000)
                expect(page.locator("#client365Detail")).to_contain_text("ДЕМО")
                expect(page.locator("#client365Detail")).to_contain_text("D7")
                expect(page.locator("#client365Detail")).to_contain_text("не подтверждённая метрика возврата")
                response=page.request.get(BASE+"/api/client-365",
                    headers={"Authorization":"Bearer "+page.evaluate("localStorage.getItem('sostoyanie_token')")})
                assert response.status==200,response.text()
                data=response.json()
                assert data["demoOnly"] is True
                assert data["truthBoundary"]["cohortRetentionRate"] is None
                assert data["truthBoundary"]["recognizedRevenue"] is None
                assert all(not x["isEvidenceOfReturn"] for x in data["followups"])
                cross=page.request.get(BASE+"/api/client-365?email=participant2@demo.ru",
                    headers={"Authorization":"Bearer "+page.evaluate("localStorage.getItem('sostoyanie_token')")})
                assert cross.status==422,cross.text()
                page.screenshot(path=str(OUT/(name+"-own-history.png")),full_page=True)
                overflow=page.evaluate("document.documentElement.scrollWidth-document.documentElement.clientWidth")
                assert overflow<=1,(name,overflow)
                assert not errors,errors
                if name=="phone":
                    page.evaluate("async () => await switchRole('organizer')")
                    expect(page.locator("#client365Detail")).not_to_contain_text("PERSONAL EVIDENCE")
                    org_token=page.evaluate("localStorage.getItem('sostoyanie_token')")
                    denial=page.request.get(BASE+"/api/client-365",
                        headers={"Authorization":"Bearer "+org_token})
                    assert denial.status==403,denial.text()
                    page.evaluate("show('me')")
                    expect(page.locator("#me")).not_to_have_class("screen participant on")
                page.close()
        finally:browser.close()


if __name__=="__main__":
    main()
