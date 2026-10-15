"""Browser proof: new participant request -> code -> account -> my-state.

Runs only against demo-seeded browser QA. The verification code is intentionally
returned by the demo API; production must deliver it through configured email.
"""
import os
import re
import secrets
import sqlite3
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("PROMOMED_BASE_URL", "http://127.0.0.1:10000").rstrip("/")
OUT = Path(os.environ.get("PROMOMED_SCREENSHOT_DIR", "artifacts/browser-qa")) / "registration"
DB = os.environ.get("PROMOMED_BROWSER_QA_SQLITE_PATH", "/tmp/promomed-browser-qa.db")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    email = "signup-browser-" + secrets.token_hex(8) + "@example.test"
    password = "SignupBrowser!" + secrets.token_urlsafe(16) + "9a"
    name = "Новый участник"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844}, locale="ru-RU")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        try:
            page.goto(BASE + "/personal/", wait_until="domcontentloaded")
            expect(page.locator("#signed-out")).to_be_visible()
            page.click("#mode-signup")
            expect(page.locator("#signup-form")).to_be_visible()

            page.fill("#signup-name", name)
            page.fill("#signup-email", email)
            page.fill("#signup-password", password)
            page.click("#signup-button")

            expect(page.locator("#verify-form")).to_be_visible(timeout=12000)
            expect(page.locator("#verify-email")).to_contain_text(email)
            expect(page.locator("#demo-code")).to_be_visible()
            demo = page.locator("#demo-code").inner_text()
            match = re.search(r"([0-9]{6})", demo)
            assert match, demo
            code = match.group(1)

            page.screenshot(path=str(OUT / "phone-verification.png"), full_page=True)
            page.fill("#verify-code", code)
            page.click("#verify-button")

            expect(page.locator("#workspace")).to_be_visible(timeout=12000)
            expect(page.locator("#account-email")).to_have_text(email)
            expect(page.locator("#registration")).to_have_text(
                "Нет подтверждённой регистрации"
            )
            assert page.evaluate("localStorage.length") == 0
            assert page.evaluate("sessionStorage.length") == 0
            page.screenshot(path=str(OUT / "phone-new-account.png"), full_page=True)

            # Memory-only session: reload requires login, account persists.
            page.reload(wait_until="domcontentloaded")
            expect(page.locator("#signed-out")).to_be_visible()
            expect(page.locator("#workspace")).to_be_hidden()
            page.fill("#email", email)
            page.fill("#password", password)
            page.click("#login-button")
            expect(page.locator("#workspace")).to_be_visible(timeout=12000)
            expect(page.locator("#account-email")).to_have_text(email)
            assert not errors, errors
        finally:
            page.close()
            browser.close()
            c = sqlite3.connect(DB, timeout=20)
            try:
                c.execute("DELETE FROM personal_notes_v1 WHERE email=?", (email,))
                c.execute("DELETE FROM auth_sessions WHERE email=?", (email,))
                c.execute(
                    "DELETE FROM participant_registration_requests WHERE email=?",
                    (email,),
                )
                c.execute("DELETE FROM registrations WHERE email=?", (email,))
                c.execute("DELETE FROM accounts WHERE email=?", (email,))
                c.commit()
            finally:
                c.close()


if __name__ == "__main__":
    main()
