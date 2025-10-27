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
pip install aiohttp pyyaml structlog

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
