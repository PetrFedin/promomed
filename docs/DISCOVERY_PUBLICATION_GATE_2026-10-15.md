# MED-11 — Public Discovery Publication-Safety Gate (2026-10-15)

**Candidate status:** Draft source-only security gate stacked after PR #96, #93, #92. This is not a live publish or a verified medical-content pipeline.

## Source-verified prior behavior
- `app/discovery._index()` included `content_catalog` items regardless of `status` (`concept`, `review`, `published`), `studio_episodes`, partner/product profiles, and even `reviewed_demo` transcript segments.
- `app/discovery.search()` returned held content titles and excerpts while setting `publication_hold=true`, then constructed facets and count totals from the unfiltered index.
- `app/discovery_reads.read()` accepted anonymous `/api/discovery` with query selectors including review status and media type.
- Saved items and `/api/discovery/save` could continue to expose legacy titles/existence to the current participant. A visual warning was not a substitute for publication approval.

## Exact scoped change
The four legacy entrypoints `GET /api/discovery`, `GET /api/discovery/saved`, `POST /api/discovery/save`, `POST /api/discovery/unsave` are unavailable in non-demo authority until independent publisher/medical/legal approval is implemented. HTTP fails closed at the entrypoint before authentication, SQL or JSON body reading, and direct read/command module calls enforce the same restriction. The repository's existing demo mode remains unchanged; no synthetic evidence is promoted.

**Deliberate UX gap:** a genuine pilot's search/saved journey is blocked by this candidate. Do NOT interpret a PostgreSQL-ready `/ready` as public-content readiness. Reuse of `/api/discovery` without admission would re-expose in-review and held text.

## Required positive replacement — Issue #98
- Build a new versioned approved-public index **from an authorization-filtered SQL source**, not `_index` followed by a UI flag.
- Include only approved, rights-cleared, not-held, not-retracted public versions; require medical/editorial reviewer identity and disclosure before claims enter the corpus.
- Compute all keyword hits, autocomplete, `total`, pagination, topic/facet counts and saved-item projections from *the same filtered corpus*, so hidden records cannot be inferred.
- Support source change impact, immediate publication hold/retraction, revoked permissions and observer consistency.
- Prove negative source cases, verified reviewer/hold changes and 7-viewport browser UX on SQLite and PostgreSQL 17; independently review every new content family before exposing it.
- Coordinate tenant-scoped public/participant/organization state from Issue #97 and external admission Issues #64/#65, with #94 main rules and full release review.

**No new DB, paid resources, production deployment, live medical advice or customer data processing.**
