#!/usr/bin/env bash
# Quick production smoke checks. Usage: BASE_URL=https://applyxai.com ./scripts/smoke_production.sh
set -euo pipefail
BASE="${BASE_URL:-http://localhost:8000}"
BASE="${BASE%/}"

curl -fsS "${BASE}/api/health" | grep -q '"success":true'
curl -fsS "${BASE}/api/site/public" | grep -q '"success":true'
curl -fsS "${BASE}/api/site/robots.txt" | head -1 | grep -qi user-agent
curl -fsS "${BASE}/api/site/agent-release" | grep -q '"version"'

echo "Smoke OK: ${BASE}"
