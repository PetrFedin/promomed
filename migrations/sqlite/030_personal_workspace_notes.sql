-- Personal user text only; no public, medical or commercial approval.
CREATE TABLE IF NOT EXISTS personal_notes_v1 (
    id TEXT PRIMARY KEY CHECK (length(id) = 32),
    email TEXT NOT NULL REFERENCES accounts(email) ON DELETE CASCADE,
    request_key TEXT NOT NULL CHECK (length(request_key) = 32),
    body TEXT NOT NULL,
    created_at BIGINT NOT NULL CHECK (created_at > 0),
    deleted_at BIGINT,
    CHECK ((deleted_at IS NULL AND length(body) BETWEEN 1 AND 2000)
        OR (deleted_at IS NOT NULL AND deleted_at > 0 AND body = '')),
    UNIQUE (email, request_key)
);
CREATE INDEX IF NOT EXISTS personal_notes_v1_owner_page
    ON personal_notes_v1(email, created_at DESC, id DESC);
CREATE TRIGGER IF NOT EXISTS personal_notes_v1_account_delete
AFTER DELETE ON accounts
BEGIN
    DELETE FROM personal_notes_v1 WHERE email=OLD.email;
END;
