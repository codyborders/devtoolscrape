#!/bin/bash
set -e

DATA_DIR="${DEVTOOLS_DATA_DIR:-/app/data}"
DB_FILE="${DEVTOOLS_DB_PATH:-${DATA_DIR%/}/startups.db}"
LEGACY_DB="/app/startups.db"

mkdir -p "$(dirname "$DB_FILE")"

# If an old root-level database exists and the data volume is empty, migrate it.
if [ -f "$LEGACY_DB" ] && [ ! -L "$LEGACY_DB" ] && [ ! -s "$DB_FILE" ]; then
    cp "$LEGACY_DB" "$DB_FILE"
fi

# Ensure the primary database file exists so sqlite commands don't fail on start.
if [ ! -f "$DB_FILE" ]; then
    touch "$DB_FILE"
fi

# Keep legacy path in place for older code paths that reference startups.db directly.
ln -sf "$DB_FILE" "$LEGACY_DB"

# Write out the cron job to run every 4 hours using ddtrace-run plus absolute binaries so spans emit correctly.
PYTHON_BIN="$(command -v python3 || true)"
if [ -z "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi
DDTRACE_BIN="$(command -v ddtrace-run || true)"
if [ -z "$DDTRACE_BIN" ]; then
    DDTRACE_BIN="ddtrace-run"
fi
CRON_ENV="DD_ENV=${DD_ENV:-prod} DD_SERVICE=${DD_SERVICE:-devtoolscrape} DD_VERSION=${DD_VERSION:-1.0} DD_AGENT_HOST=${DD_AGENT_HOST:-dd-agent} DD_TRACE_ENABLED=${DD_TRACE_ENABLED:-true} DD_APM_ENABLED=${DD_APM_ENABLED:-true} DD_RUNTIME_METRICS_ENABLED=${DD_RUNTIME_METRICS_ENABLED:-true} DD_LLMOBS_ENABLED=${DD_LLMOBS_ENABLED:-1} DD_LLMOBS_ML_APP=${DD_LLMOBS_ML_APP:-devtoolscrape}"
echo "0 */4 * * * cd /app && env ${CRON_ENV} ${DDTRACE_BIN} ${PYTHON_BIN} scrape_all.py >> /var/log/cron.log 2>&1" > /etc/cron.d/scrape_all
chmod 0644 /etc/cron.d/scrape_all
crontab /etc/cron.d/scrape_all

# Start cron in the background
cron

# Start gunicorn for the Flask app
exec ddtrace-run gunicorn -c gunicorn.conf.py app_production:app
