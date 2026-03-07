#!/bin/bash
# Fresh droplet deployment for DevTools Scraper
# Run this on a new DigitalOcean droplet

set -e

echo "🚀 Setting up fresh DevTools Scraper deployment..."

# Update system
apt update && apt upgrade -y

# Install Docker and Docker Compose
apt install -y docker.io docker-compose nginx git

# Start and enable Docker
systemctl start docker
systemctl enable docker

# Create app directory
mkdir -p /root/devtoolscrape
cd /root/devtoolscrape

# Create data and logs directories
mkdir -p data logs

# Set up Nginx reverse proxy
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
ufw allow ssh
ufw allow 'Nginx Full'
ufw --force enable

echo "✅ Fresh droplet setup complete!"
echo "📋 Next steps:"
echo "   1. Copy your code: scp -r ./* root@NEW-DROPLET-IP:/root/devtoolscrape/"
echo "   2. SSH to droplet and run: cd /root/devtoolscrape && docker-compose up -d --build"
echo "   3. Copy database from old droplet if needed:"
echo "      scp root@OLD-DROPLET-IP:/root/devtoolscrape/startups.db ./data/" 