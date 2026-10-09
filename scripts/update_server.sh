#!/usr/bin/env bash
# Pull the current GitHub branch and restart ApplyXAI.
set -euo pipefail

APP_DIR="/home/ubuntu/applyxai"
BRANCH="${1:-socialapp}"

cd "$APP_DIR"

git fetch origin

if ! git diff --quiet; then
  git stash push -m "pre-deploy $(date -Iseconds)"
fi

BEFORE="$(git rev-parse HEAD)"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"
AFTER="$(git rev-parse HEAD)"

./venv/bin/pip install -q -r requirements.txt -r backend/requirements.txt

if [[ -f backend/alembic.ini ]]; then
  ./venv/bin/alembic -c backend/alembic.ini upgrade head
fi

if [[ "$BEFORE" != "$AFTER" ]] && git diff --name-only "$BEFORE" "$AFTER" | grep -q '^frontend/'; then
  (cd frontend && npm ci && npm run build)
fi

NGINX_SNIPPET="$APP_DIR/scripts/nginx/applyxai-security-headers.conf"
NGINX_SITE="$APP_DIR/scripts/nginx/applyxai.conf"
if [[ -f "$NGINX_SITE" && -f "$NGINX_SNIPPET" ]]; then
  sudo mkdir -p /etc/nginx/snippets
  sudo cp "$NGINX_SNIPPET" /etc/nginx/snippets/applyxai-security-headers.conf
  sudo cp "$NGINX_SITE" /etc/nginx/sites-available/applyxai
  sudo ln -sf /etc/nginx/sites-available/applyxai /etc/nginx/sites-enabled/applyxai
  sudo nginx -t
  sudo systemctl reload nginx
fi

CELERY_UNIT="$APP_DIR/scripts/systemd/applyxai-celery.service"
if [[ -f "$CELERY_UNIT" ]]; then
  sudo cp "$CELERY_UNIT" /etc/systemd/system/applyxai-celery.service
  sudo systemctl daemon-reload
  sudo systemctl enable applyxai-celery.service
  sudo systemctl restart applyxai-celery.service
  sudo systemctl is-active applyxai-celery.service
fi

sudo systemctl restart applyxai-backend
sudo systemctl is-active applyxai-backend
echo "Deployed $BRANCH at $AFTER"
