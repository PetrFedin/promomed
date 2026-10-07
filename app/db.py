import hashlib
import os
import re
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_ROOT = ROOT / "migrations"

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SQLITE_PATH = os.environ.get("SQLITE_PATH", "/tmp/sostoyanie.db")

try:
    import psycopg
    from psycopg.rows import dict_row
    _PG_INTEGRITY = psycopg.IntegrityError
except Exception:
    psycopg = None
    dict_row = None

    class _PG_INTEGRITY(Exception):
        pass

INTEGRITY_ERRORS = (sqlite3.IntegrityError, _PG_INTEGRITY)

REPLACE_KEYS = {
    "speakers": ("id",),
    "product_catalog": ("id",),
    "content_catalog": ("id",),
    "partner_packages": ("id",),
    "community_threads": ("id",),
    "learning_tracks": ("id",),
    "learning_steps": ("track_id", "step_no"),
    "studio_episodes": ("id",),
    "registrations": ("email",),
    "bookings": ("email", "session_id"),
    "journeys": ("email",),
}

SERIAL_TABLES = (
    "leads",
    "questions",
    "placements",
    "meetings",
    "session_feedback",
    "takeaways",
    "product_interests",
    "followups",
    "community_posts",
    "mutual_meetings",
    "incidents",
    "appointment_history",
    "partner_engagement",
    "staff_assignments",
    "ops_broadcasts",
    "notifications",
    "direct_messages",
    "events",
)


def backend_name():
    if DATABASE_URL.startswith(("postgres://", "postgresql://")):
        return "postgres"
    if DATABASE_URL:
        raise RuntimeError("Unsupported DATABASE_URL scheme")
    return "sqlite"


def is_durable_backend():
    return backend_name() == "postgres"


def demo_seed_enabled():
    raw = os.environ.get("PROMOMED_SEED_DEMO")
    if raw is None:
        return backend_name() == "sqlite"
    return raw.strip().lower() in ("1", "true", "yes", "on")


def require_postgres():
    return os.environ.get("PROMOMED_REQUIRE_POSTGRES", "").strip().lower() in ("1", "true", "yes", "on")


def _replace_qmarks(sql):
    out = []
    quote = None
    i = 0
    while i < len(sql):
        ch = sql[i]
        if quote:
            out.append(ch)
            if ch == quote:
                if i + 1 < len(sql) and sql[i + 1] == quote:
                    out.append(sql[i + 1])
                    i += 1
                else:
                    quote = None
        else:
            if ch in ("'", '"'):
                quote = ch
                out.append(ch)
            elif ch == "?":
                out.append("%s")
            else:
                out.append(ch)
        i += 1
    return "".join(out)


_INSERT_RE = re.compile(
    r"^\s*INSERT\s+OR\s+(IGNORE|REPLACE)\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)\s*"
    r"\(([^)]+)\)\s*VALUES\s*\(([^)]*)\)\s*$",
    re.I | re.S,
)


def _rewrite_postgres(sql):
    stripped = sql.strip().rstrip(";")
    m = _INSERT_RE.match(stripped)
    if m:
        mode, table, columns_raw, values_raw = m.groups()
        columns = [x.strip() for x in columns_raw.split(",")]
        base = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({values_raw})"
        if mode.upper() == "IGNORE":
            stripped = base + " ON CONFLICT DO NOTHING"
        else:
            keys = REPLACE_KEYS.get(table)
            if not keys:
                raise RuntimeError(f"No PostgreSQL replace key mapping for table {table}")
            updates = [c for c in columns if c not in keys]
            if updates:
                set_sql = ", ".join(f"{c}=EXCLUDED.{c}" for c in updates)
                stripped = base + f" ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {set_sql}"
            else:
                stripped = base + f" ON CONFLICT ({', '.join(keys)}) DO NOTHING"
    return _replace_qmarks(stripped)


class PostgresCompatConnection:
    backend = "postgres"

    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=()):
        return self.raw.execute(_rewrite_postgres(sql), params)

    def executemany(self, sql, params_seq):
        cur = self.raw.cursor()
        cur.executemany(_rewrite_postgres(sql), params_seq)
        return cur

    def commit(self):
        return self.raw.commit()

    def rollback(self):
        return self.raw.rollback()

    def close(self):
        return self.raw.close()


def connect():
    if backend_name() == "postgres":
        if psycopg is None:
            raise RuntimeError("PostgreSQL backend requires psycopg; install requirements.txt")
        raw = psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=False)
        return PostgresCompatConnection(raw)
    c = sqlite3.connect(SQLITE_PATH, timeout=10, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def _migration_files():
    backend = backend_name()
    root = MIGRATIONS_ROOT / backend
    return sorted(p for p in root.glob("*.sql") if p.is_file())


def _split_postgres_script(sql_text):
    statements=[]
    buf=[]
    quote=None
    dollar_tag=None
    i=0
    while i < len(sql_text):
        if dollar_tag is not None:
            if sql_text.startswith(dollar_tag,i):
                buf.append(dollar_tag)
                i+=len(dollar_tag)
                dollar_tag=None
                continue
            buf.append(sql_text[i]); i+=1; continue
        ch=sql_text[i]
        if quote is not None:
            buf.append(ch)
            if ch==quote:
                if i+1 < len(sql_text) and sql_text[i+1]==quote:
                    buf.append(sql_text[i+1]); i+=2; continue
                quote=None
            i+=1; continue
        if ch in ("'", '"'):
            quote=ch; buf.append(ch); i+=1; continue
        if ch=="$":
            m=re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$",sql_text[i:])
            if m:
                dollar_tag=m.group(0)
                buf.append(dollar_tag)
                i+=len(dollar_tag)
                continue
        if ch==";":
            statement="".join(buf).strip()
            if statement: statements.append(statement)
            buf=[]; i+=1; continue
        buf.append(ch); i+=1
    tail="".join(buf).strip()
    if tail: statements.append(tail)
    if quote is not None or dollar_tag is not None:
        raise RuntimeError("Unterminated PostgreSQL migration quote")
    return statements


def _execute_script(conn, sql_text):
    if backend_name() == "sqlite":
        conn.executescript(sql_text)
        return
    for statement in _split_postgres_script(sql_text):
        conn.execute(statement)


def _ensure_migration_table(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS _schema_migrations(
               version TEXT PRIMARY KEY,
               checksum TEXT NOT NULL,
               applied_at BIGINT NOT NULL
           )"""
    )
    conn.commit()


def migration_status(conn=None):
    own = conn is None
    c = conn or connect()
    try:
        _ensure_migration_table(c)
        rows = list(c.execute("SELECT version,checksum,applied_at FROM _schema_migrations ORDER BY version"))
        applied = {r["version"]: dict(r) for r in rows}
        available = []
        drift = []
        for path in _migration_files():
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            version = path.stem
            available.append({"version": version, "checksum": checksum})
            if version in applied and applied[version]["checksum"] != checksum:
                drift.append(version)
        missing = [x["version"] for x in available if x["version"] not in applied]
        return {
            "backend": backend_name(),
            "durable": is_durable_backend(),
            "available": [x["version"] for x in available],
            "applied": list(applied.keys()),
            "missing": missing,
            "checksum_drift": drift,
            "schema_ready": not missing and not drift,
        }
    finally:
        if own:
            c.close()


def migrate(conn=None):
    own = conn is None
    c = conn or connect()
    try:
        _ensure_migration_table(c)
        applied_rows = list(c.execute("SELECT version,checksum FROM _schema_migrations"))
        applied = {r["version"]: r["checksum"] for r in applied_rows}
        for path in _migration_files():
            version = path.stem
            payload = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if version in applied:
                if applied[version] != checksum:
                    raise RuntimeError(f"Migration checksum drift: {version}")
                continue
            _execute_script(c, payload)
            c.execute(
                "INSERT INTO _schema_migrations(version,checksum,applied_at) VALUES(?,?,?)",
                (version, checksum, int(time.time())),
            )
            c.commit()
        return migration_status(c)
    except Exception:
        c.rollback()
        raise
    finally:
        if own:
            c.close()


def sync_sequences(conn):
    if backend_name() != "postgres":
        return
    for table in SERIAL_TABLES:
        conn.execute(
            f"""SELECT setval(
                    pg_get_serial_sequence('{table}','id'),
                    COALESCE((SELECT MAX(id) FROM {table}), 1),
                    EXISTS(SELECT 1 FROM {table})
                )"""
        )
    conn.commit()


def readiness():
    c = connect()
    try:
        c.execute("SELECT 1").fetchone()
        status = migration_status(c)
        status["require_postgres"] = require_postgres()
        status["demo_seed_enabled"] = demo_seed_enabled()
        demo_accounts = 0
        if "003_account_authority" in status["applied"]:
            demo_accounts = int(
                c.execute("SELECT COUNT(*) n FROM accounts WHERE email LIKE ?", ("%@demo.ru",)).fetchone()["n"]
            )
        status["demo_accounts"] = demo_accounts
        status["production_ready"] = bool(
            status["schema_ready"]
            and status["durable"]
            and not status["checksum_drift"]
            and not status["demo_seed_enabled"]
            and status["demo_accounts"] == 0
        )
        status["ready"] = bool(
            status["schema_ready"]
            and (not require_postgres() or status["durable"])
        )
        return status
    finally:
        c.close()
