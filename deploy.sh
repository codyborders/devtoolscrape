#!/bin/bash
# DevTools Scraper Deployment Script
# Run this on your DigitalOcean droplet

set -e

echo "🚀 Deploying DevTools Scraper..."

# Update system
echo "📦 Updating system packages..."
apt update && apt upgrade -y

# Install Python and dependencies
echo "🐍 Installing Python and dependencies..."
apt install -y python3 python3-pip python3-venv nginx git

# Create app directory
echo "📁 Setting up application directory..."
mkdir -p /root/devtoolscrape
cd /root/devtoolscrape

# Create virtual environment
echo "🔧 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Set up environment variables
echo "🔑 Setting up environment variables..."
if [ ! -f .env ]; then
    echo "⚠️  Please create .env file with your API keys:"
    echo "   OPENAI_API_KEY=your_key_here"
    echo "   PRODUCTHUNT_CLIENT_ID=your_client_id_here"
    echo "   PRODUCTHUNT_CLIENT_SECRET=your_client_secret_here"
fi

# Initialize database
echo "🗄️  Initializing database..."
python3 -c "from database import init_db; init_db()"

# Set up systemd service
echo "⚙️  Setting up systemd service..."
cp devtools-scraper.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable devtools-scraper

# Set up Nginx
echo "🌐 Setting up Nginx..."
cp nginx-devtools-scraper.conf /etc/nginx/sites-available/devtools-scraper
ln -sf /etc/nginx/sites-available/devtools-scraper /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
systemctl restart nginx

# Start the service
echo "🚀 Starting DevTools Scraper..."
systemctl start devtools-scraper

# Set up firewall
echo "🔥 Setting up firewall..."
ufw allow ssh
ufw allow 'Nginx Full'
ufw --force enable

echo "✅ Deployment complete!"
echo "🌐 Your app should be available at: http://your-droplet-ip"
echo "📊 Check status with: systemctl status devtools-scraper"
echo "📝 View logs with: journalctl -u devtools-scraper -f"
