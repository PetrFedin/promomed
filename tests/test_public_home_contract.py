"""PUB-UI: non-demo root is isolated from legacy demo/global state."""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from server import H

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/"public"/"public-home.html").read_text(encoding="utf-8")
JS=(ROOT/"public"/"public-home.js").read_text(encoding="utf-8")
CSS=(ROOT/"public"/"public-home.css").read_text(encoding="utf-8")
SERVER=(ROOT/"server.py").read_text(encoding="utf-8")


class PublicHomeContractTests(unittest.TestCase):
    def test_public_home_uses_only_versioned_public_state(self):
        self.assertIn('fetch("/api/public-state/v1"',JS)
        for forbidden in (
            "/api/state","/api/discovery","localStorage","sessionStorage",
            "innerHTML","insertAdjacentHTML","Authorization",
        ):
            self.assertNotIn(forbidden,JS)
        self.assertIn("textContent",JS)

    def test_public_home_has_truth_boundary_and_personal_link(self):
        self.assertIn("Только явно допущенные версии",HTML)
        self.assertIn("Без персональных данных",HTML)
        self.assertIn("Без скрытых KPI и лидов",HTML)
        self.assertIn("Без медицинских выводов по поведению",HTML)
        self.assertIn('href="/personal/"',HTML)
        self.assertIn("Content-Security-Policy",HTML)

    def test_public_home_has_safe_empty_and_error_states(self):
        self.assertIn('id="agenda-empty"',HTML)
        self.assertIn('id="content-empty"',HTML)
        self.assertIn('id="error"',HTML)
        self.assertIn("Программа готовится к публикации",HTML)
        self.assertIn("Материалы ещё не опубликованы",HTML)

    def test_public_home_is_responsive(self):
        self.assertIn("@media(max-width:820px)",CSS)
        self.assertIn("@media(max-width:430px)",CSS)

    def test_non_demo_root_reroutes_before_auth(self):
        h=SimpleNamespace(path="/",out=lambda value,status=200:(value,status))
        with patch("server.db.demo_seed_enabled",return_value=False):
            with patch("server.auth",side_effect=AssertionError("auth queried")):
                with patch(
                    "http.server.SimpleHTTPRequestHandler.do_GET",
                    autospec=True,
                    return_value="PUBLIC",
                ) as inherited:
                    self.assertEqual(H.do_GET(h),"PUBLIC")
                    self.assertEqual(h.path,"/public-home.html")
                    inherited.assert_called_once_with(h)

    def test_demo_root_keeps_existing_application(self):
        self.assertIn(
            'if p in ("/","/index.html") and not db.demo_seed_enabled():',
            SERVER,
        )


if __name__=="__main__":
    unittest.main()
