"""P0 UX-01 static navigation integrity for all Promomed public HTML surfaces.

This is a bounded *source* contract, not proof that every user journey works
in a real browser. Responsive browser QA separately covers dynamic flows.
"""
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"


class _Markup(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.references = []
        self.onclick = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        for key in ("href", "src"):
            if values.get(key):
                self.references.append((tag, key, values[key]))
        if values.get("onclick"):
            self.onclick.append(values["onclick"])


class NavigationIntegrityTests(unittest.TestCase):
    def test_local_html_pages_reference_existing_static_assets(self):
        pages = sorted(PUBLIC.glob("*.html"))
        self.assertGreaterEqual(len(pages), 10)
        for page in pages:
            parser = _Markup()
            parser.feed(page.read_text(encoding="utf-8"))
            for tag, attr, url in parser.references:
                if url.startswith(("http:", "https:", "mailto:", "tel:",
                                   "data:", "javascript:", "//", "#")):
                    continue
                path = urlsplit(url).path
                if not path or path.startswith("/api/"):
                    continue
                route = unquote(path)
                self.assertNotIn("\\", route, (page.name, route))
                if route == "/":
                    dest = PUBLIC / "index.html"
                elif route.startswith("/"):
                    dest = PUBLIC / route.lstrip("/")
                else:
                    dest = page.parent / route
                self.assertTrue(dest.is_file(), (page.name, tag, attr, url))

    def test_inline_home_actions_have_a_declared_handler(self):
        page = PUBLIC / "index.html"
        source = page.read_text(encoding="utf-8")
        markup = _Markup()
        markup.feed(source)
        self.assertGreaterEqual(len(markup.onclick), 100)
        handler_names = set()
        for inline_action in markup.onclick:
            # The first call is either a named app handler, a browser built-in,
            # or a guarded inline statement like if(event.target===this)...
            found = re.match(
                r"\s*(?:return\s+)?(?:window\.)?([A-Za-z_$][A-Za-z_$0-9]*)\s*\(",
                inline_action,
            )
            if not found:
                continue
            handler_names.add(found.group(1))
        self.assertGreaterEqual(len(handler_names), 60)
        for name in handler_names - {"if", "print"}:
            self.assertRegex(
                source,
                r"(?:function\s+" + re.escape(name) + r"\s*\("
                r"|(?:const|let|var)\s+" + re.escape(name) + r"\s*="
                r"|window\." + re.escape(name) + r"\s*=)",
                "index.html onclick references undeclared handler " + name,
            )

    def test_institutional_and_finance_surfaces_are_linked(self):
        home = (PUBLIC / "index.html").read_text(encoding="utf-8")
        workspace = (PUBLIC / "institutional-commercial-workspace.html").read_text(
            encoding="utf-8"
        )
        shell = (PUBLIC / "institutional-shell.js").read_text(encoding="utf-8")
        for route in (
            "/partner-collaboration.html", "/value-exchange.html",
            "/pilot-revenue-ladder.html",
        ):
            self.assertIn(route, home + workspace + shell)
        self.assertTrue((PUBLIC / "pilot-revenue-ladder.html").is_file())
        self.assertTrue((PUBLIC / "partner-collaboration.html").is_file())


if __name__ == "__main__":
    unittest.main()
