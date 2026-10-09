import os
from pathlib import Path
from playwright.sync_api import expect,sync_playwright
BASE_URL=os.environ.get("PROMOMED_BASE_URL","http://127.0.0.1:10000").rstrip("/")
OUT=Path(os.environ.get("PROMOMED_SCREENSHOT_DIR","artifacts/browser-qa"))/"outreach-pack"
VIEWPORTS=(("iphone",390,844),("tablet",820,1180),("desktop",1440,900))
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        b=p.chromium.launch()
        try:
            for name,w,h in VIEWPORTS:
                page=b.new_page(viewport={"width":w,"height":h})
                page.goto(f"{BASE_URL}/institutional-outreach-pack.html",wait_until="networkidle")
                expect(page).to_have_title("СОСТОЯНИЕ · Institutional Outreach Pack")
                expect(page.get_by_role("heading",name="Institutional Outreach Pack")).to_be_visible()
                expect(page.get_by_text("Meeting brief ≠ meeting happened.")).to_be_visible()
                expect(page.locator("#password")).to_have_value("")
                expect(page.get_by_role("button",name="Собрать brief")).to_be_visible()
                overflow=page.evaluate("document.documentElement.scrollWidth-document.documentElement.clientWidth")
                if overflow>1: raise AssertionError(f"{name}: horizontal overflow {overflow}px")
                page.screenshot(path=str(OUT/f"{name}.png"),full_page=True)
                page.close()
        finally: b.close()
if __name__=="__main__": main()
