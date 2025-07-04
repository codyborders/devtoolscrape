#!/bin/bash
# Quick update script for DevTools Scraper

set -e

echo "🔄 Updating DevTools Scraper..."

# Stop the current container
echo "⏹️  Stopping current container..."
docker-compose down

# Pull latest changes (if using git)
# git pull origin main

# Rebuild and start
echo "🔨 Rebuilding and starting..."
docker-compose up -d --build

echo "✅ Update complete!"
echo "📊 Check status: docker-compose ps"
echo "📝 View logs: docker-compose logs -f" 