"""Joint stakeholder->partner->organizer evidence path. Demo only, no external writes."""
import os
from pathlib import Path
from playwright.sync_api import expect, sync_playwright

BASE=os.environ.get("PROMOMED_BASE_URL","http://127.0.0.1:10000").rstrip("/")
OUT=Path(os.environ.get("PROMOMED_SCREENSHOT_DIR","artifacts/browser-qa"))/"partner-integration"

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            context=browser.new_context(viewport={"width":1280,"height":800},locale="ru-RU")
            page=context.new_page()
            page.goto(BASE+"/value-exchange.html?audience=partner",wait_until="domcontentloaded")
            expect(page.locator("#role-partner")).to_have_attribute("aria-selected","true")
            expect(page.get_by_role("link",name="Commercial Workspace")).to_have_attribute("href","/institutional-commercial-workspace.html")
            page.get_by_role("link",name="Commercial Workspace").click()
            expect(page.get_by_role("link",name="Открыть Partner Collaboration →")).to_be_visible()
            page.get_by_role("link",name="Открыть Partner Collaboration →").click()
            expect(page.locator("#workspace")).to_be_hidden()
            page.locator("#email").fill("partner@demo.ru")
            page.locator("#password").fill("demo2027")
            page.get_by_role("button",name="Войти").click()
            expect(page.locator("#workspace")).to_be_visible()
            expect(page.locator("#createPanel")).to_be_visible()
            page.locator("#title").fill("Studio pilot QA isolated")
            page.locator("#objective").fill("Demo engagement and governance only; not a signed deal")
            page.locator("#format").select_option("studio")
            page.get_by_role("button",name="Создать черновик").click()
            expect(page.locator("#projectStatus")).to_have_text("draft")
            page.locator("#taskTitle").fill("Prepare partner content for review")
            page.get_by_role("button",name="Добавить задачу").click()
            expect(page.locator("#tasks")).to_contain_text("Prepare partner content")
            page.get_by_role("button",name="Отправить на проверку").click()
            expect(page.locator("#projectStatus")).to_have_text("review_requested")
            page.screenshot(path=str(OUT/"partner-workflow.png"),full_page=True)

            organizer=browser.new_page(viewport={"width":820,"height":1180},locale="ru-RU")
            organizer.goto(BASE+"/partner-collaboration.html")
            organizer.locator("#email").fill("organizer@demo.ru")
            organizer.locator("#password").fill("demo2027")
            organizer.get_by_role("button",name="Войти").click()
            expect(organizer.locator("#projects")).to_contain_text("Studio pilot QA isolated")
            organizer.locator(".projectButton").filter(has_text="Studio pilot QA isolated").click()
            expect(organizer.locator("#projectStatus")).to_have_text("review_requested")
            organizer.get_by_role("button",name="Внутренне проверить").click()
            expect(organizer.locator("#projectStatus")).to_have_text("internally_reviewed")
            expect(organizer.locator("#history")).to_contain_text("status_internally_reviewed")
            organizer.screenshot(path=str(OUT/"organizer-review.png"),full_page=True)

            # Partner now performs an internally reviewed task and submits a
            # reference + synthetic digest, NOT an uploaded artifact.
            page.get_by_role("button",name="Обновить").click()
            page.locator(".projectButton").filter(has_text="Studio pilot QA isolated").click()
            expect(page.locator("#projectStatus")).to_have_text("internally_reviewed")
            own_task=page.locator(".task").filter(has_text="Prepare partner content for review")
            own_task.get_by_role("button",name="Начать исполнение").click()
            expect(own_task).to_contain_text("in_progress")
            own_task.get_by_role("button",name="Передать результат").click()
            own_task.locator(".subform input").nth(0).fill("demo:studio-brief-qa")
            own_task.locator(".subform input").nth(1).fill("a"*64)
            own_task.get_by_role("button",name="Отправить на внутреннюю проверку").click()
            expect(own_task).to_contain_text("submitted")
            page.screenshot(path=str(OUT/"partner-submitted.png"),full_page=True)

            organizer.get_by_role("button",name="Обновить").click()
            organizer.locator(".projectButton").filter(has_text="Studio pilot QA isolated").click()
            review_task=organizer.locator(".task").filter(has_text="Prepare partner content for review")
            expect(review_task).to_contain_text("submitted")
            review_task.get_by_role("button",name="Принять работу").click()
            review_task.locator(".subform textarea").fill("Accepted for INTERNAL demo review only")
            review_task.get_by_role("button",name="Принять внутренний результат").click()
            expect(review_task).to_contain_text("accepted")
            expect(organizer.locator("#receipts")).to_contain_text("accept")
            organizer.screenshot(path=str(OUT/"organizer-accepted-task.png"),full_page=True)

            # Participant never gets partner/organizer work records by any project identifier.
            response=page.request.post(BASE+"/api/login",data={"email":"participant@demo.ru","password":"demo2027"})
            assert response.status==200
            token=response.json()["token"]
            denial=page.request.get(BASE+"/api/partner-collaboration",headers={"Authorization":"Bearer "+token})
            assert denial.status==403,denial.text()
            error=page.request.post(BASE+"/api/partner-collaboration/create",headers={"Authorization":"Bearer "+token},data={"operation_id":"unauthorized-qa","title":"Probe","format":"event"})
            assert error.status==403,error.text()
            # Investor route uses only existing read-only evidence and truth-boundary controls.
            investor=browser.new_page(viewport={"width":375,"height":667},locale="ru-RU")
            investor.goto(BASE+"/value-exchange.html?audience=investor")
            expect(investor.locator("#role-investor")).to_have_attribute("aria-selected","true")
            expect(investor.locator("#route-status")).to_contain_text("EVIDENCE-FIRST")
            expect(investor.locator("#route-guardrail")).to_contain_text("Отсутствуют подтверждённые ARR")
            investor.screenshot(path=str(OUT/"investor-route-mobile.png"),full_page=True)
            for pg in [page,organizer,investor]:
                assert pg.evaluate("document.documentElement.scrollWidth-document.documentElement.clientWidth")<=1
            context.close();organizer.close();investor.close()
        finally:
            browser.close()

if __name__=="__main__":
    main()
