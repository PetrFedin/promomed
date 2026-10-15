"""Real loopback HTTP, actual H/body; DB/auth mocks prove pre-auth rejection.

These tests are not live non-demo identity or production capacity admission.
"""

import json
import socket
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import Mock, patch

from app.auth import MAX_JSON_BODY_BYTES
from server import H


class QuietHandler(H):
    def log_message(self, *_args):
        pass


class HttpBodyDeadlineIntegrationTests(unittest.TestCase):
    def setUp(self):
        for target, value in (
            ("app.request_body_io.BODY_TOTAL_TIMEOUT_SECONDS", 0.25),
            ("app.request_body_io.BODY_IDLE_TIMEOUT_SECONDS", 0.12),
        ):
            guard = patch(target, value)
            guard.start()
            self.addCleanup(guard.stop)
        guard = patch("server.conn", side_effect=AssertionError("DB touched before body validation"))
        self.conn = guard.start()
        self.addCleanup(guard.stop)
        guard = patch("server.authenticate", side_effect=AssertionError("authentication before validation"))
        self.authenticate = guard.start()
        self.addCleanup(guard.stop)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(2)
        self.assertFalse(self.thread.is_alive())

    def connect(self, length, initial=b"", extra=b""):
        client = socket.create_connection(self.httpd.server_address, timeout=2)
        self.addCleanup(client.close)
        header = b"POST /api/login HTTP/1.1\r\nHost: localhost\r\nContent-Length: " + str(length).encode() + b"\r\n" + extra + b"\r\n"
        client.sendall(header + initial)
        return client

    def response(self, client):
        chunks = []
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
        status, body = b"".join(chunks).split(b"\r\n\r\n", 1)
        return int(status.split(b" ", 2)[1]), json.loads(body)

    def assert_rejected_before_auth(self, client, status=400, error="bad_json"):
        self.assertEqual(self.response(client), (status, {"error": error}))
        self.conn.assert_not_called()
        self.authenticate.assert_not_called()

    def test_idle_body_is_closed_without_database_or_authentication(self):
        started = time.monotonic()
        self.assert_rejected_before_auth(self.connect(20, b"{"))
        self.assertLess(time.monotonic() - started, 2)

    def test_trickle_body_hits_total_deadline_not_renewable_idle_timeout(self):
        client = self.connect(10000, b"{")
        stop = threading.Event()
        def feed():
            while not stop.wait(0.01):
                try:
                    client.sendall(b" ")
                except OSError:
                    return
        sender = threading.Thread(target=feed, daemon=True)
        sender.start()
        started = time.monotonic()
        try:
            self.assert_rejected_before_auth(client)
            self.assertLess(time.monotonic() - started, 2)
        finally:
            stop.set()
            sender.join(1)
            self.assertFalse(sender.is_alive())

    def test_oversized_body_still_rejected_without_waiting_for_payload(self):
        self.assert_rejected_before_auth(self.connect(MAX_JSON_BODY_BYTES + 1), 413, "request_body_too_large")

    def test_duplicate_content_length_still_rejected(self):
        self.assert_rejected_before_auth(self.connect(2, extra=b"Content-Length: 2\r\n"))

    def test_truncated_body_fails_closed_when_client_half_closes(self):
        client = self.connect(3, b"{}")
        client.shutdown(socket.SHUT_WR)
        self.assert_rejected_before_auth(client)

    def test_malformed_json_still_rejected(self):
        self.assert_rejected_before_auth(self.connect(2, b"[]"))

    def test_complete_normal_body_reaches_existing_login_path(self):
        payload = json.dumps({"email": "fixture@example.test", "password": "synthetic-invalid"}).encode()
        connection = Mock()
        with patch("server.conn", return_value=connection), patch("server.authenticate", return_value=None) as authenticate:
            self.assertEqual(self.response(self.connect(len(payload), payload)), (401, {"error": "invalid_credentials"}))
        authenticate.assert_called_once_with(connection, "fixture@example.test", "synthetic-invalid")
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
