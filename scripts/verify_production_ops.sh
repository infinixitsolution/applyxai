#!/usr/bin/env bash
# On-host production sanity checks. Does not print secrets.
set -euo pipefail

APP_DIR="${APP_DIR:-/home/ubuntu/applyxai}"
ENV_FILE="${ENV_FILE:-$APP_DIR/.env}"
FAIL=0

warn() { echo "WARN: $*" >&2; }
fail() { echo "FAIL: $*" >&2; FAIL=1; }

echo "=== ApplyXAI production ops verify ==="
echo "App dir: $APP_DIR"

for unit in applyxai-backend applyxai-celery; do
  if systemctl is-active --quiet "$unit" 2>/dev/null; then
    echo "OK: $unit active"
  else
    fail "$unit is not active"
  fi
done

if [[ -f "$ENV_FILE" ]]; then
  if grep -qE '^RATE_LIMIT_STORAGE_URL=memory://' "$ENV_FILE" 2>/dev/null; then
    fail "RATE_LIMIT_STORAGE_URL is memory:// (use Redis in production)"
  elif grep -qE '^RATE_LIMIT_STORAGE_URL=redis://' "$ENV_FILE" 2>/dev/null; then
    echo "OK: RATE_LIMIT_STORAGE_URL uses Redis"
  else
    warn "RATE_LIMIT_STORAGE_URL not found or empty in $ENV_FILE"
  fi

  if grep -qE '^PAYMENT_PROVIDER=razorpay' "$ENV_FILE" 2>/dev/null; then
    echo "OK: PAYMENT_PROVIDER=razorpay"
  else
    warn "PAYMENT_PROVIDER is not razorpay (see docs/BILLING.md)"
  fi

  if grep -qE '^CLAMAV_HOST=.+' "$ENV_FILE" 2>/dev/null; then
    echo "OK: ClamAV configured"
  else
    echo "INFO: ClamAV not configured (upload scan skipped)"
  fi
else
  warn "No $ENV_FILE — skipping env checks"
fi

if command -v redis-cli >/dev/null 2>&1; then
  if redis-cli ping 2>/dev/null | grep -q PONG; then
    echo "OK: redis-cli ping"
  else
    warn "redis-cli ping failed"
  fi
fi

if systemctl is-active --quiet applyxai-celery 2>/dev/null; then
  if journalctl -u applyxai-celery --since "25 hours ago" --no-pager 2>/dev/null \
    | grep -q 'abandon_stale_mock_interviews complete'; then
    echo "OK: mock interview abandon task logged in last 25h"
  else
    warn "No abandon_stale_mock_interviews log in last 25h (beat may be new — check again tomorrow)"
  fi
fi

echo "=== Smoke ==="
BASE="${BASE_URL:-https://applyxai.com}"
if [[ -x "$APP_DIR/scripts/smoke_production.sh" ]] || [[ -f "$APP_DIR/scripts/smoke_production.sh" ]]; then
  BASE_URL="$BASE" bash "$APP_DIR/scripts/smoke_production.sh" || fail "smoke_production.sh failed"
else
  curl -fsS "${BASE%/}/api/health" | grep -q '"success":true' || fail "health check failed"
  echo "OK: GET /api/health"
fi

if [[ "$FAIL" -ne 0 ]]; then
  echo "=== Result: FAILED ==="
  exit 1
fi
echo "=== Result: OK ==="
