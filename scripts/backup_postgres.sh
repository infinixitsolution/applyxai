#!/usr/bin/env bash
# Template: daily PostgreSQL backup (not wired into the app).
# Usage: DATABASE_URL='postgresql+psycopg://user:pass@host/db' ./scripts/backup_postgres.sh
# Optional: BACKUP_S3_URI='s3://bucket/prefix/' to upload with aws cli.

set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "Set DATABASE_URL (postgresql://...)" >&2
  exit 1
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${BACKUP_DIR:-./storage/backups}/applyxai-${STAMP}.sql.gz"
mkdir -p "$(dirname "$OUT")"

# Strip SQLAlchemy driver prefix for pg_dump
PGURL="${DATABASE_URL#postgresql+psycopg://}"
PGURL="${PGURL#postgresql://}"

pg_dump "$PGURL" | gzip -9 > "$OUT"
echo "Wrote $OUT"

if [[ -n "${BACKUP_S3_URI:-}" ]]; then
  aws s3 cp "$OUT" "${BACKUP_S3_URI}$(basename "$OUT")"
  echo "Uploaded to ${BACKUP_S3_URI}"
fi
