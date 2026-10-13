-- Session authority safety for account status and role transitions.
CREATE OR REPLACE FUNCTION promomed_revoke_account_sessions()
RETURNS trigger AS $$
BEGIN
  UPDATE auth_sessions
  SET revoked_at=EXTRACT(EPOCH FROM clock_timestamp())::BIGINT
  WHERE email=OLD.email AND revoked_at IS NULL;
  RETURN COALESCE(NEW,OLD);
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS auth_accounts_role_status_session_revoke ON accounts;
CREATE TRIGGER auth_accounts_role_status_session_revoke
AFTER UPDATE OF role,status ON accounts
FOR EACH ROW
WHEN (OLD.role IS DISTINCT FROM NEW.role OR OLD.status IS DISTINCT FROM NEW.status)
EXECUTE FUNCTION promomed_revoke_account_sessions();
DROP TRIGGER IF EXISTS auth_accounts_delete_session_revoke ON accounts;
CREATE TRIGGER auth_accounts_delete_session_revoke
BEFORE DELETE ON accounts
FOR EACH ROW EXECUTE FUNCTION promomed_revoke_account_sessions();
