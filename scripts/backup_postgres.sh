#!/usr/bin/env bash
set -euo pipefail
: "${DATABASE_URL:?DATABASE_URL is required}"
BACKUP_FILE="${BACKUP_FILE:-promomed.dump}"
pg_dump "${DATABASE_URL}" --format=custom --no-owner --no-acl --file "${BACKUP_FILE}"
echo "${BACKUP_FILE}"
