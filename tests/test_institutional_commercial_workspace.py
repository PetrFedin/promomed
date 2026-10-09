import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class InstitutionalCommercialWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.html=(ROOT/"public"/"institutional-commercial-workspace.html").read_text(encoding="utf-8")

    def test_workspace_links_only_existing_planning_surfaces(self):
        for href in (
            "/institutional-buyer-fit.html",
            "/institutional-pilot-proposal.html",
            "/institutional-outreach-pack.html",
            "/institutional-command-center.html",
        ):
            self.assertIn(f'href="{href}"',self.html)

    def test_truth_boundaries_are_visible(self):
        self.assertIn("Workspace ≠ pipeline.",self.html)
        self.assertIn("READY ≠ APPROVED",self.html)
        self.assertIn("PARTICIPATION GATED",self.html)
        self.assertIn("NO CRM TRUTH",self.html)
        self.assertIn("NO COMMERCIAL CLAIM",self.html)

    def test_workspace_has_print_mode(self):
        self.assertIn("@media print",self.html)
        self.assertIn("window.print()",self.html)
        self.assertIn("Printed planning guide.",self.html)

    def test_workspace_contains_no_data_mutation_or_fake_metrics(self):
        upper=self.html.upper()
        self.assertNotIn("WIN PROBABILITY",upper)
        self.assertNotIn("PIPELINE VALUE",upper)
        self.assertNotIn("ARR",upper)
        self.assertNotIn("MRR",upper)

if __name__=="__main__":unittest.main()
