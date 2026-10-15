"""Deterministic transport regressions plus real local socket reads."""

import io
import socket
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.request_body_io import (
    BODY_READ_CHUNK_BYTES, BodyReadError, BodyReadTimeout, read_exact_body,
)


class FakeConnection:
    def __init__(self, timeout=None):
        self.timeout = timeout
        self.values = []

    def gettimeout(self):
        return self.timeout

    def settimeout(self, value):
        self.values.append(value)
        self.timeout = value


class AdvancingStream:
    def __init__(self, clock, chunks, duration):
        self.clock = clock
        self.chunks = iter(chunks)
        self.duration = duration
        self.requests = []

    def read1(self, size):
        self.requests.append(size)
        self.clock[0] += self.duration
        return next(self.chunks, b"")

    def read(self, _size):
        raise AssertionError("unbounded BufferedReader.read used")


class BodyDeadlineTests(unittest.TestCase):
    def test_zero_body_never_reads_or_touches_socket(self):
        self.assertEqual(read_exact_body(SimpleNamespace(), 0), b"")

    def test_invalid_size_rejected(self):
        for size in (-1, True, "2", None):
            with self.subTest(size=size), self.assertRaises(ValueError):
                read_exact_body(SimpleNamespace(), size)

    def test_memory_stream_compatibility(self):
        self.assertEqual(read_exact_body(SimpleNamespace(rfile=io.BytesIO(b"{}")), 2), b"{}")

    def test_total_deadline_is_not_reset_by_progress(self):
        now = [0.0]
        stream = AdvancingStream(now, [b"a"] * 20, 1.0)
        connection = FakeConnection()
        h = SimpleNamespace(rfile=stream, connection=connection)
        with self.assertRaisesRegex(BodyReadTimeout, "body_read_timeout"):
            read_exact_body(h, 20, clock=lambda: now[0])
        self.assertEqual(now[0], 10.0)
        self.assertEqual(len(stream.requests), 10)
        self.assertEqual(connection.values[-2:], [1.0, None])
        self.assertTrue(h.close_connection)

    def test_deadline_is_monotonic_and_wall_clock_independent(self):
        h = SimpleNamespace(rfile=io.BytesIO(b"{}"))
        with patch("app.request_body_io.time.time", side_effect=AssertionError("wall clock")):
            self.assertEqual(read_exact_body(h, 2), b"{}")

    def test_previous_shorter_socket_timeout_is_not_relaxed(self):
        connection = FakeConnection(0.05)
        h = SimpleNamespace(rfile=io.BytesIO(b"{}"), connection=connection)
        self.assertEqual(read_exact_body(h, 2), b"{}")
        self.assertEqual(connection.values, [0.05, 0.05])
        self.assertFalse(getattr(h, "close_connection", False))

    def test_longer_socket_timeout_restored_after_success(self):
        connection = FakeConnection(60.0)
        h = SimpleNamespace(rfile=io.BytesIO(b"{}"), connection=connection)
        self.assertEqual(read_exact_body(h, 2), b"{}")
        self.assertEqual(connection.values, [5.0, 60.0])

    def test_chunk_size_and_declared_size_are_bounded(self):
        sizes = []
        class Stream:
            def read1(self, size):
                sizes.append(size)
                return b"a" * size
        total = BODY_READ_CHUNK_BYTES * 2 + 3
        self.assertEqual(len(read_exact_body(SimpleNamespace(rfile=Stream()), total)), total)
        self.assertEqual(sizes, [BODY_READ_CHUNK_BYTES, BODY_READ_CHUNK_BYTES, 3])

    def test_body_reader_never_consumes_next_message(self):
        stream = io.BytesIO(b"{}NEXT")
        self.assertEqual(read_exact_body(SimpleNamespace(rfile=stream), 2), b"{}")
        self.assertEqual(stream.read(), b"NEXT")

    def test_eof_closes_connection_and_restores_timeout(self):
        connection = FakeConnection(30.0)
        h = SimpleNamespace(rfile=io.BytesIO(b"{"), connection=connection)
        with self.assertRaisesRegex(BodyReadError, "incomplete_json_body"):
            read_exact_body(h, 2)
        self.assertTrue(h.close_connection)
        self.assertEqual(connection.timeout, 30.0)

    def test_invalid_stream_fails_closed(self):
        for value in (None, "text", b"too long"):
            with self.subTest(value=value):
                h = SimpleNamespace(rfile=SimpleNamespace(read1=lambda _: value))
                with self.assertRaisesRegex(BodyReadError, "invalid_body_stream"):
                    read_exact_body(h, 1)
                self.assertTrue(h.close_connection)

    def test_read_only_stream_not_accepted_as_deadline_safe(self):
        h = SimpleNamespace(rfile=SimpleNamespace(read=lambda _: b"{}"))
        with self.assertRaisesRegex(BodyReadError, "unsupported_body_stream"):
            read_exact_body(h, 2)
        self.assertTrue(h.close_connection)

    def test_transport_errors_do_not_expose_details(self):
        for exc, expected in ((TimeoutError("SECRET"), "body_read_timeout"),
                              (ConnectionResetError("SECRET"), "body_connection_closed")):
            class Stream:
                def read1(self, _size):
                    raise exc
            h = SimpleNamespace(rfile=Stream(), connection=FakeConnection(40.0))
            with self.subTest(exc=type(exc)), self.assertRaisesRegex(BodyReadError, "^" + expected + "$"):
                read_exact_body(h, 2)
            self.assertTrue(h.close_connection)
            self.assertEqual(h.connection.timeout, 40.0)

    def test_closed_socket_during_restore_does_not_mask_error(self):
        class Connection(FakeConnection):
            def settimeout(self, value):
                if value == 40.0:
                    raise OSError("closed")
                super().settimeout(value)
        h = SimpleNamespace(rfile=io.BytesIO(b""), connection=Connection(40.0))
        with self.assertRaisesRegex(BodyReadError, "incomplete_json_body"):
            read_exact_body(h, 2)

    def test_actual_socket_idle_timeout_and_connection_close_flag(self):
        client, server = socket.socketpair()
        with client, server, server.makefile("rb") as stream:
            h = SimpleNamespace(rfile=stream, connection=server)
            client.sendall(b"{")
            started = time.monotonic()
            with patch("app.request_body_io.BODY_IDLE_TIMEOUT_SECONDS", 0.06), patch("app.request_body_io.BODY_TOTAL_TIMEOUT_SECONDS", 0.5):
                with self.assertRaises(BodyReadTimeout):
                    read_exact_body(h, 2)
            self.assertLess(time.monotonic() - started, 2.0)
            self.assertTrue(h.close_connection)
            self.assertIsNone(server.gettimeout())

    def test_actual_socket_trickle_cannot_extend_total_deadline(self):
        client, server = socket.socketpair()
        stop = threading.Event()
        def feed():
            while not stop.is_set():
                try:
                    client.sendall(b"x")
                except OSError:
                    return
                stop.wait(0.01)
        with client, server, server.makefile("rb") as stream:
            h = SimpleNamespace(rfile=stream, connection=server)
            sender = threading.Thread(target=feed, daemon=True)
            sender.start()
            started = time.monotonic()
            try:
                with patch("app.request_body_io.BODY_IDLE_TIMEOUT_SECONDS", 0.15), patch("app.request_body_io.BODY_TOTAL_TIMEOUT_SECONDS", 0.25):
                    with self.assertRaises(BodyReadTimeout):
                        read_exact_body(h, 10000)
                self.assertLess(time.monotonic() - started, 2.0)
                self.assertTrue(h.close_connection)
            finally:
                stop.set()
                sender.join(1)
                self.assertFalse(sender.is_alive())


if __name__ == "__main__":
    unittest.main()
