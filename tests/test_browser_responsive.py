import os
import re
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

BASE_URL = os.environ.get("PROMOMED_BASE_URL", "http://127.0.0.1:10000")
OUT = Path(os.environ.get("PROMOMED_SCREENSHOT_DIR", "artifacts/browser-qa"))
OUT.mkdir(parents=True, exist_ok=True)

VIEWPORTS = [
    ("iphone-se", 375, 667, True, True),
    ("iphone-15-pro", 393, 852, True, True),
    ("iphone-15-pro-landscape", 852, 393, True, True),
    ("ipad-air", 820, 1180, False, True),
    ("ipad-air-landscape", 1180, 820, False, True),
    ("desktop", 1440, 900, False, False),
    ("desktop-wide", 1728, 1117, False, False),
]


def clean_name(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")


def assert_no_page_overflow(page, width: int, label: str):
    metrics = page.evaluate(
        """() => ({
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
          bodyWidth: document.body.scrollWidth
        })"""
    )
    assert metrics["scrollWidth"] <= width + 1, f"{label}: html overflow {metrics}"
    assert metrics["bodyWidth"] <= width + 1, f"{label}: body overflow {metrics}"


def assert_touch_targets(page, label: str):
    for selector in [".topActions .icon", ".nav button"]:
        boxes = page.locator(selector).evaluate_all(
            """els => els.filter(e => getComputedStyle(e).display !== 'none')
                         .map(e => { const r=e.getBoundingClientRect(); return {w:r.width,h:r.height,text:e.innerText}; })"""
        )
        assert boxes, f"{label}: no visible controls for {selector}"
        for box in boxes:
            assert box["h"] >= 44, f"{label}: touch target too short {selector} {box}"
            assert box["w"] >= 44, f"{label}: touch target too narrow {selector} {box}"


def assert_readable_text(page, label: str):
    sizes = page.locator("#today.on .small, #today.on .tiny").evaluate_all(
        """els => els.filter(e => {
            const s=getComputedStyle(e); const r=e.getBoundingClientRect();
            return s.display !== 'none' && r.width > 0 && r.height > 0;
          }).slice(0,30).map(e => parseFloat(getComputedStyle(e).fontSize))"""
    )
    assert sizes, f"{label}: no readable sample text"
    assert min(sizes) >= 11, f"{label}: text below 11px: {min(sizes)}"


def assert_navigation_placement(page, width: int, height: int, label: str):
    nav = page.locator("#nav").bounding_box()
    top = page.locator(".top").bounding_box()
    assert nav and top, f"{label}: navigation/header missing"
    if width >= 1024:
        assert nav["y"] <= 32, f"{label}: desktop nav not promoted to top: {nav}"
        assert nav["y"] + nav["height"] <= top["y"] + 2, f"{label}: desktop nav overlaps header: nav={nav}, top={top}"
    else:
        assert nav["y"] + nav["height"] >= height - 3, f"{label}: mobile/tablet nav not anchored to bottom: {nav}"


def assert_sheet_within_viewport(page, height: int, label: str):
    sheet = page.locator("#sheet").bounding_box()
    assert sheet, f"{label}: sheet missing"
    assert sheet["y"] >= -1, f"{label}: sheet starts above viewport: {sheet}"
    assert sheet["height"] <= height + 1, f"{label}: sheet taller than viewport: {sheet}"


def run_device(browser, name: str, width: int, height: int, is_mobile: bool, has_touch: bool):
    context = browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=2 if is_mobile or has_touch else 1,
        is_mobile=is_mobile,
        has_touch=has_touch,
        locale="ru-RU",
    )
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.wait_for_selector("#today.on")
    expect(page.locator("#overlay")).not_to_have_class(re.compile(r"\bon\b"))
    expect(page.locator("#today")).to_have_class(re.compile(r"\bon\b"))
    expect(page.locator("#nav")).to_contain_text("Главная")
    expect(page.locator("#today h1").first).to_contain_text("Знать больше")
    expect(page.locator("#roleTag")).to_have_class(re.compile(r"\bhidden\b"))
    expect(page.locator("#proofDock")).to_be_hidden()
    expect(page.locator("#goldenDemoLauncher")).to_be_hidden()
    assert_no_page_overflow(page, width, f"{name}/home")
    assert_touch_targets(page, f"{name}/home")
    assert_readable_text(page, f"{name}/home")
    assert_navigation_placement(page, width, height, f"{name}/home")
    page.screenshot(path=str(OUT / f"{clean_name(name)}-home.png"), full_page=True)

    for screen_id in ["media", "events", "community"]:
        page.locator(f'#nav button[data-s="{screen_id}"]').click()
        page.wait_for_selector(f"#{screen_id}.on")
        assert_no_page_overflow(page, width, f"{name}/{screen_id}")

    # Account is the boundary: guest browsing remains open, personal data asks for login.
    page.locator('#nav button[data-s="me"]').click()
    expect(page.locator("#overlay")).to_have_class(re.compile(r"\bon\b"))
    expect(page.locator("#sheet")).to_contain_text("Настоящие demo-роли")
    assert_sheet_within_viewport(page, height, f"{name}/login-sheet")
    page.locator("#sheet .card").filter(has_text="Участник").get_by_role("button", name="Войти").click()
    expect(page.locator("#overlay")).to_be_hidden()
    page.locator('#nav button[data-s="me"]').click()
    page.wait_for_selector("#me.on")
    expect(page.locator("#me")).to_contain_text("Сообщения")
    expect(page.locator("#accountInbox")).to_be_visible()
    assert_no_page_overflow(page, width, f"{name}/account")
    page.screenshot(path=str(OUT / f"{clean_name(name)}-account.png"), full_page=True)

    # Organizer conversation is always available to an authenticated participant.
    page.get_by_role("button", name="Написать организатору", exact=True).click()
    page.wait_for_selector("#directMessageInput")
    text = f"Browser QA {name}"
    page.locator("#directMessageInput").fill(text)
    page.get_by_role("button", name="Отправить", exact=True).click()
    expect(page.locator("#sheet")).to_contain_text(text)

    # A random participant must still be blocked until a mutual meeting is confirmed.
    status = page.evaluate(
        """async () => {
          const token = localStorage.getItem('sostoyanie_token');
          const r = await fetch('/api/direct-message', {
            method:'POST',
            headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},
            body:JSON.stringify({recipient:'participant2@demo.ru',context:'browser_qa',body:'blocked probe'})
          });
          return r.status;
        }"""
    )
    assert status == 403, f"{name}: unconfirmed participant DM returned {status}"

    # Investor readiness proof must render as a real responsive product surface.
    page.evaluate("() => showInvestorProof()")
    page.wait_for_selector("#investorProof.on")
    expect(page.locator("#investorRuntime")).to_contain_text("Backend")
    expect(page.locator("#investorRuntime")).to_contain_text("Production ready")
    assert page.locator("#investorCapabilities .investorCapability").count() >= 8
    expect(page.locator("#investorThesis")).to_contain_text("event operating system")
    assert page.locator("#investorMilestones .investorMilestone").count() >= 5
    expect(page.locator("#committeeState")).to_contain_text("PILOT DILIGENCE READY")
    assert page.locator("#diligenceGrid .diligenceCard").count() >= 7
    assert page.locator("#investorRisks .riskRow").count() >= 5
    assert page.locator("#investorScalePaths .scalePath").count() >= 5
    page.locator("#econPlatform").fill("1000000")
    page.locator("#econEvents").fill("2")
    page.locator("#econEventFee").fill("500000")
    expect(page.locator("#investorEconomicsOutput")).to_contain_text(re.compile(r"2\s*000\s*000"))
    expect(page.locator("#investorEconomicsOutput")).to_contain_text("MAX REVENUE-LINE CONCENTRATION")
    # Finance-input value lab: 75m investment and 75m annual net verified value -> 12 month payback.
    page.locator("#valueInvestment").fill("75000000")
    page.locator("#valueAvoided").fill("30000000")
    page.locator("#valuePartner").fill("30000000")
    page.locator("#valueOps").fill("20000000")
    page.locator("#valueRunCost").fill("5000000")
    expect(page.locator("#verifiedValueOutput")).to_contain_text(re.compile(r"75\s*000\s*000"))
    expect(page.locator("#verifiedValueOutput")).to_contain_text("12.0 мес.")
    page.locator("#valueReuse").fill("10000000")
    page.locator("#valueAudience").fill("0")
    expect(page.locator("#verifiedValueOutput")).to_contain_text(re.compile(r"85\s*000\s*000"))
    expect(page.locator("#valueCaptureMap")).to_contain_text("Replace fragmented external spend")
    expect(page.locator("#valueEvidenceProtocol")).to_contain_text("LOCK BASELINE")
    assert_no_page_overflow(page, width, f"{name}/investor")
    page.screenshot(path=str(OUT / f"{clean_name(name)}-investor.png"), full_page=True)

    # Executive / CVC decision room must remain responsive and fail-closed.
    page.evaluate("() => showExecutiveRoom()")
    page.wait_for_selector("#executiveRoom.on")
    expect(page.locator("#execBoardSummary")).to_contain_text("CONTROLLED PILOT ONLY")
    assert page.locator("#execModeTabs .execModeTab").count() == 4
    assert page.locator("#execTranches .execTranche").count() == 4
    assert page.locator("#execKpis .execKpi").count() >= 7
    assert page.locator("#execReadiness .execReadiness").count() >= 7
    assert page.locator("#execDataRoom .execDataRoom").count() >= 6
    expect(page.locator("#execTruth")).to_contain_text("PRODUCTION READY")
    expect(page.locator("#execTruth")).to_contain_text("MARKET TRACTION")
    expect(page.locator("#execTruth")).to_contain_text("NO")
    page.locator('#execModeTabs .execModeTab[data-mode="procurement"]').click()
    expect(page.locator("#execModeHero")).to_contain_text("Procurement / Security")
    assert_no_page_overflow(page, width, f"{name}/executive")
    page.screenshot(path=str(OUT / f"{clean_name(name)}-executive.png"), full_page=True)

    # Corporate security/procurement room must remain responsive and truth-labeled.
    page.evaluate("() => showCorporateRoom()")
    page.wait_for_selector("#corporateRoom.on")
    expect(page.locator("#corpSummary")).to_contain_text("PRE PRODUCTION SECURITY REVIEW")
    assert page.locator("#corpControls .corpControl").count() >= 17
    assert page.locator("#corpDataInventory .corpData").count() >= 6
    assert page.locator("#corpVendorQuestions .corpQuestion").count() >= 7
    assert page.locator("#corpProcurement .corpGate").count() >= 6
    assert page.locator("#corpFrameworks .corpControl").count() >= 7
    expect(page.locator("#corpTruth")).to_contain_text("SECURITY CERTIFICATION")
    expect(page.locator("#corpTruth")).to_contain_text("APPROVED RTO/RPO")
    expect(page.locator("#corpTruth")).to_contain_text("APPROVED DPA/SLA")
    expect(page.locator("#corpTruth")).to_contain_text("NO")
    assert_no_page_overflow(page, width, f"{name}/corporate")
    page.screenshot(path=str(OUT / f"{clean_name(name)}-corporate.png"), full_page=True)

    # Shareable investor entrypoints must work directly from a fresh URL on every viewport.
    page.goto(BASE_URL + "?presentation=menu", wait_until="domcontentloaded")
    page.wait_for_selector("#overlay.on")
    expect(page.locator("#sheet")).to_contain_text("INVESTOR PRESENTATION MODE")
    expect(page.locator("#sheet")).to_contain_text("Golden Demo")
    expect(page.locator("#presentationLauncher")).to_be_visible()
    assert_sheet_within_viewport(page, height, f"{name}/presentation-menu")
    assert_no_page_overflow(page, width, f"{name}/presentation-menu")

    page.goto(BASE_URL + "?presentation=executive", wait_until="domcontentloaded")
    page.wait_for_selector("#executiveRoom.on")
    expect(page.locator("#execBoardSummary")).to_contain_text("CONTROLLED PILOT ONLY")
    expect(page.locator("#execProgrammeValue")).to_contain_text("50 000 000")
    expect(page.locator("#execValueBridge")).to_contain_text("Finance")
    expect(page.locator("#execValueBridge")).to_contain_text("Replace fragmented external spend")
    assert_no_page_overflow(page, width, f"{name}/presentation-executive")

    page.goto(BASE_URL + "?presentation=security", wait_until="domcontentloaded")
    page.wait_for_selector("#corporateRoom.on")
    expect(page.locator("#corpSummary")).to_contain_text("PRE PRODUCTION SECURITY REVIEW")
    assert_no_page_overflow(page, width, f"{name}/presentation-security")

    assert not errors, f"{name}: page errors: {errors}"
    context.close()


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for args in VIEWPORTS:
                run_device(browser, *args)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
