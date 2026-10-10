#!/usr/bin/env bash
# Optional CI: run Alembic against TEST_POSTGRES_URL when set.
set -euo pipefail
if [[ -z "${TEST_POSTGRES_URL:-}" ]]; then
  echo "SKIP: TEST_POSTGRES_URL not set"
  exit 0
fi
export DATABASE_URL="$TEST_POSTGRES_URL"
alembic -c backend/alembic.ini upgrade head
echo "Migrations applied."
