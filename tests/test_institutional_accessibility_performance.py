import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/"public"
PAGES=(
    "institutional-commercial-workspace.html",
    "institutional-buyer-fit.html",
    "institutional-pilot-proposal.html",
    "institutional-outreach-pack.html",
    "institutional-evidence-export.html",
    "institutional-command-center.html",
)

class InstitutionalAccessibilityPerformanceTests(unittest.TestCase):
    def test_shared_shell_accessibility_contract(self):
        css=(PUBLIC/"institutional-shell.css").read_text(encoding="utf-8")
        js=(PUBLIC/"institutional-shell.js").read_text(encoding="utf-8")
        self.assertIn("institutionalSkipLink",css)
        self.assertIn("prefers-reduced-motion:reduce",css)
        self.assertIn("forced-colors:active",css)
        self.assertIn("focus-visible",css)
        self.assertIn("main-content",js)
        self.assertIn("tabindex','-1",js)
        self.assertIn("Перейти к основному содержанию",js)

    def test_static_performance_budgets(self):
        css=(PUBLIC/"institutional-shell.css").read_bytes()
        js=(PUBLIC/"institutional-shell.js").read_bytes()
        self.assertLessEqual(len(css),7000)
        self.assertLessEqual(len(js),6000)
        for name in PAGES:
            payload=(PUBLIC/name).read_bytes()
            self.assertLessEqual(len(payload),70000,name)

    def test_no_external_runtime_assets_on_institutional_surfaces(self):
        for name in PAGES:
            content=(PUBLIC/name).read_text(encoding="utf-8").lower()
            self.assertNotIn('<script src="http',content,name)
            self.assertNotIn('<link rel="stylesheet" href="http',content,name)
            self.assertNotIn('<img src="http',content,name)

    def test_paint_containment_is_progressive_enhancement(self):
        css=(PUBLIC/"institutional-shell.css").read_text(encoding="utf-8")
        js=(PUBLIC/"institutional-shell.js").read_text(encoding="utf-8")
        self.assertIn("content-visibility:auto",css)
        self.assertIn("contain-intrinsic-size",css)
        self.assertIn("institutionalPerfRegion",js)

if __name__=="__main__":
    unittest.main()
