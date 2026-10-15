"""P0 SEC-01: global demo dashboards cannot query real tenant data.

This tests the HTTP entrypoint before authentication/connection, in addition to
the pure scope predicate. It is not an assertion that real tenant reporting is
implemented or admitted.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.legacy_report_scope import (
    LEGACY_GLOBAL_REPORT_ROUTES,
    requires_demo_authority,
    unavailable_on_non_demo,
)
from server import H


def fake_request(path):
    return SimpleNamespace(
        path=path,
        out=lambda value, status=200: (value, status),
    )


class LegacyGlobalReportBoundaryTests(unittest.TestCase):
    def test_registry_contains_all_observed_unscoped_reports(self):
        self.assertEqual(LEGACY_GLOBAL_REPORT_ROUTES, frozenset({
            "/api/state",
            "/api/analytics",
            "/api/command",
            "/api/intelligence",
            "/api/investor-proof",
            "/api/executive-room",
            "/api/corporate-readiness",
            "/api/product-quality-proof",
            "/api/continuity-proof",
        }))

    def test_unscoped_reports_require_demo_even_for_any_eligible_role(self):
        paths = sorted(LEGACY_GLOBAL_REPORT_ROUTES | {
            "/api/demo/status",
            "/api/demo/evidence",
            "/api/demo/reset",
            "/api/demo/next",
        })
        with patch("app.legacy_report_scope.db.demo_seed_enabled", return_value=False):
            with patch("server.auth", side_effect=AssertionError("auth DB touched")):
                with patch("server.conn", side_effect=AssertionError("global DB queried")):
                    for path in paths:
                        with self.subTest(path=path):
                            self.assertTrue(requires_demo_authority(path))
                            self.assertTrue(unavailable_on_non_demo(path))
                            self.assertEqual(
                                H.do_GET(fake_request(path)),
                                ({"error": "not_found"}, 404),
                            )
                            self.assertEqual(
                                H.do_POST(fake_request(path)),
                                ({"error": "not_found"}, 404),
                            )

    def test_non_demo_does_not_disable_unrelated_public_and_tenant_routes(self):
        paths = (
            "/", "/health", "/ready", "/api/client-365",
            "/api/partner-collaboration",
            "/api/discovery", "/api/media", "/api/login",
            "/api/analytics-export", "/api/intelligence/other",
        )
        with patch("app.legacy_report_scope.db.demo_seed_enabled", return_value=False):
            for path in paths:
                with self.subTest(path=path):
                    self.assertFalse(requires_demo_authority(path))
                    self.assertFalse(unavailable_on_non_demo(path))

    def test_demo_routes_preserve_legacy_auth_handling(self):
        with patch("app.legacy_report_scope.db.demo_seed_enabled", return_value=True):
            with patch("server.auth", return_value=None):
                for path in (
                    "/api/analytics", "/api/command", "/api/intelligence",
                    "/api/investor-proof", "/api/executive-room",
                    "/api/corporate-readiness",
                    "/api/demo/status", "/api/demo/evidence",
                ):
                    with self.subTest(path=path):
                        self.assertFalse(unavailable_on_non_demo(path))
                        self.assertEqual(
                            H.do_GET(fake_request(path)),
                            ({"error": "forbidden"}, 403),
                        )

    def test_guard_does_not_look_up_production_data_to_choose_policy(self):
        with patch("app.legacy_report_scope.db.demo_seed_enabled",
                   side_effect=AssertionError("demo check should not run")):
            self.assertFalse(unavailable_on_non_demo("/api/client-365"))
            self.assertFalse(unavailable_on_non_demo("/health"))

    def test_query_string_is_normalized_by_http_handler(self):
        with patch("app.legacy_report_scope.db.demo_seed_enabled", return_value=False):
            with patch("server.auth", side_effect=AssertionError("auth DB touched")):
                h = fake_request("/api/intelligence?organization_id=other")
                self.assertEqual(H.do_GET(h), ({"error": "not_found"}, 404))


if __name__ == "__main__":
    unittest.main()
