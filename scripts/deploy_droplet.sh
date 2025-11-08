#!/usr/bin/env bash
#
# Deploy the current git branch to the DigitalOcean droplet defined in .env.
# Steps performed remotely:
#   1. Fetch + checkout the requested branch inside /root/devtoolscrape
#   2. Back up the sqlite database (if found)
#   3. Restart the docker-compose stack
#   4. Validate the HTTP health check and confirm the DB has records
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing .env file at $ENV_FILE" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

: "${DIGITALOCEAN_IP:?DIGITALOCEAN_IP is not set in .env}"
: "${DIGITALOCEAN_PASSWORD:?DIGITALOCEAN_PASSWORD is not set in .env}"

BRANCH="${1:-$(git -C "$ROOT_DIR" rev-parse --abbrev-ref HEAD)}"
REMOTE_REPO_DIR="${REMOTE_REPO_DIR:-/root/devtoolscrape}"
REMOTE_BACKUP_DIR="${REMOTE_BACKUP_DIR:-$REMOTE_REPO_DIR/backups}"
REMOTE_DB_PRIMARY="${REMOTE_DB_PRIMARY:-$REMOTE_REPO_DIR/startups.db}"
REMOTE_DB_SECONDARY="${REMOTE_DB_SECONDARY:-$REMOTE_REPO_DIR/data/startups.db}"
REMOTE_HEALTH_URL="${REMOTE_HEALTH_URL:-http://127.0.0.1:8000/health}"
REMOTE_COMPOSE_CMD="${REMOTE_COMPOSE_CMD:-docker compose}"

if ! command -v sshpass >/dev/null 2>&1; then
  echo "sshpass is required to run this script. Install it and retry." >&2
  exit 1
fi

echo "Deploying branch '$BRANCH' to $DIGITALOCEAN_IP ..."

sshpass -p "$DIGITALOCEAN_PASSWORD" ssh -o StrictHostKeyChecking=no "root@$DIGITALOCEAN_IP" bash -s <<EOF
set -euo pipefail

BRANCH="$BRANCH"
REPO_DIR="$REMOTE_REPO_DIR"
BACKUP_DIR="$REMOTE_BACKUP_DIR"
DB_PRIMARY="$REMOTE_DB_PRIMARY"
DB_SECONDARY="$REMOTE_DB_SECONDARY"
HEALTH_URL="$REMOTE_HEALTH_URL"
COMPOSE_CMD="$REMOTE_COMPOSE_CMD"
export DB_PRIMARY DB_SECONDARY

echo "==> Working directory: \$REPO_DIR"
if [[ ! -d "\$REPO_DIR/.git" ]]; then
  echo "Repository not found at \$REPO_DIR" >&2
  exit 1
fi

cd "\$REPO_DIR"

echo "==> Fetching and checking out branch \$BRANCH"
git fetch origin
git checkout "\$BRANCH"
git reset --hard "origin/\$BRANCH"

echo "==> Backing up sqlite database (if present)"
DB_PATH=""
if [[ -f "\$DB_PRIMARY" ]]; then
  DB_PATH="\$DB_PRIMARY"
elif [[ -f "\$DB_SECONDARY" ]]; then
  DB_PATH="\$DB_SECONDARY"
fi

if [[ -n "\$DB_PATH" ]]; then
  mkdir -p "\$BACKUP_DIR"
  BACKUP_FILE="\$BACKUP_DIR/startups-\$(date +%Y%m%d-%H%M%S).db"
  cp "\$DB_PATH" "\$BACKUP_FILE"
  echo "    Backed up \$DB_PATH => \$BACKUP_FILE"
else
  echo "    No sqlite database file found; continuing without backup."
fi

echo "==> Restarting application via \$COMPOSE_CMD"
\$COMPOSE_CMD down || true
\$COMPOSE_CMD up -d --build

echo "==> Waiting for containers to settle"
sleep 5

echo "==> Validating application health at \$HEALTH_URL"
curl -fsS "\$HEALTH_URL" >/tmp/health.json
cat /tmp/health.json

echo "==> Validating database contents"
python3 - <<'PY'
import os
import sqlite3
import sys

db_candidates = [
    os.environ["DB_PRIMARY"],
    os.environ["DB_SECONDARY"],
]
for path in db_candidates:
    if os.path.exists(path):
        conn = sqlite3.connect(path)
        count = conn.execute("SELECT COUNT(*) FROM startups").fetchone()[0]
        conn.close()
        if count <= 0:
            raise SystemExit(f"Database {path} exists but contains {count} rows.")
        print(f"Database {path} contains {count} startups.")
        break
else:
    raise SystemExit("No sqlite database file found for verification.")
PY

echo "Deployment completed successfully."
EOF
