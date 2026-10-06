import os
import re
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
SERVER = (ROOT / "server.py").read_text(encoding="utf-8")
COMMUNITY_COMMANDS = (ROOT / "app" / "community_commands.py").read_text(encoding="utf-8")


class UIContractTests(unittest.TestCase):
    def test_guest_lands_on_home_without_forced_login(self):
        self.assertIn("else{role='participant';show('today');updateTag();await syncState(true)}", INDEX)
        self.assertNotIn("else if(!apiToken){openSheet('login')}", INDEX)
        self.assertNotIn("await switchRole(r);setInterval", INDEX)
        self.assertIn("<b>⌂</b>Главная", INDEX)

    def test_account_inbox_is_consent_first(self):
        self.assertIn('id="accountInbox"', INDEX)
        self.assertIn("function openConversation", INDEX)
        self.assertIn('"/api/direct-message"', COMMUNITY_COMMANDS)
        self.assertIn("conversation_requires_mutual_consent", COMMUNITY_COMMANDS)
        self.assertIn("mutual_meetings", COMMUNITY_COMMANDS)
        self.assertIn("SELECT email,role,name,status FROM accounts", COMMUNITY_COMMANDS)
        self.assertIn('recipient_account["role"] == "organizer"', COMMUNITY_COMMANDS)

    def test_responsive_breakpoints_and_touch_targets_exist(self):
        self.assertIn("@media(max-width:379px)", INDEX)
        self.assertIn("@media(min-width:640px) and (max-width:1023px)", INDEX)
        self.assertIn("@media(min-width:1024px)", INDEX)
        self.assertIn(".icon{min-width:44px;min-height:44px}", INDEX)
        self.assertIn("viewport-fit=cover", INDEX)
        self.assertIn("env(safe-area-inset-bottom)", INDEX)
        self.assertIn("100dvh", INDEX)
        self.assertIn("@media(max-height:520px) and (orientation:landscape)", INDEX)
        self.assertIn("@media(min-width:1440px)", INDEX)
        self.assertIn('role="dialog" aria-modal="true"', INDEX)
        self.assertIn('rel="manifest" href="/manifest.webmanifest"', INDEX)
        self.assertIn('apple-mobile-web-app-capable" content="yes"', INDEX)
        self.assertIn(":focus-visible", INDEX)
        self.assertIn("@media(prefers-reduced-motion:reduce)", INDEX)
        self.assertIn("@media(display-mode:standalone)", INDEX)

    def test_investor_readiness_is_evidence_labeled(self):
        self.assertIn('id="investorRuntime"', INDEX)
        self.assertIn('id="investorCapabilities"', INDEX)
        self.assertIn('id="investorRevenue"', INDEX)
        self.assertIn('id="investorMoat"', INDEX)
        self.assertIn('id="investorThesis"', INDEX)
        self.assertIn('id="investorMilestones"', INDEX)
        self.assertIn('id="committeeState"', INDEX)
        self.assertIn('id="diligenceGrid"', INDEX)
        self.assertIn('id="investorRisks"', INDEX)
        self.assertIn('id="investorScalePaths"', INDEX)
        self.assertIn("async function loadInvestorReadiness()", INDEX)
        self.assertIn("CI-PROVEN", INDEX)
        self.assertIn("REVENUE ARCHITECTURE · WITHOUT FICTION", INDEX)
        self.assertIn("DEFENSIBILITY · WHY THIS IS NOT JUST AN EVENT APP", INDEX)
        self.assertIn("SCENARIO ECONOMICS LAB · USER INPUT ONLY", INDEX)
        self.assertIn("function calcInvestorScenario()", INDEX)
        self.assertIn("Revenue = platform fee + events × event fee", INDEX)
        self.assertIn("Scenario only · значения не сохраняются и не являются прогнозом.", INDEX)
        self.assertIn("INVESTMENT COMMITTEE ROOM · DILIGENCE BEFORE STORYTELLING", INDEX)
        self.assertIn("RISK REGISTER · EXPLICIT, NOT HIDDEN", INDEX)
        self.assertIn("SCALE PATHS · OPTION VALUE AFTER PROOF", INDEX)
        self.assertNotIn("COMMERCIAL SCENARIO BUILDER · INPUTS, NOT FORECAST", INDEX)
        self.assertEqual(INDEX.count("function calcInvestorScenario()"), 1)

    def test_executive_cvc_room_is_decision_oriented(self):
        self.assertIn('id="executiveRoom"', INDEX)
        self.assertIn('id="execModeTabs"', INDEX)
        self.assertIn('id="execBoardSummary"', INDEX)
        self.assertIn('id="execTranches"', INDEX)
        self.assertIn('id="execKpis"', INDEX)
        self.assertIn('id="execReadiness"', INDEX)
        self.assertIn('id="execDataRoom"', INDEX)
        self.assertIn('id="execTruth"', INDEX)
        self.assertIn("async function showExecutiveRoom()", INDEX)
        self.assertIn("EXECUTIVE / CVC DECISION ROOM", INDEX)
        self.assertIn("MILESTONE FUNDING · RELEASE CAPITAL AGAINST EVIDENCE", INDEX)
        self.assertIn("PILOT KPI DICTIONARY · FORMULA BEFORE TARGET", INDEX)
        self.assertIn("CORPORATE READINESS · PROCUREMENT / SECURITY VIEW", INDEX)
        self.assertIn("STRATEGIC PARTNER VALUE EXCHANGE", INDEX)
        self.assertIn("DUE-DILIGENCE DATA ROOM · INDEX", INDEX)
        self.assertNotIn("Guaranteed commercial uplift", INDEX)
        self.assertIn("PROGRAMME VALUE CASE · 50–100M ₽", INDEX)
        self.assertIn("FORMULA · NOT FORECAST", INDEX)
        self.assertIn("BOARD VALUE BRIDGE · FROM CAPITAL TO ACCEPTED VALUE", INDEX)
        self.assertIn('id="execValueBridge"', INDEX)
        self.assertIn("INVESTMENT PROOF SYSTEM · TRANCHE CONTROL", INDEX)
        self.assertIn('id="investmentProofDecision"', INDEX)
        self.assertIn('id="investmentProofTranches"', INDEX)
        self.assertIn('id="investmentProofKpis"', INDEX)
        self.assertIn('id="investmentProofLedger"', INDEX)
        self.assertIn("async function loadInvestmentProofSystem()", INDEX)
        self.assertIn("DIGITAL INVESTMENT CONTRACT · DEMO ACCEPTANCE", INDEX)
        self.assertIn('id="digitalContractAcceptances"', INDEX)
        self.assertIn('id="digitalContractCertificates"', INDEX)
        self.assertIn("async function acceptDemoRequirement(", INDEX)
        self.assertIn("LEGAL EFFECT:", INDEX)
        self.assertIn("not an electronic signature", INDEX)
        self.assertIn("CONTRACT BUILDER · SCOPE → PAYMENT → EVIDENCE → BOARD", INDEX)
        self.assertIn('id="contractBuilderTabs"', INDEX)
        self.assertIn('id="contractBuilderSummary"', INDEX)
        self.assertIn('id="contractScope"', INDEX)
        self.assertIn('id="contractAcceptance"', INDEX)
        self.assertIn('id="contractPayments"', INDEX)
        self.assertIn('id="contractEvidenceRoom"', INDEX)
        self.assertIn('id="contractBoardCertificate"', INDEX)
        self.assertIn("async function loadContractBuilder()", INDEX)
        self.assertIn("function renderContractPackage(", INDEX)
        self.assertIn("not a commercial quote", INDEX.lower())
        self.assertIn("PILOT DEAL ROOM · OBLIGATION → EVIDENCE → REMEDIATION → PAYMENT", INDEX)
        self.assertIn('id="dealRoomSummary"', INDEX)
        self.assertIn('id="dealRoomObligations"', INDEX)
        self.assertIn('id="dealRoomIssues"', INDEX)
        self.assertIn('id="dealRoomBoardPacket"', INDEX)
        self.assertIn("async function loadDealRoom()", INDEX)
        self.assertIn("async function acceptDealObligation(", INDEX)
        self.assertIn("PAYMENT AUTHORITY:", INDEX)
        self.assertIn('id="dealRoomOwnerInbox"', INDEX)
        self.assertIn('id="dealRoomEvidenceRegistry"', INDEX)
        self.assertIn('id="dealRoomPaymentRequest"', INDEX)
        self.assertIn("async function createDealPaymentRequest()", INDEX)
        self.assertIn("function exportDealBoardPacket()", INDEX)
        self.assertIn("OWNER INBOX · SLA", INDEX)
        self.assertIn("EVIDENCE DOCUMENT REGISTRY", INDEX)
        self.assertIn("FINANCE PAYMENT REQUEST", INDEX)
        self.assertIn("PORTFOLIO CAPITAL CONTROL · CEO / CFO VIEW", INDEX)
        self.assertIn('id="portfolioCapitalSummary"', INDEX)
        self.assertIn('id="portfolioWorkstreams"', INDEX)
        self.assertIn('id="portfolioOverdue"', INDEX)
        self.assertIn('id="portfolioForecast"', INDEX)
        self.assertIn('id="portfolioNextRelease"', INDEX)
        self.assertIn('id="portfolioControlRules"', INDEX)
        self.assertIn("async function loadPortfolioCapitalControl()", INDEX)
        self.assertIn("CAPITAL ALLOCATION OPTIMIZER · NEXT 10M ₽", INDEX)
        self.assertIn('id="capitalOptimizerRecommendation"', INDEX)
        self.assertIn('id="capitalOptimizerScenarios"', INDEX)
        self.assertIn('id="capitalOptimizerMethod"', INDEX)
        self.assertIn("async function loadCapitalOptimizer()", INDEX)
        self.assertIn("EXECUTABLE CAPITAL ALLOCATION PLAN · SECURITY 10M ₽", INDEX)
        self.assertIn('id="capitalPlanSummary"', INDEX)
        self.assertIn('id="capitalPlanPackages"', INDEX)
        self.assertIn('id="capitalPlanTrajectory"', INDEX)
        self.assertIn('id="capitalPlanRules"', INDEX)
        self.assertIn("async function loadCapitalAllocationPlan()", INDEX)
        self.assertIn("CAPITAL PLAN EXECUTION AUTHORITY · PLAN → COMMIT → ACTUAL → VALUE", INDEX)
        self.assertIn('id="capitalExecutionSummary"', INDEX)
        self.assertIn('id="capitalExecutionPackages"', INDEX)
        self.assertIn('id="capitalExecutionVariance"', INDEX)
        self.assertIn("async function loadCapitalExecution()", INDEX)
        self.assertIn("async function advanceCapitalExecutionDemo()", INDEX)
        self.assertIn("FORECAST VARIANCE · INTERVENTION ENGINE", INDEX)
        self.assertIn('id="interventionSummary"', INDEX)
        self.assertIn('id="interventionDiagnostics"', INDEX)
        self.assertIn('id="interventionLogic"', INDEX)
        self.assertIn("async function loadInterventionEngine()", INDEX)
        self.assertIn("async function createPrimaryIntervention()", INDEX)
        self.assertIn("CAPITAL RECOVERY & REALLOCATION COCKPIT", INDEX)
        self.assertIn('id="reforecastRecommendation"', INDEX)
        self.assertIn('id="reforecastScenarios"', INDEX)
        self.assertIn('id="reforecastApproval"', INDEX)
        self.assertIn("async function loadRecoveryReforecast()", INDEX)
        self.assertIn("REALLOCATION APPROVAL AUTHORITY · DEMO", INDEX)
        self.assertIn('id="reallocationApproval"', INDEX)
        self.assertIn("async function loadReallocationApproval()", INDEX)
        self.assertIn("CONTINUE JOURNEY · PERSONAL", INDEX)
        self.assertIn('id="personalizedContinue"', INDEX)
        self.assertIn("function renderPersonalizedJourney(", INDEX)
        self.assertIn("function openPersonalizedTarget(", INDEX)
        self.assertIn("medical inference", INDEX.lower())
        self.assertIn("RELATIONSHIP 365", INDEX)
        self.assertIn("DISCOVERY & SEARCH AUTHORITY", INDEX)
        self.assertIn("TRANSCRIPT INTELLIGENCE · EVIDENCE-FIRST", INDEX)
        self.assertIn("CLAIM EVIDENCE GRAPH", INDEX)
        self.assertIn("Почему этому можно доверять?", INDEX)
        self.assertIn("async function openEvidenceGraph(", INDEX)
        self.assertIn("function renderEvidenceGraphSheet(", INDEX)
        self.assertIn("EVIDENCE COVERAGE · EDITOR QUEUE", INDEX)
        self.assertIn("KNOWLEDGE CHANGE IMPACT · CONTROL", INDEX)
        self.assertIn('id="changeImpactControl"', INDEX)
        self.assertIn("async function createDemoSourceChange()", INDEX)
        self.assertIn("async function remediateLatestChange()", INDEX)
        self.assertIn("async function resolveLatestChange(", INDEX)
        self.assertIn("UNDER REVIEW · PUBLICATION HOLD", INDEX)
        self.assertIn('id="evidenceCoverage"', INDEX)
        self.assertIn("async function loadEvidenceCoverage()", INDEX)
        self.assertIn('id="transcriptIntelligence"', INDEX)
        self.assertIn("async function loadTranscriptIntelligence(", INDEX)
        self.assertIn("function renderTranscriptIntelligence(", INDEX)
        self.assertIn('id="discoveryQuery"', INDEX)
        self.assertIn('id="discoveryResults"', INDEX)
        self.assertIn("function runDiscoverySearch()", INDEX)
        self.assertIn("function toggleDiscoverySave(", INDEX)
        self.assertIn('id="journey365Timeline"', INDEX)
        self.assertIn("function renderJourney365(", INDEX)
        self.assertIn("function openJourney365Action(", INDEX)
        self.assertIn("async function acceptReallocationRole(", INDEX)

    def test_corporate_security_room_is_truth_labeled(self):
        self.assertIn('id="corporateRoom"', INDEX)
        self.assertIn('id="corpSummary"', INDEX)
        self.assertIn('id="corpTruth"', INDEX)
        self.assertIn('id="corpControls"', INDEX)
        self.assertIn('id="corpDataInventory"', INDEX)
        self.assertIn('id="corpPrivacy"', INDEX)
        self.assertIn('id="corpVendorQuestions"', INDEX)
        self.assertIn('id="corpProcurement"', INDEX)
        self.assertIn('id="corpFrameworks"', INDEX)
        self.assertIn("async function showCorporateRoom()", INDEX)
        self.assertIn("CORPORATE SECURITY / PROCUREMENT ROOM", INDEX)
        self.assertIn("CONTROL MATRIX · EVIDENCE BACKED", INDEX)
        self.assertIn("DATA INVENTORY · BEFORE REAL DATA", INDEX)
        self.assertIn("VENDOR QUESTIONNAIRE · FIRST ANSWERS", INDEX)
        self.assertIn("PROCUREMENT GATES", INDEX)
        self.assertIn("FRAMEWORK CROSSWALK · REFERENCE, NOT CERTIFICATION", INDEX)
        self.assertIn("This is an evidence-backed readiness pack, not a security certification.", (ROOT / "app" / "corporate.py").read_text(encoding="utf-8"))

    def test_investor_value_case_is_visible_and_truth_labeled(self):
        self.assertIn("50–100M ₽ VALUE CASE · WHAT THE COMPANY ACTUALLY BUYS", INDEX)
        self.assertIn('id="valueCompanyContext"', INDEX)
        self.assertIn('id="valueEnvelopes"', INDEX)
        self.assertIn('id="valuePaybackTable"', INDEX)
        self.assertIn('id="valueLevers"', INDEX)
        self.assertIn('id="valueTruthBoundary"', INDEX)
        self.assertIn("FORMULA · NOT FORECAST", INDEX)
        self.assertIn("Быстрая окупаемость должна быть доказана, а не нарисована.", INDEX)
        self.assertIn('id="valueInvestment"', INDEX)
        self.assertIn('id="valueAvoided"', INDEX)
        self.assertIn('id="valuePartner"', INDEX)
        self.assertIn('id="valueOps"', INDEX)
        self.assertIn('id="valueRunCost"', INDEX)
        self.assertIn('id="verifiedValueOutput"', INDEX)
        self.assertIn("function calcVerifiedValue()", INDEX)
        self.assertIn("No double counting.", INDEX)
        self.assertIn('id="valueCaptureMap"', INDEX)
        self.assertIn('id="valueEvidenceProtocol"', INDEX)
        self.assertIn('id="valueReuse"', INDEX)
        self.assertIn('id="valueAudience"', INDEX)
        self.assertIn("OWNER → BASELINE → FORMULA → PROOF", INDEX)

    def test_investor_presentation_mode_is_shareable_and_reset_safe(self):
        self.assertIn('id="presentationLauncher"', INDEX)
        self.assertIn("const presentationModes=new Set(['menu','golden','owner','investor','executive','security'])", INDEX)
        self.assertIn("function applyPresentationDeepLink()", INDEX)
        self.assertIn("new URLSearchParams(location.search).get('presentation')", INDEX)
        self.assertIn("if(mode==='golden')return guidedStart()", INDEX)
        self.assertIn("if(mode==='owner'){await goldenLogin();await api('/api/demo/reset'", INDEX)
        self.assertIn("if(mode==='investor')return showInvestorProof()", INDEX)
        self.assertIn("if(mode==='executive')return showExecutiveRoom()", INDEX)
        self.assertIn("if(mode==='security')return showCorporateRoom()", INDEX)
        self.assertIn("Truth boundary:", INDEX)

    def test_no_legacy_undefined_token_helper(self):
        self.assertNotIn("if(token)o.headers.Authorization", INDEX)

    def test_server_compiles(self):
        proc = subprocess.run(
            ["python", "-m", "py_compile", str(ROOT / "server.py")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_inline_javascript_parses(self):
        scripts = re.findall(r"<script>(.*?)</script>", INDEX, flags=re.S)
        self.assertTrue(scripts, "No inline JavaScript found")
        combined = "\n".join(scripts)
        proc = subprocess.run(
            ["node", "--check"],
            input=combined,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_database_initializes_inbox_schema(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "ui-contract.db"
            env = os.environ.copy()
            env["SQLITE_PATH"] = str(db)
            code = f"""
import os
os.environ['SQLITE_PATH'] = r'{db}'
import server
server.init()
c = server.conn()
tables = {{r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}}
assert 'direct_messages' in tables
s = server.state(c, 'participant@demo.ru')
assert 'direct_messages' in s
assert isinstance(s['direct_messages'], list)
c.close()
"""
            proc = subprocess.run(
                ["python", "-c", code],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
