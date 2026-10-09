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

class InstitutionalPresentationContractTests(unittest.TestCase):
    def test_all_institutional_surfaces_use_shared_shell(self):
        for name in PAGES:
            content=(PUBLIC/name).read_text(encoding="utf-8")
            self.assertIn('/institutional-shell.css',content,name)
            self.assertIn('/institutional-shell.js',content,name)

    def test_shell_contains_all_six_routes_and_truth_cue(self):
        js=(PUBLIC/"institutional-shell.js").read_text(encoding="utf-8")
        for name in PAGES:
            self.assertIn('/'+name,js)
        self.assertIn('Planning ≠ customer truth',js)
        self.assertIn('aria-current="page"',js)

    def test_print_hides_shared_navigation(self):
        css=(PUBLIC/"institutional-shell.css").read_text(encoding="utf-8")
        self.assertIn('@media print',css)
        self.assertIn('.institutionalShellNav,.institutionalShellTrail{display:none!important}',css)

if __name__=="__main__":
    unittest.main()
