"""Security boundary for POST JSON envelopes (no live service or DB required)."""

import io
import json
import unittest
from unittest.mock import patch
from email.message import Message
from types import SimpleNamespace

from app.auth import (
    MAX_JSON_BODY_BYTES, RequestBodyError, RequestBodyTooLarge, body,
)
from server import H


class ExplodingRead:
    """An oversized request must be rejected before reading its body."""
    def read(self, *_args):
        raise AssertionError("oversized body was read")


def request(payload=b"", *, content_length=None, extra_headers=(), stream=None):
    headers = Message()
    if content_length is not None:
        headers["Content-Length"] = str(content_length)
    for key, value in extra_headers:
        headers[key] = value
    return SimpleNamespace(
        headers=headers, rfile=stream if stream is not None else io.BytesIO(payload),
        path="/api/login",
        out=lambda value, status=200: (value, status),
    )


class JsonEnvelopeBoundaryTests(unittest.TestCase):
    def test_legacy_empty_post_without_length_keeps_empty_object(self):
        self.assertEqual(body(request()), {})

    def test_valid_unicode_object(self):
        data = {"title": "СОСТОЯНИЕ", "count": 0, "value": None}
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.assertEqual(body(request(payload, content_length=len(payload))), data)

    def test_limit_is_inclusive(self):
        payload = b"{}" + b" " * (MAX_JSON_BODY_BYTES - 2)
        self.assertEqual(body(request(payload, content_length=len(payload))), {})

    def test_oversized_body_is_rejected_before_reading(self):
        oversized = request(
            content_length=MAX_JSON_BODY_BYTES + 1, stream=ExplodingRead()
        )
        with self.assertRaises(RequestBodyTooLarge):
            body(oversized)
        self.assertEqual(
            H.do_POST(oversized),
            ({"error": "request_body_too_large"}, 413),
        )

    def test_malformed_content_lengths_are_rejected(self):
        for length in ("-1", "+2", "1.0", "NaN", "1,2", " ", "1" * 11):
            with self.subTest(length=length), self.assertRaises(RequestBodyError):
                body(request(b"{}", content_length=length))

    def test_duplicate_content_length_rejected(self):
        duplicated = request(
            b"{}", content_length=2, extra_headers=[("Content-Length", "2")]
        )
        with self.assertRaises(RequestBodyError):
            body(duplicated)

    def test_transfer_encoding_not_supported(self):
        chunked = request(extra_headers=[("Transfer-Encoding", "chunked")])
        with self.assertRaises(RequestBodyError):
            body(chunked)

    def test_truncated_body_fails_closed(self):
        with self.assertRaisesRegex(RequestBodyError, "incomplete_json_body"):
            body(request(b"{}", content_length=3))

    def test_non_json_and_non_object_inputs_rejected(self):
        for payload in (b"[1]", b"null", b"true", b"4", b'"string"',
                        b"{", b"\xff"):
            with self.subTest(payload=payload):
                with self.assertRaises(RequestBodyError):
                    body(request(payload, content_length=len(payload)))

    def test_nested_json_parser_depth_is_rejected(self):
        deeply_nested = b"[" * 2000 + b"0" + b"]" * 2000
        h = request(deeply_nested, content_length=len(deeply_nested))
        self.assertEqual(H.do_POST(h), ({"error": "bad_json"}, 400))

    def test_bad_json_uses_400_without_auth_or_db_access(self):
        bad = request(b"[]", content_length=2)
        self.assertEqual(H.do_POST(bad), ({"error": "bad_json"}, 400))


class DemoEndpointTruthBoundaryTests(unittest.TestCase):
    def test_non_demo_get_does_not_expose_cross_tenant_event_history(self):
        with patch("app.db.demo_seed_enabled", return_value=False):
            with patch("server.conn", side_effect=AssertionError("demo data accessed")):
                for route, role in (
                    ("/api/demo/status", "sales"),
                    ("/api/demo/evidence", "partner"),
                ):
                    # Even an otherwise eligible authenticated role cannot use
                    # an unscoped demo projection in the real-data authority.
                    with self.subTest(route=route), patch(
                        "server.auth",
                        return_value=(role, "Authorized Actor", "actor@example.test"),
                    ):
                        h = request()
                        h.path = route
                        self.assertEqual(
                            H.do_GET(h), ({"error": "not_found"}, 404)
                        )

    def test_non_demo_post_reset_or_step_never_reads_body(self):
        with patch("app.db.demo_seed_enabled", return_value=False):
            for route in ("/api/demo/reset", "/api/demo/next"):
                with self.subTest(route=route):
                    h = request(stream=ExplodingRead())
                    h.path = route
                    self.assertEqual(H.do_POST(h), ({"error": "not_found"}, 404))

    def test_direct_demo_command_rejects_even_organizer_without_demo_seed(self):
        from app import demo_commands

        with patch("app.db.demo_seed_enabled", return_value=False):
            for route in ("/api/demo/reset", "/api/demo/next"):
                result = demo_commands.handle_command(
                    None, route, "organizer", "organizer@example.test", {}
                )
                self.assertEqual(result.status, 404)
                self.assertEqual(result.payload, {"error": "not_found"})

    def test_demo_mode_still_rejects_unauthorized_roles(self):
        from app import demo_commands

        with patch("app.db.demo_seed_enabled", return_value=True):
            h = request()
            h.path = "/api/demo/evidence"
            self.assertEqual(H.do_GET(h), ({"error": "forbidden"}, 403))
            result = demo_commands.handle_command(
                None, "/api/demo/reset", "participant",
                "participant@demo.ru", {},
            )
            self.assertEqual(result.status, 403)


if __name__ == "__main__":
    unittest.main()
