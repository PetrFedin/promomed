"""Browser proof for the participant-owned personal workspace.

Demo identity only. This validates UI wiring and responsive behavior; it is not
non-demo production admission or independent medical/privacy review.
"""
import os
import secrets
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("PROMOMED_BASE_URL", "http://127.0.0.1:10000").rstrip("/")
OUT = Path(os.environ.get("PROMOMED_SCREENSHOT_DIR", "artifacts/browser-qa")) / "my-state"


def login(page):
    page.fill("#email", "participant@demo.ru")
    page.fill("#password", "demo2027")
    page.click("#login-button")
    expect(page.locator("#workspace")).to_be_visible(timeout=12000)
    expect(page.locator("#account-email")).to_have_text("participant@demo.ru")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
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
                login(page)

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
                login(page)
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


if __name__ == "__main__":
    main()
