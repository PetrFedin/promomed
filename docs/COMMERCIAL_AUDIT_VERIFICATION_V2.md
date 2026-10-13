# Commercial Evidence — Audit Verification v2

This internal-only verifier checks immutable candidate contract and event documents in Promomed. It does NOT validate external signatures, a bank statement, a legal invoice or recognized revenue.

Prior verifier compared the audit hash chain to the stored `payload_sha256` column. It could therefore miss a change to an underlying monetary or lineage field if the stored payload hash was not recomputed.

The new verifier reconstructs canonical payloads from actual stored fields, recomputes SHA-256, validates deterministic document and audit identifiers, checks matching organization demo scope and recording actor, detects duplicate audit entries and missing audit coverage.

Adversarial tests tamper with a contract amount, invoice amount and audit suffix after disabling SQLite triggers in an isolated fixture. Each must produce an invalid verification outcome, followed by rollback.

Limits: a privileged database operator may still rewrite and re-anchor a complete consistent history. Independent signed records, secured external hash anchoring, timestamp proof, immutable retention and separate Finance acceptance are required before reliance for investors. Actual revenue, cash, invoice and contribution metrics remain NULL/not verified. This module is not exposed for external financial writes.

Dependency: PR #88 stacked after #87 → #84 → #80 → #77; no merge or deployment before exact-head CI and review. Render #64 and PostgreSQL #65 remain production blockers.
