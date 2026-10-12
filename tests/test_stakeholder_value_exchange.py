import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PAGE=(ROOT/"public/value-exchange.html").read_text(encoding="utf-8")
JS=(ROOT/"public/value-exchange.js").read_text(encoding="utf-8")
CSS=(ROOT/"public/value-exchange.css").read_text(encoding="utf-8")
HOME=(ROOT/"public/index.html").read_text(encoding="utf-8")

class StakeholderValueContract(unittest.TestCase):
    def test_home_discovery_and_deep_link(self):
        self.assertIn('href="/value-exchange.html"', HOME)
        self.assertIn("function applyStakeholderDeepLink()", HOME)
        self.assertIn("allowed.has(target)",HOME)

    def test_three_role_experience(self):
        for role in ("participant","partner","investor"):
            self.assertIn('id="role-'+role+'"',PAGE)
            self.assertIn(role+":{",JS)
        self.assertIn('role="tabpanel"',PAGE)
        self.assertIn('aria-controls="role-content"',PAGE)
        self.assertIn("aria-selected",JS)
        self.assertIn('event.key==="ArrowRight"',JS)
        self.assertIn('event.key==="ArrowLeft"',JS)

    def test_existing_routes_only_and_no_fake_lead(self):
        for url in ("/?screen=events","/?screen=commercial","/institutional-commercial-workspace.html","/institutional-evidence-export.html","/?presentation=executive"):
            self.assertIn(url,PAGE+JS)
        self.assertNotIn("fetch('/api/lead'",JS)
        self.assertNotIn('method:"POST"',JS)
        self.assertIn("Коммерческий спрос",PAGE)

    def test_truthful_read_only_api_and_form(self):
        for endpoint in ("/health","/ready","/api/product-quality-proof"):self.assertIn(endpoint,JS)
        self.assertIn("Promise.allSettled",JS)
        self.assertIn('r.production_ready===true',JS)
        self.assertIn('НЕТ ПОДТВЕРЖДЕНИЯ',JS)
        for f in ("audience","reach","optin","return"):
            self.assertIn('id="'+f+'"',PAGE)
        self.assertIn('raw!==""',JS)
        self.assertIn('values.audience*values.reach/100',JS)
        self.assertIn('seen*values.optin/100',JS)
        self.assertIn('consent*values.return/100',JS)
        self.assertIn("aria-invalid",JS)
        self.assertIn("navigator.clipboard.writeText",JS)

    def test_responsive_accessibility(self):
        self.assertIn('name="viewport"',PAGE)
        self.assertIn(".skip:focus",CSS)
        self.assertIn("prefers-reduced-motion",CSS)
        self.assertIn("@media(max-width:670px)",CSS)
        self.assertIn('role="status"',PAGE)

if __name__=="__main__":
    unittest.main()
