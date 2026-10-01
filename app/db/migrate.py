from pathlib import Path
from .core import connect, backend_name

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "migrations" / "postgres"

def _files():
    return sorted(MIGRATIONS.glob("*.sql"))

def migrate():
    if backend_name() != "postgres":
        c = connect()
        try:
            for name in ("0003_integration_authorities.sql","0004_observability_passkeys_citations.sql"):
                migration = MIGRATIONS / name
                if migration.exists():
                    c.executescript(migration.read_text(encoding="utf-8"))
            c.commit()
        finally:
            c.close()
        return {"backend": "sqlite", "applied": ["demo-integration-schema"], "pending": []}
    c = connect()
    applied_now = []
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS schema_migrations(
            version TEXT PRIMARY KEY,
            applied_at BIGINT NOT NULL
        )""")
        rows = c.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
        applied = {r["version"] for r in rows}
        for path in _files():
            if path.name in applied:
                continue
            script = path.read_text(encoding="utf-8")
            statements = [s.strip() for s in script.split(";") if s.strip()]
            for stmt in statements:
                c.execute(stmt)
            c.execute(
                "INSERT INTO schema_migrations(version,applied_at) VALUES(?,EXTRACT(EPOCH FROM NOW())::BIGINT)",
                (path.name,),
            )
            applied_now.append(path.name)
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
    result = migration_status()
    result["applied_now"] = applied_now
    return result

def migration_status():
    expected = [p.name for p in _files()]
    if backend_name() != "postgres":
        return {"backend": "sqlite", "expected": expected, "applied": [], "pending": expected}
    c = connect()
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS schema_migrations(
            version TEXT PRIMARY KEY,
            applied_at BIGINT NOT NULL
        )""")
        rows = c.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
        applied = [r["version"] for r in rows]
    finally:
        c.close()
    return {
        "backend": "postgres",
        "expected": expected,
        "applied": applied,
        "pending": [x for x in expected if x not in applied],
    }
