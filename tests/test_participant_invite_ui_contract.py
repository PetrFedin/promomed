"""Static privacy/security contract for the invite activation surface."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "public" / "join" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "public" / "join" / "join.js").read_text(encoding="utf-8")
CSS = (ROOT / "public" / "join" / "join.css").read_text(encoding="utf-8")


class ParticipantInviteUiContractTests(unittest.TestCase):
    def test_token_uses_fragment_and_is_removed_from_address_bar(self):
        self.assertIn("location.hash", JS)
        self.assertIn("new URLSearchParams(raw)", JS)
        self.assertIn("history.replaceState(null,'',location.pathname)", JS)
        self.assertNotIn("location.search", JS)

    def test_no_browser_persistent_credential_storage(self):
        combined = HTML + "\n" + JS
        self.assertNotIn("localStorage", combined)
        self.assertNotIn("sessionStorage", combined)
        self.assertNotIn("document.cookie", combined)

    def test_hidden_state_overrides_layout_rules(self):
        # Author CSS display rules must never make an element with [hidden] visible.
        compact = CSS.replace(" ", "").replace("\n", "")
        self.assertIn("[hidden]{display:none!important}", compact)
        self.assertIn('id="success" class="success" hidden', HTML)

    def test_activation_posts_token_and_password_only(self):
        self.assertIn("JSON.stringify({token,password:password.value})", JS)
        self.assertNotIn("email:", JS)
        self.assertNotIn("name:", JS)
        self.assertIn("/api/participant-invite/accept", JS)

    def test_no_automatic_session_or_medical_form_claim(self):
        self.assertIn("Серверную сессию мы не создавали автоматически", HTML)
        self.assertIn("не медицинская анкета", HTML)
        self.assertIn('href="/personal/"', HTML)

    def test_csp_is_same_origin_and_form_submission_is_script_controlled(self):
        self.assertIn("default-src 'none'", HTML)
        self.assertIn("connect-src 'self'", HTML)
        self.assertIn("form-action 'none'", HTML)
        self.assertIn('id="joinForm"', HTML)


if __name__ == "__main__":
    unittest.main()
