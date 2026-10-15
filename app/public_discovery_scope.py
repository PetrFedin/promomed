"""Publication-admission gate for the legacy discovery routes.

Legacy search indexes concepts, review-stage content, demo-reviewed transcripts
and held rows before computing facets. Until a verifiably approved public corpus
exists, neither a count nor a title may be exposed by those routes in non-demo.
"""
from app import db

UNADMITTED_DISCOVERY_ROUTES = frozenset({
    "/api/discovery",
    "/api/discovery/saved",
    "/api/discovery/save",
    "/api/discovery/unsave",
})


def unpublished_legacy_discovery(path):
    return isinstance(path, str) and path in UNADMITTED_DISCOVERY_ROUTES


def unavailable_on_non_demo(path):
    return unpublished_legacy_discovery(path) and not db.demo_seed_enabled()
