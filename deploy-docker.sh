#!/bin/bash
# Docker-based deployment script for DevTools Scraper
# Run this on your DigitalOcean droplet

set -e

echo "🚀 Deploying DevTools Scraper with Docker..."

# Update system
echo "📦 Updating system packages..."
apt update && apt upgrade -y

# Install Docker and Docker Compose
echo "🐳 Installing Docker and Docker Compose..."
apt install -y docker.io docker-compose curl

# Start and enable Docker
systemctl start docker
systemctl enable docker

# Create app directory
echo "📁 Setting up application directory..."
mkdir -p /root/devtoolscrape
cd /root/devtoolscrape

# Create data and logs directories
mkdir -p data logs

# Copy your application files (you'll need to do this manually or via git)
echo "📋 Copy your application files to /root/devtoolscrape/"
echo "   You can use: scp -r ./* root@your-droplet-ip:/root/devtoolscrape/"

# If you have an existing database, preserve it
if [ -f /root/devtoolscrape/startups.db ]; then
    echo "💾 Preserving existing database..."
    cp /root/devtoolscrape/startups.db /root/devtoolscrape/data/startups.db
fi

# Build and start the Docker container
echo "🔨 Building and starting Docker container..."
docker-compose up -d --build

# Set up Nginx reverse proxy
echo "🌐 Setting up Nginx reverse proxy..."
cat > /etc/nginx/sites-available/devtools-scraper << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

ln -sf /etc/nginx/sites-available/devtools-scraper /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
systemctl restart nginx

# Set up firewall
echo "🔥 Setting up firewall..."
ufw allow ssh
ufw allow 'Nginx Full'
ufw --force enable

echo "✅ Docker deployment complete!"
echo "🌐 Your app should be available at: http://your-droplet-ip"
echo "📊 Check status with: docker-compose ps"
echo "📝 View logs with: docker-compose logs -f"
echo "🔄 To update: docker-compose down && docker-compose up -d --build" 