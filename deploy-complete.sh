#!/bin/bash
# Complete deployment script with database migration
# Run this on a new DigitalOcean droplet

set -e

if [ $# -ne 2 ]; then
    echo "Usage: $0 GITHUB_REPO_URL OLD_DROPLET_IP"
    echo "Example: $0 https://github.com/username/devtoolscrape.git 123.456.789.012"
    exit 1
fi

GITHUB_REPO=$1
OLD_DROPLET_IP=$2

echo "🚀 Complete DevTools Scraper deployment with database migration..."

# Update system
echo "📦 Updating system packages..."
apt update && apt upgrade -y

# Install Docker and Docker Compose
echo "🐳 Installing Docker and Docker Compose..."
apt install -y docker.io docker-compose nginx git

# Start and enable Docker
systemctl start docker
systemctl enable docker

# Create app directory
echo "📁 Setting up application directory..."
mkdir -p /root/devtoolscrape
cd /root/devtoolscrape

# Create data and logs directories
mkdir -p data logs

# Clone from GitHub
echo "📥 Cloning from GitHub..."
git clone $GITHUB_REPO .

# Copy database from old droplet
echo "🔄 Migrating database from old droplet..."
scp root@$OLD_DROPLET_IP:/root/devtoolscrape/startups.db ./data/startups.db
chmod 644 ./data/startups.db

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

# Build and start the app
echo "🔨 Building and starting the app..."
docker-compose up -d --build

echo "✅ Complete deployment finished!"
echo "🌐 Your app should be available at: http://$(curl -s ifconfig.me)"
echo "📊 Check status: docker-compose ps"
echo "📝 View logs: docker-compose logs -f" 