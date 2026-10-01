import os
import re
import sqlite3

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SQLITE_PATH = os.environ.get("SQLITE_PATH", "/tmp/sostoyanie.db")

_REPLACE_KEYS = {
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

def backend_name():
    return "postgres" if DATABASE_URL.startswith(("postgres://", "postgresql://")) else "sqlite"

def _rewrite_insert_or_ignore(sql):
    if "INSERT OR IGNORE" not in sql.upper():
        return sql
    rewritten = re.sub(r"INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", sql, flags=re.I)
    stripped = rewritten.rstrip().rstrip(";")
    if "ON CONFLICT" not in stripped.upper():
        stripped += " ON CONFLICT DO NOTHING"
    return stripped

def _rewrite_insert_or_replace(sql):
    if "INSERT OR REPLACE" not in sql.upper():
        return sql
    m = re.match(
        r"\s*INSERT\s+OR\s+REPLACE\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)\s*;?\s*$",
        sql,
        flags=re.I | re.S,
    )
    if not m:
        raise ValueError("unsupported INSERT OR REPLACE form for PostgreSQL")
    table, cols_raw, vals_raw = m.groups()
    cols = [x.strip() for x in cols_raw.split(",")]
    keys = _REPLACE_KEYS.get(table.lower())
    if not keys:
        raise ValueError(f"missing conflict key mapping for {table}")
    updates = [c for c in cols if c not in keys]
    conflict = ",".join(keys)
    if updates:
        assignment = ",".join(f"{c}=EXCLUDED.{c}" for c in updates)
        suffix = f" ON CONFLICT ({conflict}) DO UPDATE SET {assignment}"
    else:
        suffix = f" ON CONFLICT ({conflict}) DO NOTHING"
    return f"INSERT INTO {table}({','.join(cols)}) VALUES({vals_raw}){suffix}"

def _quote_legacy_end(sql):
    # Only the two legacy schemas use a column literally named "end".
    # Avoid global text replacement: words such as attendee contain "end".
    sql = re.sub(r'\\b([A-Za-z_][A-Za-z0-9_]*)\\.end\\b', r'\\1."end"', sql)
    for table in ("program_items", "appointment_slots"):
        m = re.match(
            rf"(\\s*INSERT\\s+INTO\\s+{table}\\s*\\()([^)]+)(\\)\\s*VALUES.*)",
            sql,
            flags=re.I | re.S,
        )
        if m:
            cols = [c.strip() for c in m.group(2).split(",")]
            cols = ['"end"' if c.lower() == "end" else c for c in cols]
            sql = m.group(1) + ",".join(cols) + m.group(3)
        sql = re.sub(
            rf"(\\bUPDATE\\s+{table}\\s+SET\\s+)end\\b",
            rf'\\1"end"',
            sql,
            flags=re.I,
        )
    return sql

def adapt_sql(sql):
    if backend_name() != "postgres":
        return sql
    sql = _rewrite_insert_or_replace(sql)
    sql = _rewrite_insert_or_ignore(sql)
    sql = _quote_legacy_end(sql)
    return sql.replace("?", "%s")

class CompatConnection:
    def __init__(self, raw, backend):
        self.raw = raw
        self.backend = backend

    def execute(self, sql, params=()):
        if self.backend == "postgres":
            return self.raw.execute(adapt_sql(sql), params)
        return self.raw.execute(sql, params)

    def executemany(self, sql, seq):
        if self.backend == "postgres":
            cur = self.raw.cursor()
            cur.executemany(adapt_sql(sql), seq)
            return cur
        return self.raw.executemany(sql, seq)

    def executescript(self, script):
        if self.backend == "postgres":
            return None
        return self.raw.executescript(script)

    def commit(self):
        return self.raw.commit()

    def rollback(self):
        return self.raw.rollback()

    def close(self):
        return self.raw.close()

def connect():
    if backend_name() == "postgres":
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("PostgreSQL selected but psycopg is not installed") from exc
        raw = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        return CompatConnection(raw, "postgres")
    raw = sqlite3.connect(SQLITE_PATH, timeout=10, check_same_thread=False)
    raw.row_factory = sqlite3.Row
    return CompatConnection(raw, "sqlite")

def db_status():
    return {
        "backend": backend_name(),
        "durable": backend_name() == "postgres",
        "sqlite_path": None if backend_name() == "postgres" else SQLITE_PATH,
        "production_admitted": backend_name() == "postgres",
    }
