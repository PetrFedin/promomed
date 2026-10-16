"""Fail-closed registry for legacy global/shared-capacity mutations.

These routes are not admitted in non-demo authority until they receive explicit
tenant/event scope and negative cross-scope qualification. New versioned
production routes must NOT be added here; they require their own authority.
"""
from app import db

LEGACY_GLOBAL_WRITE_ROUTES=frozenset({
    # Global operations / venue / demo staff controls.
    "/api/move-session",
    "/api/live",
    "/api/checkin",
    "/api/staff-assignment",
    "/api/speaker-readiness",
    "/api/broadcast",
    "/api/venue-state",
    "/api/incident",
    "/api/stream-control",
    "/api/venue",
    "/api/phase",
    # Partner singleton/global writes.
    "/api/placement",
    "/api/lead",
    "/api/appointment-booking",
    "/api/appointment-manage",
    # Legacy participant programme writes lacking admitted event authority.
    "/api/register",
    "/api/booking",
    "/api/replay",
    "/api/session-attendance",
})


def requires_demo_authority(path):
    return isinstance(path,str) and path in LEGACY_GLOBAL_WRITE_ROUTES


def unavailable_on_non_demo(path):
    return requires_demo_authority(path) and not db.demo_seed_enabled()
