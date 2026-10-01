#!/usr/bin/env bash
set -euo pipefail
: "${RESTORE_DATABASE_URL:?RESTORE_DATABASE_URL is required}"
BACKUP_FILE="${BACKUP_FILE:-promomed.dump}"
pg_restore --clean --if-exists --no-owner --no-acl --dbname "${RESTORE_DATABASE_URL}" "${BACKUP_FILE}"
