"""Browser proof for the participant-owned personal workspace.

Demo identity only. This validates UI wiring and responsive behavior; it is not
non-demo production admission or independent medical/privacy review.
"""
import os
import secrets
import sqlite3
import sys
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.auth import hash_password

BASE = os.environ.get("PROMOMED_BASE_URL", "http://127.0.0.1:10000").rstrip("/")
OUT = Path(os.environ.get("PROMOMED_SCREENSHOT_DIR", "artifacts/browser-qa")) / "my-state"
DB = os.environ.get("PROMOMED_BROWSER_QA_SQLITE_PATH", "/tmp/promomed-browser-qa.db")


def login(page, email, password):
    page.fill("#email", email)
    page.fill("#password", password)
    page.click("#login-button")
    expect(page.locator("#workspace")).to_be_visible(timeout=12000)
    expect(page.locator("#account-email")).to_have_text(email)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    email = "my-state-browser-" + secrets.token_hex(8) + "@example.test"
    password = "ci-only-" + secrets.token_urlsafe(18) + "Aa1!"
    now = int(time.time())
    c = sqlite3.connect(DB, timeout=20)
    c.execute(
        "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
        "VALUES(?,?,'participant','My State Browser','active',?,?)",
        (email, hash_password(password), now, now),
    )
    c.commit()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for name, width, height in (
                ("phone", 375, 812),
                ("tablet", 820, 1180),
                ("desktop", 1440, 900),
            ):
                page = browser.new_page(
                    viewport={"width": width, "height": height},
                    locale="ru-RU",
                )
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(BASE + "/personal/", wait_until="domcontentloaded")
                expect(page.locator("#signed-out")).to_be_visible()
                login(page, email, password)

                text = "browser-note-" + secrets.token_hex(6)
                page.fill("#note-text", text)
                page.click("#save-note")
                expect(page.locator("#notes")).to_contain_text(text, timeout=10000)
                page.screenshot(
                    path=str(OUT / (name + "-workspace.png")),
                    full_page=True,
                )

                overflow = page.evaluate(
                    "document.documentElement.scrollWidth-document.documentElement.clientWidth"
                )
                assert overflow <= 1, (name, overflow)
                assert not errors, errors

                # Token is intentionally memory-only: reload returns to login.
                page.reload(wait_until="domcontentloaded")
                expect(page.locator("#signed-out")).to_be_visible()
                expect(page.locator("#workspace")).to_be_hidden()
                expect(page.locator("body")).not_to_contain_text(text)

                # Data itself persists in the database and is visible after re-auth.
                login(page, email, password)
                expect(page.locator("#notes")).to_contain_text(text, timeout=10000)
                note = page.locator(".note").filter(has_text=text).first
                note.locator("button").click()
                expect(note.locator("button")).to_have_text("Подтвердить удаление")
                note.locator("button").click()
                expect(page.locator("#notes")).not_to_contain_text(text, timeout=10000)

                # Server-backed logout-all must return to the signed-out surface.
                page.click("#logout-all")
                expect(page.locator("#signed-out")).to_be_visible(timeout=10000)
                page.close()
        finally:
            browser.close()
            c.execute("DELETE FROM auth_sessions WHERE email=?", (email,))
            c.execute("DELETE FROM accounts WHERE email=?", (email,))
            c.commit()
            c.close()


if __name__ == "__main__":
    main()
