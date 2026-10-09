import os
from pathlib import Path
from playwright.sync_api import expect, sync_playwright

BASE_URL=os.environ.get("PROMOMED_BASE_URL","http://127.0.0.1:10000").rstrip("/")
SCREENSHOT_DIR=Path(os.environ.get("PROMOMED_SCREENSHOT_DIR","artifacts/browser-qa"))/"institutional-accessibility"
PAGES=(
    ("workspace","/institutional-commercial-workspace.html"),
    ("buyer-fit","/institutional-buyer-fit.html"),
    ("proposal","/institutional-pilot-proposal.html"),
    ("outreach","/institutional-outreach-pack.html"),
    ("export","/institutional-evidence-export.html"),
    ("command","/institutional-command-center.html"),
)

def main():
    SCREENSHOT_DIR.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch()
        try:
            for key,path in PAGES:
                page=browser.new_page(viewport={"width":1440,"height":900},reduced_motion="reduce")
                page.goto(BASE_URL+path,wait_until="networkidle")
                skip=page.get_by_role("link",name="Перейти к основному содержанию")
                expect(skip).to_be_attached()
                page.keyboard.press("Tab")
                expect(skip).to_be_focused()
                page.keyboard.press("Enter")
                expect(page.locator("#main-content")).to_be_focused()
                expect(page.get_by_role("navigation",name="Institutional commercial navigation")).to_be_visible()
                overflow=page.evaluate("document.documentElement.scrollWidth-document.documentElement.clientWidth")
                if overflow>1:
                    raise AssertionError(f"{key}: horizontal overflow {overflow}px")
                page.screenshot(path=str(SCREENSHOT_DIR/f"{key}.png"),full_page=True)
                page.close()
        finally:
            browser.close()

if __name__=="__main__":
    main()
