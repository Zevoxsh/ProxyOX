#!/bin/bash

# ProxyOX Uninstallation Script

set -e

echo "==================================="
echo "  ProxyOX Uninstallation Script"
echo "==================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

# Stop and disable service
echo "🛑 Stopping ProxyOX service..."
systemctl stop proxyox 2>/dev/null || true
systemctl disable proxyox 2>/dev/null || true

# Remove service file
echo "🗑️  Removing systemd service..."
rm -f /etc/systemd/system/proxyox.service

# Reload systemd
echo "🔄 Reloading systemd..."
systemctl daemon-reload

echo ""
echo "✅ ProxyOX service uninstalled!"
echo ""
echo "Note: Project files are still in $(pwd)"
echo "To remove them completely, run: rm -rf $(pwd)"
echo ""
