#!/usr/bin/env bash
set -euo pipefail
: "${DATABASE_URL:?DATABASE_URL is required}"
BACKUP_FILE="${BACKUP_FILE:-promomed.dump}"
PG_DOCKER_IMAGE="${PG_DOCKER_IMAGE:-}"

if [ -n "${PG_DOCKER_IMAGE}" ]; then
  out_dir="$(cd "$(dirname "${BACKUP_FILE}")" && pwd)"
  out_name="$(basename "${BACKUP_FILE}")"
  docker run --rm --network host -v "${out_dir}:/backup" "${PG_DOCKER_IMAGE}"     pg_dump "${DATABASE_URL}" --format=custom --no-owner --no-acl --file "/backup/${out_name}"
else
  pg_dump "${DATABASE_URL}" --format=custom --no-owner --no-acl --file "${BACKUP_FILE}"
fi

test -s "${BACKUP_FILE}"
echo "${BACKUP_FILE}"
