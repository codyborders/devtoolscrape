#!/bin/bash
set -e

# Write out the cron job to run every 4 hours
echo "0 */4 * * * cd /app && python3 scrape_all.py >> /var/log/cron.log 2>&1" > /etc/cron.d/scrape_all
chmod 0644 /etc/cron.d/scrape_all
crontab /etc/cron.d/scrape_all

# Start cron in the background
cron

# Start gunicorn for the Flask app
exec gunicorn -c gunicorn.conf.py app_production:app 