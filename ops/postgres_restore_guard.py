"""Fail-closed admission guard for PostgreSQL restore targets.

A restore is allowed only to a *new*, explicitly named Promomed restore database.
This guard is read-only: it never creates, cleans or truncates target objects.
"""

import re
from urllib.parse import unquote, urlsplit

from app import db


class UnsafeRestoreTarget(RuntimeError):
    """Raised before pg_restore if the destination cannot be proved safe."""


# In addition to normal URL comparison, inspect the *actual* connected target.
# Reject non-extension relations/functions/foreign objects and custom schemas.
# Extension-owned objects may be pre-installed by a managed PostgreSQL provider.
USER_OBJECTS_SQL = """
WITH user_objects AS (
  SELECT c.oid AS object_id
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
   WHERE c.relkind IN ('r','p','v','m','f','S')
     AND n.nspname NOT LIKE 'pg_%'
     AND n.nspname <> 'information_schema'
     AND NOT EXISTS (
       SELECT 1 FROM pg_catalog.pg_depend d
       WHERE d.classid = 'pg_catalog.pg_class'::regclass
         AND d.objid = c.oid AND d.deptype = 'e'
     )
  UNION ALL
  SELECT p.oid
    FROM pg_catalog.pg_proc p
    JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname NOT LIKE 'pg_%'
     AND n.nspname <> 'information_schema'
     AND NOT EXISTS (
       SELECT 1 FROM pg_catalog.pg_depend d
       WHERE d.classid = 'pg_catalog.pg_proc'::regclass
         AND d.objid = p.oid AND d.deptype = 'e'
     )
  UNION ALL
  SELECT n.oid
    FROM pg_catalog.pg_namespace n
   WHERE n.nspname <> 'public'
     AND n.nspname <> 'information_schema'
     AND n.nspname NOT LIKE 'pg_%'
)
SELECT COUNT(*)::bigint FROM user_objects
"""


def _endpoint(url):
    """Parse unambiguous libpq URLs without printing credentials."""
    if not url:
        raise UnsafeRestoreTarget("source and target PostgreSQL URLs are required")
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ("postgres", "postgresql"):
            raise UnsafeRestoreTarget("PostgreSQL URL scheme required")
        if not parsed.hostname or not parsed.path or parsed.path == "/":
            raise UnsafeRestoreTarget("explicit PostgreSQL hostname and database name required")
        if parsed.port is not None and parsed.port <= 0:
            raise UnsafeRestoreTarget("invalid PostgreSQL port")
        database_name = unquote(parsed.path[1:])
        if "/" in database_name or not database_name:
            raise UnsafeRestoreTarget("unambiguous PostgreSQL database name required")
        # Query overrides could make the real destination different from URL path.
        forbidden = ("host=", "hostaddr=", "port=", "dbname=", "service=")
        lowered = parsed.query.lower()
        if any(re.search(r"(?:^|&)" + re.escape(k), lowered) for k in forbidden):
            raise UnsafeRestoreTarget("connection parameter override not allowed for restore")
        return (parsed.hostname.lower(), parsed.port or 5432, database_name)
    except UnsafeRestoreTarget:
        raise
    except (TypeError, ValueError) as exc:
        raise UnsafeRestoreTarget("invalid PostgreSQL connection URL") from None


def require_empty_isolated_restore_target(source_url, target_url, connector=None):
    """Ensure an explicitly isolated *empty* target before any write.

    This does not replace operator verification that the target is dedicated to
    Promomed. Restrict access to the restore database and avoid concurrent writers.
    """
    source = _endpoint(source_url)
    target = _endpoint(target_url)
    if source == target:
        raise UnsafeRestoreTarget("source and restore URLs resolve to the same endpoint/database")
    if not re.fullmatch(r"promomed[a-z0-9_-]*restore", target[2].lower()):
        raise UnsafeRestoreTarget("restore database name must start with promomed and end with restore")
    if db.psycopg is None and connector is None:
        raise UnsafeRestoreTarget("psycopg is required to verify restore target")

    connect = connector or db.psycopg.connect
    try:
        with connect(target_url, connect_timeout=10) as c:
            with c.cursor() as cur:
                cur.execute("SELECT current_database()")
                actual_database = cur.fetchone()[0]
                if actual_database != target[2]:
                    raise UnsafeRestoreTarget("connected restore database differs from URL database")
                cur.execute(USER_OBJECTS_SQL)
                user_objects = int(cur.fetchone()[0])
    except UnsafeRestoreTarget:
        raise
    except Exception:
        # Do not leak DSNs, authentication errors, server names or passwords.
        raise UnsafeRestoreTarget("restore target inspection failed; restore refused") from None

    if user_objects != 0:
        raise UnsafeRestoreTarget("restore target contains user objects; restore refused")
    return {"ok": True, "target_empty": True, "target_database": actual_database}
