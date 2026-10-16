import io
import json
import unittest
from email.message import Message
from types import SimpleNamespace
from unittest.mock import patch

from app.commanding import custom
from app.my_workspace import NOTE_ROUTE, READ_ROUTE
from server import H


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


class MyStateHttpRoutingTests(unittest.TestCase):
    def test_get_requires_authenticated_server_session_before_db(self):
        h = request(READ_ROUTE)
        with patch("server.auth", return_value=None):
            with patch("server.conn", side_effect=AssertionError("DB opened")):
                self.assertEqual(
                    H.do_GET(h), ({"error": "unauthorized"}, 401)
                )

    def test_get_rejects_client_account_selector_before_auth_or_db(self):
        h = request(READ_ROUTE + "?email=other@example.test")
        with patch("server.auth", side_effect=AssertionError("auth queried")):
            with patch("server.conn", side_effect=AssertionError("DB opened")):
                self.assertEqual(
                    H.do_GET(h), ({"error": "unsupported_query"}, 422)
                )

    def test_authenticated_get_dispatches_current_actor_only_and_closes(self):
        h = request(READ_ROUTE)
        c = FakeConn()
        expected = {"version": "my-state-v1", "account": {"email": "a@example.test"}}
        with patch(
            "server.auth",
            return_value=("participant", "Actor", "a@example.test"),
        ):
            with patch("server.conn", return_value=c):
                with patch(
                    "server.read_my_workspace",
                    return_value=(expected, 200),
                ) as read:
                    self.assertEqual(H.do_GET(h), (expected, 200))
        read.assert_called_once_with(
            c, READ_ROUTE, "participant", "a@example.test"
        )
        self.assertTrue(c.closed)

    def test_post_rejects_query_selector_before_reading_body(self):
        class ExplodingRead:
            def read(self, *_):
                raise AssertionError("body read")
        h = request(NOTE_ROUTE + "?email=other@example.test")
        h.rfile = ExplodingRead()
        with patch("server.auth", side_effect=AssertionError("auth queried")):
            self.assertEqual(
                H.do_POST(h), ({"error": "unsupported_query"}, 422)
            )

    def test_post_uses_workspace_command_and_never_global_state(self):
        h = request(
            NOTE_ROUTE,
            {"text": "private", "request_id": "a" * 32},
        )
        c = FakeConn()
        outcome = custom(
            {
                "note": {
                    "id": "b" * 32,
                    "body": "private",
                    "created_at": 1,
                },
                "replayed": False,
            },
            201,
        )
        with patch(
            "server.auth",
            return_value=("participant", "Actor", "a@example.test"),
        ):
            with patch("server.conn", return_value=c):
                with patch(
                    "server.handle_my_workspace_command",
                    return_value=outcome,
                ) as command:
                    with patch(
                        "server.state",
                        side_effect=AssertionError("global state rendered"),
                    ):
                        payload, status = H.do_POST(h)
        self.assertEqual(status, 201)
        self.assertEqual(payload["note"]["body"], "private")
        command.assert_called_once_with(
            c,
            NOTE_ROUTE,
            "participant",
            "a@example.test",
            {"text": "private", "request_id": "a" * 32},
        )
        self.assertTrue(c.committed)
        self.assertTrue(c.closed)


if __name__ == "__main__":
    unittest.main()
