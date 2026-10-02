import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(path, backend):
    manifest = {
        "backend": backend,
        "created_at": int(time.time()),
        "sha256": sha256_file(path),
        "git_commit": os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("GITHUB_SHA") or "local",
    }
    manifest_path = Path(str(path) + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def validate_manifest(path):
    manifest_path = Path(str(path) + ".manifest.json")
    if not manifest_path.exists():
        raise SystemExit(f"Missing manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    actual = sha256_file(path)
    if actual != manifest.get("sha256"):
        raise SystemExit("Backup checksum mismatch")
    return manifest


def backup_sqlite(output):
    source = sqlite3.connect(db.SQLITE_PATH)
    target = sqlite3.connect(str(output))
    try:
        source.backup(target)
        target.commit()
    finally:
        target.close()
        source.close()


def restore_sqlite(input_path, target_path):
    source = sqlite3.connect(str(input_path))
    target = sqlite3.connect(str(target_path))
    try:
        source.backup(target)
        target.commit()
    finally:
        target.close()
        source.close()


def require_binary(name):
    binary = shutil.which(name)
    if not binary:
        raise SystemExit(f"Required binary not found: {name}")
    return binary


def backup_postgres(output, database_url):
    cmd = [
        require_binary("pg_dump"),
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        "--file",
        str(output),
        database_url,
    ]
    subprocess.run(cmd, check=True)


def restore_postgres(input_path, database_url):
    cmd = [
        require_binary("pg_restore"),
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        "--dbname",
        database_url,
        str(input_path),
    ]
    subprocess.run(cmd, check=True)


def main():
    parser = argparse.ArgumentParser(description="Promomed durable database backup/restore proof utility")
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("backup")
    b.add_argument("--output", required=True)

    r = sub.add_parser("restore")
    r.add_argument("--input", required=True)
    r.add_argument("--database-url")
    r.add_argument("--sqlite-path")

    args = parser.parse_args()

    if args.command == "backup":
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        backend = db.backend_name()
        if backend == "postgres":
            backup_postgres(output, db.DATABASE_URL)
        else:
            backup_sqlite(output)
        manifest = write_manifest(output, backend)
        print(json.dumps({"ok": True, "backend": backend, "backup": str(output), "manifest": str(manifest)}))
        return

    input_path = Path(args.input)
    manifest = validate_manifest(input_path)
    backend = manifest["backend"]
    if backend == "postgres":
        target = args.database_url or os.environ.get("RESTORE_DATABASE_URL", "")
        if not target.startswith(("postgres://", "postgresql://")):
            raise SystemExit("PostgreSQL restore requires --database-url or RESTORE_DATABASE_URL")
        restore_postgres(input_path, target)
    elif backend == "sqlite":
        target = args.sqlite_path or os.environ.get("RESTORE_SQLITE_PATH", "")
        if not target:
            raise SystemExit("SQLite restore requires --sqlite-path or RESTORE_SQLITE_PATH")
        restore_sqlite(input_path, target)
    else:
        raise SystemExit(f"Unsupported manifest backend: {backend}")
    print(json.dumps({"ok": True, "backend": backend, "restored": True}))


if __name__ == "__main__":
    main()
