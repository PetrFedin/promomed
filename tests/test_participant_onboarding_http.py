"""HTTP composition tests for participant invite onboarding."""
import io
import json
import unittest
from email.message import Message
from types import SimpleNamespace
from unittest.mock import patch

from app.commanding import custom
from app.participant_onboarding import ACCEPT_ROUTE, CREATE_ROUTE
from server import H


def request(path, payload=None):
    headers = Message()
    raw = b""
    if payload is not None:
        raw = json.dumps(payload).encode("utf-8")
        headers["Content-Length"] = str(len(raw))
    return SimpleNamespace(
        path=path,
        headers=headers,
        rfile=io.BytesIO(raw),
        out=lambda value, status=200: (value, status),
    )


class FakeConn:
    def __init__(self):
        self.committed = False
        self.closed = False

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        self.closed = True


class ParticipantOnboardingHttpTests(unittest.TestCase):
    def test_accept_dispatches_before_authentication(self):
        h = request(ACCEPT_ROUTE, {"token": "A" * 43, "password": "PasswordPhrase42!"})
        expected = {"accepted": True, "sessionCreated": False}
        with patch("server.handle_participant_invite_public", return_value=(expected, 201)) as public:
            with patch("server.auth", side_effect=AssertionError("auth queried")):
                self.assertEqual(H.do_POST(h), (expected, 201))
        public.assert_called_once()

    def test_query_selector_is_rejected_before_body_or_auth(self):
        class ExplodingRead:
            def read(self, *_):
                raise AssertionError("body read")
        h = request(ACCEPT_ROUTE + "?email=other@example.test")
        h.rfile = ExplodingRead()
        with patch("server.auth", side_effect=AssertionError("auth queried")):
            with patch("server.handle_participant_invite_public",
                       side_effect=AssertionError("public handler called")):
                self.assertEqual(
                    H.do_POST(h), ({"error": "unsupported_query"}, 422)
                )

    def test_create_requires_server_authenticated_organizer(self):
        h = request(CREATE_ROUTE, {"email": "p@example.test", "name": "P"})
        with patch("server.auth", return_value=None):
            with patch("server.conn", side_effect=AssertionError("DB opened")):
                self.assertEqual(H.do_POST(h), ({"error": "unauthorized"}, 401))

    def test_authenticated_create_uses_current_actor_not_body_selector(self):
        h = request(CREATE_ROUTE, {"email": "p@example.test", "name": "P"})
        c = FakeConn()
        outcome = custom({
            "invite_id": "b" * 32,
            "token": "A" * 43,
            "expires_at": 1,
            "delivery": "manual_secure_channel_required",
        }, 201)
        with patch(
            "server.auth",
            return_value=("organizer", "Organizer", "organizer@example.test"),
        ):
            with patch("server.conn", return_value=c):
                with patch(
                    "server.handle_participant_invite_command",
                    return_value=outcome,
                ) as command:
                    payload, status = H.do_POST(h)
        self.assertEqual(status, 201)
        self.assertEqual(payload["invite_id"], "b" * 32)
        command.assert_called_once_with(
            c, CREATE_ROUTE, "organizer", "organizer@example.test",
            {"email": "p@example.test", "name": "P"},
        )
        self.assertTrue(c.committed)
        self.assertTrue(c.closed)


if __name__ == "__main__":
    unittest.main()
