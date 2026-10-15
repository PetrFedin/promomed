"""Fail-closed boundary for unscoped legacy aggregate/report HTTP routes.

This pre-tenant set reads application-wide tables and must NEVER be interpreted
as an organization-scoped report. Production reporting requires new, separately
reviewed membership-scoped projections; this gate is not a tenant implementation.
"""
from app import db

LEGACY_GLOBAL_REPORT_ROUTES = frozenset({
    "/api/state",
    "/api/analytics",
    "/api/command",
    "/api/intelligence",
    "/api/investor-proof",
    "/api/executive-room",
    "/api/corporate-readiness",
    "/api/product-quality-proof",
    "/api/continuity-proof",
})


def requires_demo_authority(path):
    """Exact legacy report routes and the explicit demo namespace only."""
    return isinstance(path, str) and (
        path in LEGACY_GLOBAL_REPORT_ROUTES or path.startswith("/api/demo/")
    )


def unavailable_on_non_demo(path):
    """Reject before auth/DB dispatch without revealing route or tenant data."""
    return requires_demo_authority(path) and not db.demo_seed_enabled()
