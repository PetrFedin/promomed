#!/usr/bin/env bash
set -euo pipefail
: "${RESTORE_DATABASE_URL:?RESTORE_DATABASE_URL is required}"
BACKUP_FILE="${BACKUP_FILE:-promomed.dump}"
PG_DOCKER_IMAGE="${PG_DOCKER_IMAGE:-}"

test -s "${BACKUP_FILE}"
if [ -n "${PG_DOCKER_IMAGE}" ]; then
  in_dir="$(cd "$(dirname "${BACKUP_FILE}")" && pwd)"
  in_name="$(basename "${BACKUP_FILE}")"
  docker run --rm --network host -v "${in_dir}:/backup:ro" "${PG_DOCKER_IMAGE}"     pg_restore --clean --if-exists --no-owner --no-acl --dbname "${RESTORE_DATABASE_URL}" "/backup/${in_name}"
else
  pg_restore --clean --if-exists --no-owner --no-acl --dbname "${RESTORE_DATABASE_URL}" "${BACKUP_FILE}"
fi
