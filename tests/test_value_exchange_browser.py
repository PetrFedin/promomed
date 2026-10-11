import os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

BASE=os.environ.get("PROMOMED_BASE_URL","http://127.0.0.1:10000").rstrip("/")
OUT=Path(os.environ.get("PROMOMED_SCREENSHOT_DIR","artifacts/browser-qa"))/"value-exchange"
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            for name,w,h in (("phone",375,667),("tablet",820,1180),("desktop",1440,900)):
                page=browser.new_page(viewport={"width":w,"height":h},locale="ru-RU")
                errors=[]
                page.on("pageerror",lambda e:errors.append(str(e)))
                page.goto(BASE+"/value-exchange.html",wait_until="domcontentloaded")
                expect(page.locator("#route-title")).to_contain_text("От интереса")
                expect(page.locator("#route-steps .stepCard")).to_have_count(3)
                page.locator("#role-partner").click()
                expect(page.locator("#route-title")).to_contain_text("совместный формат")
                expect(page.locator("#role-partner")).to_have_attribute("aria-selected","true")
                expect(page.locator("#route-steps a").first).to_have_attribute("href","/?screen=commercial")
                page.locator("#role-investor").click()
                expect(page.locator("#route-title")).to_contain_text("бизнеса")
                expect(page.locator("#route-steps a").first).to_have_attribute("href","/?presentation=investor")
                page.locator("#role-participant").focus()
                page.keyboard.press("ArrowRight")
                expect(page.locator("#role-partner")).to_have_attribute("aria-selected","true")
                page.locator("#audience").fill("1000")
                page.locator("#reach").fill("40")
                page.locator("#optin").fill("25")
                page.locator("#return").fill("50")
                expect(page.locator("#result-reach")).to_have_text("400")
                expect(page.locator("#result-optin")).to_have_text("100")
                expect(page.locator("#result-return")).to_have_text("50")
                page.locator("#reach").fill("")
                expect(page.locator("#funnel-numbers")).to_be_hidden()
                page.locator("#reach").fill("40")
                expect(page.locator("#funnel-numbers")).to_be_visible()
                expect(page.locator("#runtime-state")).not_to_have_text("Проверяем…",timeout=12000)
                page.screenshot(path=str(OUT/(name+".png")),full_page=True)
                overflow=page.evaluate("document.documentElement.scrollWidth-document.documentElement.clientWidth")
                assert overflow<=1,(name,overflow)
                assert not errors,errors
                page.close()
        finally:browser.close()

if __name__=="__main__":
    main()
