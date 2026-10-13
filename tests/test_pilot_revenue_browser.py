"""Read-only browser proof for the institutional commercial evidence ladder.

CI uses local SQLite demo only. A login rejection must never reveal organization
metadata or accidentally claim payments or contract acceptance.
"""
import os
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = os.environ.get("PROMOMED_BASE_URL", "http://127.0.0.1:10000")
OUT = Path(os.environ.get("PROMOMED_SCREENSHOT_DIR", "artifacts/browser-qa"))
OUT.mkdir(parents=True, exist_ok=True)

DEVICES = [("phone",375,812), ("tablet",820,1180), ("desktop",1440,900)]

def main():
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch()
        try:
            for device,width,height in DEVICES:
                page=browser.new_page(viewport={"width":width,"height":height})
                errors=[]
                page.on("pageerror", lambda exc: errors.append(str(exc)))
                response=page.goto(BASE+"/pilot-revenue-ladder.html",wait_until="domcontentloaded")
                assert response and response.status == 200
                expect(page.get_by_role("heading",name="Семь этапов доказательства")).to_be_visible()
                expect(page.get_by_role("button",name=re.compile("06.*Finance"))).to_be_visible()
                expect(page.locator("#scopedProof")).to_be_hidden()
                assert page.locator(".stage-control").count()==7
                assert page.locator(".stage-control[aria-pressed=true]").count()==1

                page.locator('[data-step="finance"]').click()
                expect(page.locator("#stageTitle")).to_contain_text("Finance acceptance")
                expect(page.locator("#stageBadge")).to_have_text("GATED")
                expect(page.locator("#requiredList li")).to_have_count(4)
                page.locator('[data-step="renewal"]').click()
                expect(page.locator("#stageTitle")).to_contain_text("Repeatable contract")
                expect(page.locator("#stageBadge")).to_have_text("GATED")
                expect(page.locator("#metricRevenue")).to_have_text("—")
                page.locator("#loginEmail").fill("unverified@example.test")
                page.locator("#loginPassword").fill("invalid-only")
                page.locator("#organizationId").fill("UNKNOWN-TENANT")
                page.locator('#proofForm button[type="submit"]').click()
                expect(page.locator("#proofStatus")).to_contain_text(
                    "Не удалось подтвердить доступ"
                )
                expect(page.locator("#scopedProof")).to_be_hidden()
                expect(page.locator("#loginPassword")).to_have_value("")
                page.locator("#logoutButton").click()
                expect(page.locator("#loginEmail")).to_have_value("")
                assert page.locator("#scopedProof").is_hidden()
                dims=page.evaluate("() => ({scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth,window:innerWidth})")
                assert dims["scroll"] <= width+1 and dims["body"] <= width+1, (device,dims)
                page.screenshot(path=str(OUT/f"investor-revenue-ladder-{device}.png"),full_page=True)
                assert not errors, (device,errors)
                page.close()
        finally:
            browser.close()


if __name__=="__main__":
    main()
