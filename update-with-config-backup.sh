#!/bin/bash

###############################################
# ProxyOX Update Script with Config Backup
###############################################

echo "====================================="
echo "   ProxyOX Update (Keep Config)"
echo "====================================="
echo ""

INSTALL_DIR="/etc/proxyox"

if [ ! -d "$INSTALL_DIR" ]; then
    echo "❌ ProxyOX not installed in $INSTALL_DIR"
    exit 1
fi

cd "$INSTALL_DIR" || exit 1

# 1. Sauvegarder la configuration actuelle
echo "📦 Backing up current config.yaml..."
cp config.yaml config.yaml.backup
echo "✅ Config saved to config.yaml.backup"
echo ""

# 2. Sauvegarder les variables d'environnement
if [ -f ".env" ]; then
    echo "📦 Backing up .env file..."
    cp .env .env.backup
    echo "✅ .env saved to .env.backup"
    echo ""
fi

# 3. Stash les modifications locales
echo "📥 Stashing local changes..."
git stash
echo ""

# 4. Pull les dernières modifications
echo "🔄 Pulling latest changes from GitHub..."
git pull origin main
echo ""

# 5. Restaurer la configuration
echo "📤 Restoring your config.yaml..."
cp config.yaml.backup config.yaml
echo "✅ Config restored"
echo ""

if [ -f ".env.backup" ]; then
    echo "📤 Restoring your .env..."
    cp .env.backup .env
    echo "✅ .env restored"
    echo ""
fi

# 6. Mettre à jour les dépendances Python
echo "📦 Updating Python dependencies..."
pip3 install -r requirements.txt --quiet --upgrade
echo "✅ Dependencies updated"
echo ""

# 7. Redémarrer le service
if systemctl is-active --quiet proxyox; then
    echo "🔄 Restarting ProxyOX service..."
    systemctl restart proxyox
    echo "✅ Service restarted"
    echo ""
fi

echo "====================================="
echo "✅ Update complete!"
echo "====================================="
echo ""
echo "Your configuration has been preserved:"
echo "  - config.yaml (your settings)"
echo "  - .env (your credentials)"
echo ""
echo "Backups available:"
echo "  - config.yaml.backup"
echo "  - .env.backup"
echo ""
echo "Check status: systemctl status proxyox"
echo "View logs: journalctl -u proxyox -f"
echo ""
