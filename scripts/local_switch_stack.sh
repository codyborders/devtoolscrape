#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <blue|green>" >&2
  exit 1
fi

COLOR="$1"
if [[ "$COLOR" != "blue" && "$COLOR" != "green" ]]; then
  echo "Invalid color: $COLOR (expected 'blue' or 'green')" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONF_DIR="$ROOT_DIR/deploy/nginx/local"
TARGET_CONF="$CONF_DIR/default.conf.$COLOR"
ACTIVE_CONF="$CONF_DIR/default.conf"

if [[ ! -f "$TARGET_CONF" ]]; then
  echo "Template $TARGET_CONF does not exist" >&2
  exit 1
fi

cp "$TARGET_CONF" "$ACTIVE_CONF"
echo "Switched local router to $COLOR stack."

if command -v docker &>/dev/null; then
  if docker compose ls &>/dev/null; then
    docker compose -f "$ROOT_DIR/docker-compose.local-blue-green.yml" exec router nginx -s reload >/dev/null 2>&1 || true
  fi
fi
