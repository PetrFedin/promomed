"""HTTP session authority after role, suspension and deletion via a real local server.

Uses only a disposable CI SQLite fixture, never external accounts or production.
"""
import os
import secrets
import sqlite3
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.auth import hash_password

BASE = os.getenv("PROMOMED_BASE_URL", "http://127.0.0.1:10000").rstrip("/")
DB = os.getenv("PROMOMED_BROWSER_QA_SQLITE_PATH", "/tmp/promomed-browser-qa.db")


def main():
    email = "session-browser-" + secrets.token_hex(8) + "@example.test"
    password = "ci-only-" + secrets.token_urlsafe(18)
    now = int(time.time())
    c = sqlite3.connect(DB, timeout=20)
    c.execute(
        "INSERT INTO accounts(email,password_hash,role,name,status,created_at,updated_at) "
        "VALUES(?,?,'participant','Disposable QA','active',?,?)",
        (email, hash_password(password), now, now),
    )
    c.commit()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            def login():
                response = page.request.post(
                    BASE + "/api/login",
                    data={"email": email, "password": password},
                    timeout=10000,
                )
                assert response.status == 200, response.text()
                return response.json()["token"]

            def read(token):
                return page.request.get(
                    BASE + "/api/client-365",
                    headers={"Authorization": "Bearer " + token},
                    timeout=10000,
                )

            old = login()
            initial = read(old)
            assert initial.status == 200, initial.text()
            assert initial.json()["truthBoundary"]["ownAccountOnly"]
            c.execute("UPDATE accounts SET status='suspended' WHERE email=?", (email,))
            c.commit()
            after_suspend = read(old)
            assert after_suspend.status == 401, after_suspend.text()
            c.execute("UPDATE accounts SET status='active' WHERE email=?", (email,))
            c.commit()
            assert read(old).status == 401, "Suspension cannot resurrect an old token"
            second = login()
            assert read(second).status == 200
            c.execute("UPDATE accounts SET role='organizer' WHERE email=?", (email,))
            c.commit()
            assert read(second).status == 401, "Role change cannot retain participant session"
            # A newly issued organizer token cannot read the participant-only API.
            new_role = login()
            assert read(new_role).status == 403
            c.execute("DELETE FROM accounts WHERE email=?", (email,))
            c.commit()
            assert read(new_role).status == 401, "Deleted account must lose session immediately"
        finally:
            browser.close()
            c.execute("DELETE FROM auth_sessions WHERE email=?", (email,))
            c.execute("DELETE FROM accounts WHERE email=?", (email,))
            c.commit()
            c.close()


if __name__ == "__main__":
    main()
