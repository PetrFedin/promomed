"""Browser proof for capacity-aware event registration in personal workspace."""
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
OUT = Path(os.environ.get("PROMOMED_SCREENSHOT_DIR", "artifacts/browser-qa")) / "event-registration"
DB = os.environ.get("PROMOMED_BROWSER_QA_SQLITE_PATH", "/tmp/promomed-browser-qa.db")
EVENT_ID = "SOSTOYANIE-2027"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    email = "event-ui-" + secrets.token_hex(8) + "@example.test"
    password = "EventUiBrowser!" + secrets.token_urlsafe(15) + "8a"
    now = int(time.time())
    c = sqlite3.connect(DB, timeout=20)
    c.execute(
        "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
        "VALUES(?,?,'participant','Event UI','active',?,?)",
        (email, hash_password(password), now, now),
    )
    c.commit()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844}, locale="ru-RU")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        try:
            page.goto(BASE + "/personal/", wait_until="domcontentloaded")
            page.fill("#email", email)
            page.fill("#password", password)
            page.click("#login-button")
            expect(page.locator("#workspace")).to_be_visible(timeout=12000)

            card = page.locator(".eventRegistration").filter(has_text="СОСТОЯНИЕ / 2027").first
            expect(card).to_be_visible(timeout=12000)
            expect(card.locator(".eventStatus")).to_have_text("Не зарегистрирован")
            expect(card.locator(".eventAction")).to_have_text("Зарегистрироваться")
            card.locator(".eventAction").click()
            expect(card.locator(".eventStatus")).to_have_text("Место подтверждено", timeout=12000)
            expect(card.locator(".eventAction")).to_have_text("Отменить регистрацию")
            page.screenshot(path=str(OUT / "phone-confirmed.png"), full_page=True)

            row = c.execute(
                "SELECT status FROM participant_event_registrations_v1 "
                "WHERE event_id=? AND email=?", (EVENT_ID, email),
            ).fetchone()
            assert row and row[0] == "confirmed", row
            assert c.execute(
                "SELECT 1 FROM registrations WHERE email=?", (email,)
            ).fetchone() is None

            card.locator(".eventAction").click()
            expect(card.locator(".eventStatus")).to_have_text("Регистрация отменена", timeout=12000)
            expect(card.locator(".eventAction")).to_have_text("Зарегистрироваться")
            row = c.execute(
                "SELECT status FROM participant_event_registrations_v1 "
                "WHERE event_id=? AND email=?", (EVENT_ID, email),
            ).fetchone()
            assert row and row[0] == "cancelled", row
            assert not errors, errors
        finally:
            page.close()
            browser.close()
            c.execute(
                "DELETE FROM participant_event_registrations_v1 WHERE email=?", (email,)
            )
            c.execute("DELETE FROM auth_sessions WHERE email=?", (email,))
            c.execute("DELETE FROM personal_notes_v1 WHERE email=?", (email,))
            c.execute("DELETE FROM accounts WHERE email=?", (email,))
            c.commit()
            c.close()


if __name__ == "__main__":
    main()
