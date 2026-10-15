import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "public" / "personal" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "public" / "personal" / "workspace.js").read_text(encoding="utf-8")
CSS = (ROOT / "public" / "personal" / "workspace.css").read_text(encoding="utf-8")


class MyStateUiContractTests(unittest.TestCase):
    def test_private_workspace_uses_versioned_own_account_api(self):
        self.assertIn('const API="/api/my-state/v1"', JS)
        self.assertIn('request("/api/login"', JS)
        self.assertIn('API+"/logout-all"', JS)
        self.assertIn('API+"/notes"', JS)
        self.assertIn('API+"/notes/delete"', JS)

    def test_self_registration_uses_verified_public_endpoints(self):
        self.assertIn('const REG_REQUEST="/api/participant-registration/v1/request"', JS)
        self.assertIn('const REG_VERIFY="/api/participant-registration/v1/verify"', JS)
        self.assertIn('request(REG_REQUEST', JS)
        self.assertIn('request(REG_VERIFY', JS)
        self.assertIn('data.eventRegistration', JS)
        self.assertIn('data.demoOnly&&data.demoVerificationCode', JS)
        self.assertIn('id="signup-form"', HTML)
        self.assertIn('id="verify-form"', HTML)
        self.assertIn('autocomplete="one-time-code"', HTML)
        self.assertIn("Создание аккаунта не означает регистрацию на мероприятие", HTML)

    def test_bearer_token_is_memory_only(self):
        self.assertNotIn("localStorage", JS)
        self.assertNotIn("sessionStorage", JS)
        self.assertIn("state.token", JS)
        self.assertIn('window.addEventListener("pagehide",clearSession)', JS)

    def test_account_switch_and_stale_response_fencing_exist(self):
        self.assertIn("state.generation++", JS)
        self.assertIn("AbortController", JS)
        self.assertIn("stale(g,token)", JS)
        self.assertIn("data.role!==\"participant\"", JS)

    def test_login_captures_credentials_before_clear_session(self):
        capture = 'const email=$("email").value.trim(),password=$("password").value;'
        submit = JS.index('$("login-form").addEventListener("submit"')
        capture_at = JS.index(capture, submit)
        clear_at = JS.index("clearSession();", submit)
        self.assertGreaterEqual(submit, 0)
        self.assertGreaterEqual(capture_at, 0)
        self.assertGreater(clear_at, capture_at)

    def test_user_text_is_rendered_as_text_not_html(self):
        self.assertIn("textContent", JS)
        self.assertNotIn("innerHTML", JS)
        self.assertNotIn("insertAdjacentHTML", JS)

    def test_page_explains_truth_boundaries_and_limits(self):
        self.assertIn("Личная заметка", HTML)
        self.assertIn("не медицинская рекомендация", HTML)
        self.assertIn("Бронирование не считается посещением", HTML)
        self.assertIn('maxlength="2000"', HTML)
        self.assertIn("Выйти на всех устройствах", HTML)
        self.assertIn("localStorage", HTML)

    def test_page_has_local_content_security_policy_and_responsive_layout(self):
        self.assertIn("Content-Security-Policy", HTML)
        self.assertIn("default-src 'none'", HTML)
        self.assertIn("@media(max-width:760px)", CSS)
        self.assertIn("@media(max-width:390px)", CSS)


if __name__ == "__main__":
    unittest.main()
