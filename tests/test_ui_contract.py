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


class UIContractTests(unittest.TestCase):
    def test_guest_lands_on_home_without_forced_login(self):
        self.assertIn("else{role='participant';show('today');updateTag();await syncState(true)}", INDEX)
        self.assertNotIn("else if(!apiToken){openSheet('login')}", INDEX)
        self.assertNotIn("await switchRole(r);setInterval", INDEX)
        self.assertIn("<b>⌂</b>Главная", INDEX)

    def test_account_inbox_is_consent_first(self):
        self.assertIn('id="accountInbox"', INDEX)
        self.assertIn("function openConversation", INDEX)
        self.assertIn('elif p=="/api/direct-message"', SERVER)
        self.assertIn("conversation_requires_mutual_consent", SERVER)
        self.assertIn("mutual_meetings", SERVER)
        self.assertIn("organizer@demo.ru", SERVER)

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
        self.assertIn('role="dialog" aria-modal="true"', INDEX)\n        self.assertIn('rel="manifest" href="/manifest.webmanifest"', INDEX)\n        self.assertIn('apple-mobile-web-app-capable" content="yes"', INDEX)\n        self.assertIn(":focus-visible", INDEX)\n        self.assertIn("@media(prefers-reduced-motion:reduce)", INDEX)\n        self.assertIn("@media(display-mode:standalone)", INDEX)

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
