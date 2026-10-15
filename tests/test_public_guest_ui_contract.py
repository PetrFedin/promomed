import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/"public"/"explore"/"index.html").read_text(encoding="utf-8")
JS=(ROOT/"public"/"explore"/"explore.js").read_text(encoding="utf-8")
CSS=(ROOT/"public"/"explore"/"explore.css").read_text(encoding="utf-8")


class PublicGuestUiContractTests(unittest.TestCase):
    def test_guest_surface_uses_only_public_state_v1(self):
        self.assertIn('fetch("/api/public-state/v1"', JS)
        self.assertNotIn("/api/state", JS)
        self.assertNotIn("/api/discovery", JS)
        self.assertNotIn("/api/analytics", JS)

    def test_no_browser_credential_or_untrusted_html_storage(self):
        self.assertNotIn("localStorage", JS)
        self.assertNotIn("sessionStorage", JS)
        self.assertNotIn("Authorization", JS)
        self.assertNotIn("innerHTML", JS)
        self.assertNotIn("insertAdjacentHTML", JS)
        self.assertIn("textContent", JS)

    def test_empty_and_error_states_are_truthful(self):
        self.assertIn("Пока без публикаций", HTML)
        self.assertIn("Публичных материалов пока нет", HTML)
        self.assertIn("Непроверенные локальные данные не подставлены", JS)
        self.assertIn("publication hold", HTML.lower())

    def test_personal_account_is_separate_surface(self):
        self.assertIn('href="/personal/"', HTML)
        self.assertIn("Моё СОСТОЯНИЕ", HTML)
        self.assertNotIn("Войти как", HTML)

    def test_non_demo_root_routes_to_admitted_guest_surface(self):
        import http.server
        import server
        for path in ("/", "/index.html"):
            h=SimpleNamespace(path=path)
            with patch("server.db.demo_seed_enabled", return_value=False):
                with patch.object(http.server.SimpleHTTPRequestHandler, "do_GET", return_value="STATIC") as static:
                    self.assertEqual(server.H.do_GET(h), "STATIC")
                    self.assertEqual(h.path, "/explore/")
                    static.assert_called_once()

    def test_demo_root_is_not_rewritten_to_public_guest_surface(self):
        import http.server
        import server
        h=SimpleNamespace(path="/")
        with patch("server.db.demo_seed_enabled", return_value=True):
            with patch("server.auth", return_value=None):
                with patch.object(http.server.SimpleHTTPRequestHandler, "do_GET", return_value="LEGACY") as static:
                    self.assertEqual(server.H.do_GET(h), "LEGACY")
                    self.assertEqual(h.path, "/")

    def test_csp_and_responsive_contract(self):
        self.assertIn("Content-Security-Policy", HTML)
        self.assertIn("default-src 'none'", HTML)
        self.assertIn("@media(max-width:760px)", CSS)


if __name__=="__main__":
    unittest.main()
