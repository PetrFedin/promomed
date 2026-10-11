import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "public/investor-decision-lab.html").read_text(encoding="utf-8")
JS = (ROOT / "public/investor-decision-lab.js").read_text(encoding="utf-8")
CSS = (ROOT / "public/investor-decision-lab.css").read_text(encoding="utf-8")
HOME = (ROOT / "public/index.html").read_text(encoding="utf-8")
COMMERCIAL = (ROOT / "public/institutional-commercial-workspace.html").read_text(encoding="utf-8")


class InvestorDecisionLabTests(unittest.TestCase):
    def test_three_scenarios_and_all_inputs(self):
        self.assertEqual(len(re.findall(r'data-scenario="(?:conservative|base|optimistic)"', HTML)), 3)
        for key in ("clients","feeAnnual","events","eventFee","variablePct","fixedCost","investment"):
            self.assertIn('id="' + key + '"', HTML)
        self.assertIn('id="metricBreakeven"', HTML)
        self.assertIn('id="metricPayback"', HTML)

    def test_source_of_truth_is_read_only_and_no_artificial_numbers(self):
        self.assertIn('get("/health")', JS)
        self.assertIn('get("/ready")', JS)
        self.assertIn('get("/api/product-quality-proof")', JS)
        self.assertNotIn("localStorage", JS)
        self.assertNotIn("sessionStorage", JS)
        self.assertNotRegex(JS, r'\bfetch\s*\([^)]*method\s*:\s*["\']POST')
        self.assertNotIn("new WebSocket", JS)
        self.assertIn("USER ASSUMPTIONS ONLY", HTML)
        self.assertIn("Не подтверждён", HTML)
        self.assertIn("не финансовый прогноз", HTML.lower())

    def test_error_safe_numbers_and_zero_contribution(self):
        self.assertIn("Number.isFinite(n)", JS)
        self.assertIn("Number.isSafeInteger(n)", JS)
        self.assertIn("contributionRate <= 0", JS)
        self.assertIn("operating > 0", JS)
        self.assertIn("revenue > 0", JS)
        self.assertIn("breakEven === null", JS)
        self.assertIn("payback === null", JS)

    def test_dom_outputs_are_not_built_from_untrusted_html(self):
        self.assertNotIn(".innerHTML", JS)
        self.assertIn("textContent", JS)
        self.assertIn("replaceChildren", JS)
        self.assertIn("aria-pressed", JS)
        self.assertIn("aria-invalid", JS)
        self.assertIn("@media(max-width:650px)", CSS)
        self.assertIn("prefers-reduced-motion", CSS)

    def test_navigation_to_proven_workspaces(self):
        for page in ("institutional-buyer-fit.html", "institutional-pilot-proposal.html",
                     "institutional-command-center.html", "institutional-commercial-workspace.html"):
            self.assertIn(page, HTML)
        self.assertIn("investor-decision-lab.html", HOME)
        self.assertIn("investor-decision-lab.html", COMMERCIAL)


if __name__ == "__main__":
    unittest.main()
