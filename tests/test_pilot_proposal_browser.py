import os
from pathlib import Path
from playwright.sync_api import expect, sync_playwright

BASE_URL=os.environ.get("PROMOMED_BASE_URL","http://127.0.0.1:10000").rstrip("/")
SCREENSHOT_DIR=Path(os.environ.get("PROMOMED_SCREENSHOT_DIR","artifacts/browser-qa"))/"pilot-proposal"
VIEWPORTS=(("iphone",390,844),("tablet",820,1180),("desktop",1440,900))

def main():
    SCREENSHOT_DIR.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch()
        try:
            for name,width,height in VIEWPORTS:
                page=browser.new_page(viewport={"width":width,"height":height})
                page.goto(f"{BASE_URL}/institutional-pilot-proposal.html",wait_until="networkidle")
                expect(page).to_have_title("СОСТОЯНИЕ · Institutional Pilot Proposal Studio")
                expect(page.get_by_role("heading",name="Institutional Pilot Proposal Studio")).to_be_visible()
                expect(page.get_by_text("PROPOSAL ≠ COMMITMENT.")).to_be_visible()
                expect(page.locator("#archetype")).to_be_visible()
                expect(page.locator("#password")).to_have_value("")
                expect(page.get_by_role("button",name="Собрать предложение")).to_be_visible()
                overflow=page.evaluate("document.documentElement.scrollWidth-document.documentElement.clientWidth")
                if overflow>1:
                    raise AssertionError(f"{name}: horizontal overflow {overflow}px")
                page.screenshot(path=str(SCREENSHOT_DIR/f"{name}.png"),full_page=True)
                page.close()
        finally:
            browser.close()

if __name__=="__main__":
    main()
