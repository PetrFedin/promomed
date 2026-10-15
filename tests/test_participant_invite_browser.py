"""Browser proof: organizer invite -> anonymous activation -> participant login."""
import os
import secrets
import sqlite3
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("PROMOMED_BASE_URL", "http://127.0.0.1:10000").rstrip("/")
OUT = Path(os.environ.get("PROMOMED_SCREENSHOT_DIR", "artifacts/browser-qa")) / "participant-invite"
DB = os.environ.get("PROMOMED_BROWSER_QA_SQLITE_PATH", "/tmp/promomed-browser-qa.db")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    email = "invite-browser-" + secrets.token_hex(8) + "@example.test"
    password = "InviteBrowserPassphrase42!"
    invite_id = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844}, locale="ru-RU")
        try:
            login = page.request.post(
                BASE + "/api/login",
                data={"email": "organizer@demo.ru", "password": "demo2027"},
            )
            assert login.ok, (login.status, login.text())
            organizer_token = login.json()["token"]
            created = page.request.post(
                BASE + "/api/participant-invite/create",
                headers={"Authorization": "Bearer " + organizer_token},
                data={"email": email, "name": "Invite Browser Participant"},
            )
            assert created.status == 201, (created.status, created.text())
            invite = created.json()
            invite_id = invite["invite_id"]
            raw_token = invite["token"]

            page.goto(
                BASE + "/join/#token=" + raw_token,
                wait_until="domcontentloaded",
            )
            expect(page.locator("#joinForm")).to_be_visible()
            expect(page.locator("#inviteState")).to_contain_text("Приглашение получено")
            assert page.url == BASE + "/join/", page.url
            assert page.evaluate("localStorage.length") == 0
            assert page.evaluate("sessionStorage.length") == 0

            page.fill("#password", password)
            page.fill("#confirm", password)
            page.click("#submit")
            expect(page.locator("#success")).to_be_visible(timeout=12000)
            expect(page.locator("#joinForm")).to_be_hidden()
            page.screenshot(path=str(OUT / "activation-success.png"), full_page=True)

            page.click("#success a")
            expect(page.locator("#signed-out")).to_be_visible(timeout=10000)
            page.fill("#email", email)
            page.fill("#password", password)
            page.click("#login-button")
            expect(page.locator("#workspace")).to_be_visible(timeout=12000)
            expect(page.locator("#account-email")).to_have_text(email)
            expect(page.locator("#registration")).to_have_text("Подтверждена")
            assert page.evaluate("localStorage.getItem('sostoyanie_token')") is None
            page.screenshot(path=str(OUT / "participant-workspace.png"), full_page=True)

            replay = page.request.post(
                BASE + "/api/participant-invite/accept",
                data={"token": raw_token, "password": password},
            )
            assert replay.status == 404, (replay.status, replay.text())
        finally:
            browser.close()
            c = sqlite3.connect(DB, timeout=20)
            try:
                c.execute("DELETE FROM auth_sessions WHERE email=?", (email,))
                c.execute("DELETE FROM personal_notes_v1 WHERE email=?", (email,))
                c.execute("DELETE FROM registrations WHERE email=?", (email,))
                if invite_id:
                    c.execute("DELETE FROM participant_invites WHERE id=?", (invite_id,))
                    c.execute(
                        "DELETE FROM events WHERE kind='participant_invite_created' "
                        "AND payload LIKE ?",
                        ("%" + invite_id + "%",),
                    )
                c.execute("DELETE FROM accounts WHERE email=?", (email,))
                c.commit()
            finally:
                c.close()


if __name__ == "__main__":
    main()
