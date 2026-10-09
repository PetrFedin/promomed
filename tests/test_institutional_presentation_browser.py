import os
from pathlib import Path
from playwright.sync_api import expect, sync_playwright

BASE_URL=os.environ.get("PROMOMED_BASE_URL","http://127.0.0.1:10000").rstrip("/")
SCREENSHOT_DIR=Path(os.environ.get("PROMOMED_SCREENSHOT_DIR","artifacts/browser-qa"))/"institutional-shell"
PAGES=(
    ("workspace","/institutional-commercial-workspace.html","Workspace"),
    ("buyer-fit","/institutional-buyer-fit.html","Buyer Fit"),
    ("proposal","/institutional-pilot-proposal.html","Proposal"),
    ("outreach","/institutional-outreach-pack.html","Outreach"),
    ("export","/institutional-evidence-export.html","Export"),
    ("command","/institutional-command-center.html","Command Center"),
)
VIEWPORTS=(("iphone",390,844),("tablet",820,1180),("desktop",1440,900))

def main():
    SCREENSHOT_DIR.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch()
        try:
            for viewport,width,height in VIEWPORTS:
                for key,path,label in PAGES:
                    page=browser.new_page(viewport={"width":width,"height":height})
                    page.goto(BASE_URL+path,wait_until="networkidle")
                    nav=page.get_by_role("navigation",name="Institutional commercial navigation")
                    expect(nav).to_be_visible()
                    expect(nav.get_by_role("link",name=label)).to_have_attribute("aria-current","page")
                    expect(page.get_by_text("Planning ≠ customer truth")).to_be_visible()
                    expect(page.get_by_role("link",name="Workspace")).to_be_visible()
                    overflow=page.evaluate("document.documentElement.scrollWidth-document.documentElement.clientWidth")
                    if overflow>1:
                        raise AssertionError(f"{viewport}/{key}: horizontal overflow {overflow}px")
                    page.screenshot(path=str(SCREENSHOT_DIR/f"{viewport}-{key}.png"),full_page=True)
                    page.close()
        finally:
            browser.close()

if __name__=="__main__":
    main()
