"""Bounded POST-body transport reads; not an edge/server admission substitute."""

import time

BODY_TOTAL_TIMEOUT_SECONDS = 10.0
BODY_IDLE_TIMEOUT_SECONDS = 5.0
BODY_READ_CHUNK_BYTES = 64 * 1024


class BodyReadError(ValueError):
    """A request body could not be completely and safely read."""


class BodyReadTimeout(BodyReadError):
    """The idle timeout or whole-body deadline was exceeded."""


def read_exact_body(handler, size, *, clock=None):
    """Read exactly size bytes without renewing the total deadline per chunk.

    A real socket-backed BufferedReader must use read1: read(n) can perform
    multiple raw reads and keep a trickling client alive indefinitely. BytesIO
    also implements read1 for existing in-memory command-envelope tests.
    This function neither parses headers nor raises the JSON byte-size limit.
    """
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise ValueError("invalid_body_size")
    if size == 0:
        return b""
    clock = time.monotonic if clock is None else clock
    connection = getattr(handler, "connection", None)
    previous_timeout = None
    restore_timeout = False
    try:
        reader = getattr(handler.rfile, "read1", None)
        if not callable(reader):
            raise BodyReadError("unsupported_body_stream")
        if connection is not None:
            previous_timeout = connection.gettimeout()
            restore_timeout = True
        deadline = clock() + BODY_TOTAL_TIMEOUT_SECONDS
        payload = bytearray()
        while len(payload) < size:
            remaining = deadline - clock()
            if remaining <= 0:
                raise BodyReadTimeout("body_read_timeout")
            if connection is not None:
                timeout = min(BODY_IDLE_TIMEOUT_SECONDS, remaining)
                if previous_timeout is not None:
                    timeout = min(timeout, previous_timeout)
                connection.settimeout(timeout)
            wanted = min(BODY_READ_CHUNK_BYTES, size - len(payload))
            chunk = reader(wanted)
            if clock() >= deadline:
                raise BodyReadTimeout("body_read_timeout")
            if not isinstance(chunk, bytes) or len(chunk) > wanted:
                raise BodyReadError("invalid_body_stream")
            if not chunk:
                raise BodyReadError("incomplete_json_body")
            payload.extend(chunk)
        return bytes(payload)
    except TimeoutError:
        handler.close_connection = True
        raise BodyReadTimeout("body_read_timeout") from None
    except OSError:
        handler.close_connection = True
        raise BodyReadError("body_connection_closed") from None
    except BodyReadError:
        handler.close_connection = True
        raise
    finally:
        if restore_timeout:
            try:
                connection.settimeout(previous_timeout)
            except OSError:
                # A disconnected client must not hide the original safe error.
                pass
