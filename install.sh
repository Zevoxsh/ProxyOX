#!/bin/bash

# ProxyOX Installation Script for Linux
# This script installs ProxyOX as a systemd service
# Usage: 
#   Local: sudo bash install.sh
#   Remote: curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/proxyox/main/install.sh | sudo bash

set -e

echo "==================================="
echo "   ProxyOX Installation Script"
echo "==================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

# Get the actual user (not root)
if [ -n "$SUDO_USER" ]; then
    REAL_USER=$SUDO_USER
    REAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
else
    REAL_USER=$(whoami)
    REAL_HOME=$HOME
fi

# Check if we're running from a downloaded script (not in the repo)
if [ ! -f "config.yaml" ]; then
    echo "📥 ProxyOX not found locally. Cloning from GitHub..."
    INSTALL_DIR="/etc/proxyox"
    
    # Install git if not present
    if ! command -v git &> /dev/null; then
        echo "📦 Installing git..."
        if command -v apt-get &> /dev/null; then
            apt-get update && apt-get install -y git
        elif command -v yum &> /dev/null; then
            yum install -y git
        elif command -v dnf &> /dev/null; then
            dnf install -y git
        fi
    fi
    
    # Clone repository
    if [ -d "$INSTALL_DIR" ]; then
        echo "⚠️  Directory $INSTALL_DIR already exists. Updating..."
        cd "$INSTALL_DIR"
        git pull
    else
        git clone https://github.com/Zevoxsh/ProxyOX.git "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi
else
    # Running from local directory - move to /etc/proxyox
    INSTALL_DIR="/etc/proxyox"
    CURRENT_DIR=$(pwd)
    
    if [ "$CURRENT_DIR" != "$INSTALL_DIR" ]; then
        echo "📦 Moving ProxyOX to $INSTALL_DIR..."
        if [ -d "$INSTALL_DIR" ]; then
            echo "⚠️  Backing up existing installation..."
            mv "$INSTALL_DIR" "${INSTALL_DIR}.backup.$(date +%s)"
        fi
        cp -r "$CURRENT_DIR" "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi
fi

echo "📁 Installation directory: $INSTALL_DIR"
echo "👤 User: $REAL_USER"
echo ""

# Install Python dependencies
echo "📦 Installing Python dependencies..."
if command -v apt-get &> /dev/null; then
    # Debian/Ubuntu
    apt-get update
    apt-get install -y python3 python3-pip python3-venv
elif command -v yum &> /dev/null; then
    # RHEL/CentOS
    yum install -y python3 python3-pip
elif command -v dnf &> /dev/null; then
    # Fedora
    dnf install -y python3 python3-pip
else
    echo "⚠️  Could not detect package manager. Please install Python 3 manually."
fi

# Create virtual environment
echo "🐍 Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Install Python packages
echo "📚 Installing Python packages..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f "$INSTALL_DIR/.env" ]; then
    echo "🔐 Creating .env configuration file..."
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    
    # Generate random password
    RANDOM_PASSWORD=$(openssl rand -base64 12 2>/dev/null || cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 12 | head -n 1)
    
    # Update .env with random password
    sed -i "s/DASHBOARD_PASSWORD=changeme/DASHBOARD_PASSWORD=$RANDOM_PASSWORD/" "$INSTALL_DIR/.env"
    
    # Store credentials for later display
    DASHBOARD_USER="proxyox"
    DASHBOARD_PASS="$RANDOM_PASSWORD"
else
    echo "ℹ️  .env file already exists, keeping existing configuration"
    # Read existing credentials
    DASHBOARD_USER=$(grep "DASHBOARD_USERNAME=" "$INSTALL_DIR/.env" | cut -d'=' -f2)
    DASHBOARD_PASS=$(grep "DASHBOARD_PASSWORD=" "$INSTALL_DIR/.env" | cut -d'=' -f2)
fi

# Create systemd service file
echo "⚙️  Creating systemd service..."
cat > /etc/systemd/system/proxyox.service <<EOF
[Unit]
Description=ProxyOX - Multi-Protocol Proxy Manager
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$REAL_USER
Group=$REAL_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/src/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=proxyox

# Security settings
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Set proper permissions
echo "🔒 Setting permissions..."
chown -R $REAL_USER:$REAL_USER $INSTALL_DIR
chmod 755 $INSTALL_DIR/src
chmod 644 $INSTALL_DIR/src/*.py
chmod 644 $INSTALL_DIR/config.yaml
chmod 600 $INSTALL_DIR/.env  # Secure .env file

# Reload systemd
echo "🔄 Reloading systemd..."
systemctl daemon-reload

# Enable service
echo "✅ Enabling ProxyOX service..."
systemctl enable proxyox

echo ""
echo "==================================="
echo "   ✅ Installation Complete!"
echo "==================================="
echo ""
echo "🔐 Dashboard Credentials:"
# Determine host IP (try hostname -I, then ip route)
HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$HOST_IP" ]; then
    HOST_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if ($i=="src") print $(i+1)}' | head -n1)
fi
[ -z "$HOST_IP" ] && HOST_IP="localhost"

# Determine port from .env (common keys) or default to 4173
PORT=$(grep -E '^(PORT|DASHBOARD_PORT|HTTP_PORT|APP_PORT)=' "$INSTALL_DIR/.env" 2>/dev/null | head -n1 | cut -d'=' -f2 | tr -d '"' | tr -d "'")
PORT=${PORT:-4173}

echo "   URL:      http://$HOST_IP:$PORT"
echo "   Username: $DASHBOARD_USER"
echo "   Password: $DASHBOARD_PASS"
echo ""
echo "⚠️  IMPORTANT: Change your password in /etc/proxyox/.env"
echo "   Then restart: sudo systemctl restart proxyox"
echo ""
echo "Available commands:"
echo "  sudo systemctl start proxyox      - Start ProxyOX"
echo "  sudo systemctl stop proxyox       - Stop ProxyOX"
echo "  sudo systemctl restart proxyox    - Restart ProxyOX"
echo "  sudo systemctl status proxyox     - Check status"
echo "  sudo journalctl -u proxyox -f     - View logs"
echo ""
echo "To start ProxyOX now, run:"
echo "  sudo systemctl start proxyox"
echo ""