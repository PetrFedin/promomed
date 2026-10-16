"""SEC-11: legacy global/shared-capacity writes are demo-only."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import legacy_write_scope
from app import operations_commands, partner_commands, programme_commands
from server import H


class ExplodingRead:
    def read(self,*_):
        raise AssertionError("request body read")


def request(path):
    return SimpleNamespace(
        path=path,
        rfile=ExplodingRead(),
        headers={},
        out=lambda value,status=200:(value,status),
    )


class LegacyWriteScopeTests(unittest.TestCase):
    def test_registry_is_exact_and_versioned_routes_are_not_denied(self):
        self.assertEqual(len(legacy_write_scope.LEGACY_GLOBAL_WRITE_ROUTES),20)
        for route in (
            "/api/my-state/v1/notes",
            "/api/event-registration/v1",
            "/api/participant-registration/v1/request",
            "/api/participant-registration/v1/verify",
            "/api/public-state/v1",
            "/api/partner-collaboration",
        ):
            with self.subTest(route=route):
                self.assertFalse(legacy_write_scope.requires_demo_authority(route))

    def test_non_demo_http_denies_every_legacy_write_before_body_auth_or_db(self):
        with patch("app.legacy_write_scope.db.demo_seed_enabled",return_value=False):
            with patch("server.auth",side_effect=AssertionError("auth touched")):
                with patch("server.conn",side_effect=AssertionError("DB opened")):
                    for route in sorted(legacy_write_scope.LEGACY_GLOBAL_WRITE_ROUTES):
                        with self.subTest(route=route):
                            self.assertEqual(
                                H.do_POST(request(route)),
                                ({"error":"not_found"},404),
                            )

    def test_query_string_cannot_bypass_exact_path_guard(self):
        with patch("app.legacy_write_scope.db.demo_seed_enabled",return_value=False):
            h=request("/api/lead?organization=other")
            self.assertEqual(H.do_POST(h),({"error":"not_found"},404))

    def test_direct_domain_handlers_cannot_bypass_non_demo_gate(self):
        cases=(
            (operations_commands.handle_command,"/api/venue","organizer"),
            (operations_commands.handle_command,"/api/checkin","staff"),
            (partner_commands.handle_command,"/api/placement","partner"),
            (partner_commands.handle_command,"/api/lead","participant"),
            (partner_commands.handle_command,"/api/appointment-booking","participant"),
            (programme_commands.handle_command,"/api/booking","participant"),
            (programme_commands.handle_command,"/api/activity-booking","participant"),
            (programme_commands.handle_command,"/api/session-attendance","staff"),
            (programme_commands.handle_command,"/api/replay","participant"),
        )
        with patch("app.legacy_write_scope.db.demo_seed_enabled",return_value=False):
            for handler,route,role in cases:
                with self.subTest(route=route):
                    outcome=handler(
                        None,route,role,role+"@example.test",{}
                    )
                    self.assertEqual(outcome.status,404)
                    self.assertEqual(outcome.payload,{"error":"not_found"})

    def test_demo_mode_preserves_existing_role_checks(self):
        with patch("app.legacy_write_scope.db.demo_seed_enabled",return_value=True):
            outcome=operations_commands.handle_command(
                None,"/api/venue","participant","p@demo.ru",{}
            )
            self.assertEqual(outcome.status,403)
            outcome=partner_commands.handle_command(
                None,"/api/placement","participant","p@demo.ru",{}
            )
            self.assertEqual(outcome.status,403)
            outcome=programme_commands.handle_command(
                None,"/api/booking","partner","partner@demo.ru",{}
            )
            self.assertEqual(outcome.status,403)


if __name__=="__main__":
    unittest.main()
