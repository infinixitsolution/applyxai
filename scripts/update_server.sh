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

./venv/bin/pip install -q -r requirements.txt

if [[ -f backend/alembic.ini ]]; then
  ./venv/bin/alembic -c backend/alembic.ini upgrade head
fi

if [[ "$BEFORE" != "$AFTER" ]] && git diff --name-only "$BEFORE" "$AFTER" | grep -q '^frontend/'; then
  (cd frontend && npm ci && npm run build)
fi

sudo systemctl restart applyxai-backend
sudo systemctl is-active applyxai-backend
echo "Deployed $BRANCH at $AFTER"
