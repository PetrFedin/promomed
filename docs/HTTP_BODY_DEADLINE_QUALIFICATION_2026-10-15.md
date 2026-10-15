# HTTP body deadline qualification — 2026-10-15

Status: candidate only; independent review and exact-HEAD CI required. No release admission.

## Origin and finding

Stacked on Draft PR #93, exact source `bf20b439ef3a773cfa120848704bad22ecb49dc2`. Its five existing workflow runs completed successfully before this patch. No independent PR review was present at inspection. Draft #92/#93 and infrastructure #64/#65 remain separate gates.

`app.auth.body()` previously called `h.rfile.read(n)` after checking the 4 MiB limit. Size validation did not give the body read a whole-request deadline. A single socket timeout around BufferedReader.read(n) would still permit repeated successful raw reads to extend total occupancy.

## Implementation

- New `app/request_body_io.py`, invoked directly by `app.auth.body`; no monkey patch or startup command changes.
- Selected guard defaults: 10 seconds for the complete body, 5 seconds maximum idle raw read, 64 KiB maximum read1 chunk. These are implementation limits, not measured production SLOs or throughput claims.
- One monotonic deadline is shared by all chunks. Each raw read gets the remaining deadline or shorter existing socket timeout. Progress never resets the total deadline.
- Uses `read1`, not a potentially multi-read buffered `read`. Reads exactly the declared byte count, never the next message. Zero-length legacy POSTs still parse as `{}`.
- Timeout, disconnect, invalid stream and premature EOF mark the connection for closure before any login authentication. Socket settings are restored without leaking transport exception details.
- Existing generic HTTP 400 `bad_json` response is deliberately retained for read failures. Oversized declared bodies still return 413 before reading. This patch does not introduce HTTP 408.
- The existing 4 MiB size boundary, demo/production segregation, role/session rules, schema and server source-line budget are unchanged.

## Evidence and scope

- 16 unique deterministic/in-memory/real-socket unit tests passed in the isolated local container before submission.
- 7 additional integration tests use the actual server.H and actual loopback HTTP sockets; DB/auth test doubles assert rejection before authority access. These require the full repository CI checkout; no local full-app pass is claimed.
- Dedicated `Promomed HTTP body transport` PR workflow runs those 23 new tests plus the existing 18 request-envelope/demo-boundary tests, preserving the log as an artifact. A green result must be verified on the exact candidate SHA, not inferred from this document.
- Five existing UI/browser/persistence/Render-contract workflow conclusions must also be verified on the same candidate. Source code may pass while external release admission remains HOLD.

## Deliberately not solved

Request-line/header timeouts, a bounded worker/connection pool, edge admission/rate limiting, login-attempt throttling, credential scanning, shared multi-instance limits and measured production load are not implemented or proven here. The Python http.server documentation explicitly warns against treating it as a production security boundary. Do not market this patch as complete slow-client or denial-of-service protection.

External authenticated non-demo browser journeys, dedicated isolated PostgreSQL with restore proof (#65), existing Render reconciliation (#64), repository protection (#94), independent reviewer sign-off and owner release approval remain required. No main merge, Render update, production DB write, secret or paid service was created by this patch. GitHub Actions usage quota/cost was not independently audited.

Reference semantics: Python documentation for io.BufferedReader.read1, socket.settimeout, and http.server security considerations. The body deadline begins after headers have been parsed; it does not bound header parsing or total request processing.
