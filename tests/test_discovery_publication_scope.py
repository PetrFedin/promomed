"""MED-11: no draft/held/demo-only search or saved-item metadata in non-demo.

A public publisher-authorized index does not exist yet. These regression tests
verify a temporary fail-closed boundary, not that publication approval is done.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import discovery_reads, participant_commands
from app.public_discovery_scope import (
    UNADMITTED_DISCOVERY_ROUTES, unpublished_legacy_discovery,
    unavailable_on_non_demo,
)
from server import H


def fake_request(path):
    return SimpleNamespace(
        path=path, out=lambda data, status=200: (data, status)
    )


class DiscoveryPublicationBoundaryTests(unittest.TestCase):
    def test_route_allowlist_is_explicit_and_closed(self):
        self.assertEqual(UNADMITTED_DISCOVERY_ROUTES, frozenset({
            "/api/discovery", "/api/discovery/saved",
            "/api/discovery/save", "/api/discovery/unsave",
        }))
        for path in ("", "/", "/health", "/api/client-365",
                     "/api/partner-collaboration", "/api/discovery-other"):
            self.assertFalse(unpublished_legacy_discovery(path))

    def test_unadmitted_http_discovery_rejects_before_auth_or_db_or_body(self):
        with patch("app.public_discovery_scope.db.demo_seed_enabled",
                   return_value=False):
            with patch("server.auth", side_effect=AssertionError("auth queried")):
                with patch("server.conn", side_effect=AssertionError("DB queried")):
                    with patch("server.body", side_effect=AssertionError("body read")):
                        for path in sorted(UNADMITTED_DISCOVERY_ROUTES):
                            for url in (path, path + "?q=unpublished&kind=transcript"):
                                with self.subTest(url=url):
                                    self.assertTrue(unavailable_on_non_demo(path))
                                    self.assertEqual(
                                        H.do_GET(fake_request(url)),
                                        ({"error": "not_found"}, 404),
                                    )
                                    self.assertEqual(
                                        H.do_POST(fake_request(url)),
                                        ({"error": "not_found"}, 404),
                                    )

    def test_direct_discovery_projection_cannot_bypass_http_gate(self):
        for raw_path in ("/api/discovery?q=on-hold&kind=content",
                         "/api/discovery/saved"):
            with self.subTest(path=raw_path):
                with patch("app.public_discovery_scope.db.demo_seed_enabled",
                           return_value=False):
                    self.assertEqual(
                        discovery_reads.read(None, raw_path, "participant", "a@e.test"),
                        ({"error": "not_found"}, 404),
                    )

    def test_direct_saved_mutations_cannot_bypass_http_gate(self):
        with patch("app.public_discovery_scope.db.demo_seed_enabled",
                   return_value=False):
            for route in ("/api/discovery/save", "/api/discovery/unsave"):
                outcome = participant_commands.handle_command(
                    None, route, "participant", "a@e.test",
                    {"target_kind": "content", "target_ref": "hidden"},
                )
                self.assertEqual(outcome.status, 404)
                self.assertEqual(outcome.payload, {"error": "not_found"})

    def test_demo_read_and_save_authority_semantics_not_relaxed(self):
        with patch("app.public_discovery_scope.db.demo_seed_enabled",
                   return_value=True):
            for path in UNADMITTED_DISCOVERY_ROUTES:
                self.assertFalse(unavailable_on_non_demo(path))
            self.assertEqual(
                discovery_reads.read(None, "/api/discovery/saved", None, None),
                ({"error": "forbidden"}, 403),
            )
            out = participant_commands.handle_command(
                None, "/api/discovery/save", "partner", "partner@demo.ru", {}
            )
            self.assertEqual(out.status, 403)


if __name__ == "__main__":
    unittest.main()
