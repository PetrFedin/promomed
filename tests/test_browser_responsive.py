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
    sizes = page.locator(".screen.on .small, .screen.on .tiny, .sheet .small, .sheet .tiny").evaluate_all(
        """els => els.filter(e => {
            const s=getComputedStyle(e); const r=e.getBoundingClientRect();
            return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
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
    expect(page.locator("#personalizedContinue")).to_contain_text("YOUR NEXT BEST ACTIONS")
    expect(page.locator("#personalizedContinue")).to_contain_text("Почему это безопасно")
    expect(page.locator("#personalizedContinue")).to_contain_text("medical inference = OFF")
    expect(page.locator("#journey365Timeline")).to_contain_text("Следующий шаг")
    expect(page.locator("#journey365Timeline")).to_contain_text("behavioural relationship journey")
    page.get_by_role("button", name="Поиск").click()
    expect(page.locator("#sheet")).to_contain_text("DISCOVERY & SEARCH AUTHORITY")
    expect(page.locator("#discoveryResults")).to_contain_text("сон")
    page.locator("#discoveryQuery").fill("метабол")
    expect(page.locator("#discoveryResults")).to_contain_text("Метабол")
    expect(page.locator("#discoveryMeta")).to_contain_text("medical inference OFF")
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Медиа").click()
    page.evaluate("show('studio')")
    expect(page.locator("#transcriptIntelligence")).to_contain_text("reviewed takeaways")
    expect(page.locator("#transcriptIntelligence")).to_contain_text("Publication rule")
    page.evaluate("openContent('CT01')")
    page.get_by_role("button", name="Почему этому можно доверять?").click()
    expect(page.locator("#sheet")).to_contain_text("CLAIM EVIDENCE GRAPH")
    expect(page.locator("#sheet")).to_contain_text("VERIFIED_DEMO")
    expect(page.locator("#sheet")).to_contain_text("Exact citations")
    expect(page.locator("#sheet")).to_contain_text("supported_by_segment")
    expect(page.locator("#sheet")).to_contain_text("externally verified publications: NO")
    assert_touch_targets(page, f"{name}/home")
    assert_readable_text(page, f"{name}/home")
    assert_navigation_placement(page, width, height, f"{name}/home")
    page.screenshot(path=str(OUT / f"{clean_name(name)}-home.png"), full_page=True)
    page.keyboard.press("Escape")
    expect(page.locator("#overlay")).not_to_have_class(re.compile(r"\bon\b"))

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
    page.evaluate("""async () => {
      const token = localStorage.getItem('sostoyanie_token');
      const headers={'Content-Type':'application/json','Authorization':'Bearer '+token};
      for (const path of ['/api/deal-room/reset-demo','/api/capital-plan-execution/reset-demo','/api/intervention-engine/reset-demo']) {
        await fetch(path,{method:'POST',headers,body:'{}'});
      }
    }""")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#executiveRoom.on")
    expect(page.locator("#execBoardSummary")).to_contain_text("CONTROLLED PILOT ONLY")
    expect(page.locator("#execProgrammeValue")).to_contain_text("50 000 000")
    expect(page.locator("#execValueBridge")).to_contain_text("Finance")
    expect(page.locator("#execValueBridge")).to_contain_text("Replace fragmented external spend")
    expect(page.locator("#investmentProofDecision")).to_contain_text("CONTROLLED PILOT ONLY")
    expect(page.locator("#investmentProofDecision")).to_contain_text("RELEASE 50M")
    expect(page.locator("#investmentProofTranches")).to_contain_text("50m · Controlled Platform Pilot")
    expect(page.locator("#investmentProofKpis")).to_contain_text("Finance-accepted annualized net value")
    expect(page.locator("#investmentProofLedger")).to_contain_text("TRANCHE DECISION")
    expect(page.locator("#digitalContractAcceptances")).to_contain_text("T50 acceptance")
    expect(page.locator("#digitalContractCertificates")).to_contain_text("LEGAL EFFECT: NONE")
    expect(page.locator("#contractBuilderSummary")).to_contain_text("50m · Controlled Platform Pilot")
    expect(page.locator("#contractPayments")).to_contain_text("Scope + baseline lock")
    expect(page.locator("#contractPayments")).to_contain_text("Production core admission")
    expect(page.locator("#contractEvidenceRoom")).to_contain_text("Finance value reconciliation")
    expect(page.locator("#contractBoardCertificate")).to_contain_text("HOLD")
    expect(page.locator("#contractBoardCertificate")).to_contain_text("LEGAL EFFECT:")
    page.locator('#contractBuilderTabs .chip[data-contract="t75"]').click()
    expect(page.locator("#contractBuilderSummary")).to_contain_text("75m · Operating Health Relationship Platform")
    page.locator('#contractBuilderTabs .chip[data-contract="t100"]').click()
    expect(page.locator("#contractBuilderSummary")).to_contain_text("100m · Strategic Platform Programme")
    expect(page.locator("#dealRoomSummary")).to_contain_text("12 500 000")
    expect(page.locator("#dealRoomSummary")).to_contain_text("4 / 5")
    expect(page.locator("#dealRoomSummary")).to_contain_text("BLOCKED")
    expect(page.locator("#dealRoomIssues")).to_contain_text("Partner acceptance missing")
    expect(page.locator("#dealRoomObligations")).to_contain_text("Partner delivery acceptance")
    expect(page.locator("#dealRoomOwnerInbox")).to_contain_text("Commercial Director")
    expect(page.locator("#dealRoomOwnerInbox")).to_contain_text("3 дн.")
    expect(page.locator("#dealRoomEvidenceRegistry")).to_contain_text("Документов пока нет")
    page.locator("#dealRoomObligations").get_by_role("button", name="Attach + accept demo").click()
    expect(page.locator("#dealRoomSummary")).to_contain_text("5 / 5")
    expect(page.locator("#dealRoomSummary")).to_contain_text("ELIGIBLE_DEMO_PREVIEW")
    expect(page.locator("#dealRoomSummary")).to_contain_text("NOT AUTHORIZED")
    expect(page.locator("#dealRoomEvidenceRegistry")).to_contain_text("REGISTERED DEMO")
    expect(page.locator("#dealRoomIssues")).to_contain_text("RESOLVED DEMO")
    expect(page.locator("#dealRoomBoardPacket")).to_contain_text("GO_TO_FINANCE_REVIEW")
    expect(page.locator("#dealRoomBoardPacket")).to_contain_text("PAYMENT AUTHORITY: NONE")
    page.locator("#dealPaymentRequestBtn").click()
    expect(page.locator("#dealRoomPaymentRequest")).to_contain_text("12 500 000")
    expect(page.locator("#dealRoomPaymentRequest")).to_contain_text("FINANCE REVIEW DEMO")
    expect(page.locator("#dealRoomPaymentRequest")).to_contain_text("PAYMENT AUTHORIZED: NO")
    expect(page.locator("#portfolioCapitalSummary")).to_contain_text("COMMITTED")
    expect(page.locator("#portfolioCapitalSummary")).to_contain_text("75 000 000")
    expect(page.locator("#portfolioCapitalSummary")).to_contain_text("PAID")
    expect(page.locator("#portfolioCapitalSummary")).to_contain_text("10 000 000")
    expect(page.locator("#portfolioCapitalSummary")).to_contain_text("ELIGIBLE")
    expect(page.locator("#portfolioCapitalSummary")).to_contain_text("32 500 000")
    expect(page.locator("#portfolioCapitalSummary")).to_contain_text("BLOCKED")
    expect(page.locator("#portfolioCapitalSummary")).to_contain_text("AT RISK")
    expect(page.locator("#portfolioCapitalSummary")).to_contain_text("0 ₽")
    expect(page.locator("#portfolioCapitalSummary")).to_contain_text("ITERATE")
    expect(page.locator("#portfolioOverdue")).to_contain_text("3 overdue")
    expect(page.locator("#portfolioNextRelease")).to_contain_text("10 000 000")
    expect(page.locator("#portfolioNextRelease")).to_contain_text("Security acceptance")
    expect(page.locator("#portfolioNextRelease")).to_contain_text("PAYMENT AUTHORIZED: NO")
    expect(page.locator("#portfolioForecast")).to_contain_text("T+3 days target")
    expect(page.locator("#capitalOptimizerRecommendation")).to_contain_text("Security / Production")
    expect(page.locator("#capitalOptimizerRecommendation")).to_contain_text("12 500 000")
    expect(page.locator("#capitalOptimizerScenarios")).to_contain_text("DO NOT ALLOCATE INCREMENTAL CAPITAL")
    expect(page.locator("#capitalOptimizerScenarios")).to_contain_text("FUND ONLY WITH APPROVAL WORKPLAN")
    expect(page.locator("#capitalOptimizerMethod")).to_contain_text("risk-adjusted capital unlock")
    expect(page.locator("#capitalPlanSummary")).to_contain_text("10 000 000")
    expect(page.locator("#capitalPlanSummary")).to_contain_text("12 500 000")
    expect(page.locator("#capitalPlanPackages")).to_contain_text("Security baseline & control register")
    expect(page.locator("#capitalPlanPackages")).to_contain_text("Security acceptance & remediation reserve")
    expect(page.locator("#capitalPlanTrajectory")).to_contain_text("STEP 0")
    expect(page.locator("#capitalPlanTrajectory")).to_contain_text("42 500 000")
    expect(page.locator("#capitalPlanRules")).to_contain_text("HOLD")
    expect(page.locator("#capitalExecutionSummary")).to_contain_text("10 000 000")
    expect(page.locator("#capitalExecutionSummary")).to_contain_text("5 500 000")
    expect(page.locator("#capitalExecutionSummary")).to_contain_text("3 270 000")
    expect(page.locator("#capitalExecutionSummary")).to_contain_text("0 ₽")
    expect(page.locator("#interventionSummary")).to_contain_text("RECOVERY_SPRINT")
    expect(page.locator("#interventionSummary")).to_contain_text("ITERATE")
    expect(page.locator("#interventionDiagnostics")).to_contain_text("Durable production & recovery proof")
    expect(page.locator("#interventionDiagnostics")).to_contain_text("HOLD_COMMITMENT")
    expect(page.locator("#interventionLogic")).to_contain_text("does not move money")
    expect(page.locator("#reforecastRecommendation")).to_contain_text("RECOVER_S2_BEFORE_REALLOCATION")
    expect(page.locator("#reforecastScenarios")).to_contain_text("A · Recover S2")
    expect(page.locator("#reforecastScenarios")).to_contain_text("B · Freeze Security downstream")
    expect(page.locator("#reforecastScenarios")).to_contain_text("4 500 000")
    expect(page.locator("#reforecastScenarios")).to_contain_text("NOT_CALCULATED_UNTIL_FINANCE_ACCEPTS_VALUE")
    expect(page.locator("#reforecastApproval")).to_contain_text("AUTOMATIC ACTIONS: NO")
    expect(page.locator("#reallocationApproval")).to_contain_text("NO PROPOSAL")
    page.get_by_role("button", name="Создать proposal").click()
    expect(page.locator("#reallocationApproval")).to_contain_text("4 500 000")
    page.get_by_role("button", name="Finance accept").click()
    page.get_by_role("button", name="Business Owner accept").click()
    page.get_by_role("button", name="IC accept").click()
    expect(page.locator("#reallocationApproval")).to_contain_text("APPROVED DEMO PREVIEW")
    expect(page.locator("#reallocationApproval")).to_contain_text("CAPITAL MOVED: NO")
    expect(page.locator("#capitalExecutionPackages")).to_contain_text("Durable production & recovery proof")
    expect(page.locator("#capitalExecutionPackages")).to_contain_text("IN PROGRESS")
    page.get_by_role("button", name="Принять S2 evidence · demo").click()
    expect(page.locator("#capitalExecutionSummary")).to_contain_text("4 270 000")
    expect(page.locator("#capitalExecutionSummary")).to_contain_text("2 / 4 evidence accepted")
    expect(page.locator("#capitalExecutionSummary")).to_contain_text("0 ₽")
    page.locator("#digitalContractAcceptances").get_by_role("button", name="Demo accept").first.click()
    expect(page.locator("#digitalContractAcceptances")).to_contain_text("ACCEPTED DEMO")
    expect(page.locator("#digitalContractCertificates")).to_contain_text("LEGAL EFFECT: NONE")
    expect(page.locator("#investmentProofDecision")).to_contain_text("RELEASE 50M")
    expect(page.locator("#investmentProofDecision")).to_contain_text("NO")
    assert_no_page_overflow(page, width, f"{name}/presentation-executive")

    page.goto(BASE_URL + "?presentation=security", wait_until="domcontentloaded")
    page.wait_for_selector("#corporateRoom.on")
    expect(page.locator("#corpSummary")).to_contain_text("PRE PRODUCTION SECURITY REVIEW")
    assert_no_page_overflow(page, width, f"{name}/presentation-security")

    # Knowledge change impact must fail-close affected content and recover only after remediation.
    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.evaluate("""async () => {
      const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'editor@demo.ru',password:'demo2027'})});
      const d=await r.json();
      localStorage.setItem('sostoyanie_token',d.token);
      localStorage.setItem('sostoyanie_role',d.role);
      localStorage.setItem('sostoyanie_email','editor@demo.ru');
    }""")
    page.reload(wait_until="domcontentloaded")
    page.evaluate("show('editor')")
    expect(page.locator("#evidenceCoverage")).to_contain_text("75.0%")
    expect(page.locator("#evidenceMonitorDesk")).to_contain_text("CROSSREF")
    expect(page.locator("#evidenceMonitorDesk")).to_contain_text("SHA-256")
    page.get_by_role("button", name="DEMO · provider retraction snapshot").click()
    pending=page.locator("#evidenceMonitorDesk .card").filter(has_text="SOURCE_RETRACTED").first
    expect(pending).to_contain_text("PENDING REVIEW")
    pending.get_by_role("button", name="Editorial accept").click()
    pending=page.locator("#evidenceMonitorDesk .card").filter(has_text="SOURCE_RETRACTED").first
    pending.get_by_role("button", name="Scientific accept").click()
    pending=page.locator("#evidenceMonitorDesk .card").filter(has_text="SOURCE_RETRACTED").first
    expect(pending).to_contain_text("REVIEW READY")
    pending.get_by_role("button", name="Admit").click()
    expect(page.locator("#changeImpactControl")).to_contain_text("SOURCE_RETRACTED")
    expect(page.locator("#changeImpactControl")).to_contain_text("PUBLICATION HOLD")
    expect(page.locator("#evidenceMonitorDesk")).to_contain_text("ADMITTED DEMO")
    page.evaluate("openContent('CT01')")
    expect(page.locator("#sheet")).to_contain_text("UNDER REVIEW · PUBLICATION HOLD")
    page.keyboard.press("Escape")
    page.get_by_role("button", name="DEMO · retract affected claim").click()
    page.get_by_role("button", name="Review + release hold").click()
    expect(page.locator("#changeImpactControl")).not_to_contain_text("PUBLICATION HOLD:")
    # Return shared demo authority to a deterministic baseline for the next viewport.
    page.evaluate("""async () => {
      const lr=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'organizer@demo.ru',password:'demo2027'})});
      const ld=await lr.json();
      await fetch('/api/demo/reset',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+ld.token},body:'{}'});
    }""")

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
