-- Session authority safety: changes of role, status or account deletion
-- invalidate existing sessions immediately. No new provider or network action.
CREATE TRIGGER IF NOT EXISTS auth_accounts_role_status_session_revoke
AFTER UPDATE OF role,status ON accounts
WHEN NEW.role IS NOT OLD.role OR NEW.status IS NOT OLD.status
BEGIN
  UPDATE auth_sessions SET revoked_at=CAST(strftime('%s','now') AS INTEGER)
  WHERE email=OLD.email AND revoked_at IS NULL;
END;
CREATE TRIGGER IF NOT EXISTS auth_accounts_delete_session_revoke
BEFORE DELETE ON accounts
BEGIN
  UPDATE auth_sessions SET revoked_at=CAST(strftime('%s','now') AS INTEGER)
  WHERE email=OLD.email AND revoked_at IS NULL;
END;
