#!/bin/bash
# Database migration script
# Run this on the NEW droplet to copy database from OLD droplet

set -e

if [ $# -ne 1 ]; then
    echo "Usage: $0 OLD_DROPLET_IP"
    echo "Example: $0 123.456.789.012"
    exit 1
fi

OLD_DROPLET_IP=$1

echo "🔄 Migrating database from old droplet ($OLD_DROPLET_IP)..."

# Stop the app if it's running
echo "⏹️  Stopping app if running..."
docker-compose down 2>/dev/null || true

# Copy database from old droplet
echo "📥 Copying database..."
scp root@$OLD_DROPLET_IP:/root/devtoolscrape/startups.db ./data/startups.db

# Set proper permissions
chmod 644 ./data/startups.db

echo "✅ Database migration complete!"
echo "📊 Database copied to: ./data/startups.db"
echo "🚀 You can now start the app with: docker-compose up -d --build" 