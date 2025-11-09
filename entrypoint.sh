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

# Write out the cron job to run every 4 hours
echo "0 */4 * * * cd /app && python3 scrape_all.py >> /var/log/cron.log 2>&1" > /etc/cron.d/scrape_all
chmod 0644 /etc/cron.d/scrape_all
crontab /etc/cron.d/scrape_all

# Start cron in the background
cron

# Start gunicorn for the Flask app
exec ddtrace-run gunicorn -c gunicorn.conf.py app_production:app
