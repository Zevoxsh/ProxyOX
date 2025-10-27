# ProxyOX - Multi-Protocol Proxy Manager

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)

ProxyOX is a professional multi-protocol proxy manager with a beautiful real-time monitoring dashboard.

## Features

- 🚀 **Multi-Protocol Support**: TCP, UDP, and HTTP proxying
- 📊 **Real-time Dashboard**: Beautiful web interface with live charts
- 📈 **Advanced Metrics**: Traffic monitoring, connection tracking, performance analytics
- ⚡ **High Performance**: Async architecture with aiohttp
- 🔧 **Easy Configuration**: Simple YAML configuration file
- 🐧 **Linux Ready**: Systemd service integration

## Quick Start

### One-Command Installation (Recommended)

Install ProxyOX directly from GitHub in one command:

```bash
curl -fsSL https://raw.githubusercontent.com/Zevoxsh/proxyox/main/install.sh | sudo bash
```

Or with wget:

```bash
wget -qO- https://raw.githubusercontent.com/Zevoxsh/proxyox/main/install.sh | sudo bash
```

### Manual Installation from GitHub

```bash
# Clone the repository
git clone https://github.com/Zevoxsh/proxyox.git
cd proxyox

# Run installation script
sudo bash install.sh

# Start the service
sudo systemctl start proxyox

# Check status
sudo systemctl status proxyox

# View logs
sudo journalctl -u proxyox -f
```

### Alternative: Clone and Install in One Line

```bash
git clone https://github.com/Zevoxsh/proxyox.git && cd proxyox && sudo bash install.sh
```

### Manual Installation

```bash
# Install Python dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env file from example
cp .env.example .env

# Edit credentials (optional)
nano .env

# Run manually
python src/main.py
```

## Configuration

### Authentication

ProxyOX uses HTTP Basic Authentication to secure the dashboard. Credentials are stored in the `.env` file:

```bash
# Edit /etc/proxyox/.env
DASHBOARD_USERNAME=proxyox
DASHBOARD_PASSWORD=your_secure_password_here
```

After changing credentials, restart the service:
```bash
sudo systemctl restart proxyox
```

**Default credentials** (automatically changed to a random password during installation):
- Username: `proxyox`
- Password: Displayed at the end of installation

### Proxy Configuration

Edit `config.yaml` to configure your proxies:

```yaml
dashboard:
  host: "0.0.0.0"
  port: 8080

proxies:
  - protocol: tcp
    listen: "0.0.0.0:8081"
    target: "example.com:80"
    
  - protocol: http
    listen: "0.0.0.0:8082"
    target: "http://backend.local:3000"
    
  - protocol: udp
    listen: "0.0.0.0:8083"
    target: "dns.server.com:53"
```

## Systemd Commands

```bash
# Start ProxyOX
sudo systemctl start proxyox

# Stop ProxyOX
sudo systemctl stop proxyox

# Restart ProxyOX
sudo systemctl restart proxyox

# Check status
sudo systemctl status proxyox

# Enable auto-start on boot
sudo systemctl enable proxyox

# Disable auto-start
sudo systemctl disable proxyox

# View logs
sudo journalctl -u proxyox -f

# View logs since boot
sudo journalctl -u proxyox -b
```

## Dashboard

Access the dashboard at `http://your-server:8080`

Features:
- Real-time traffic monitoring (10-second window)
- Active connections tracking
- Protocol distribution
- HTTP method statistics
- Connection history and logs
- System metrics

## Uninstallation

```bash
sudo bash uninstall.sh
```

## Requirements

- Python 3.8+
- Linux (for systemd service)
- aiohttp
- pyyaml
- structlog

## Project Structure

```
proxyox/
├── config.yaml           # Configuration file
├── install.sh           # Linux installation script
├── uninstall.sh         # Uninstallation script
├── README.md            # This file
└── src/
    ├── main.py          # Entry point
    ├── config.py        # Configuration loader
    ├── dashboard/       # Web dashboard
    │   ├── app.py
    │   └── static/
    │       ├── index.html
    │       └── dashboard-v2.js
    └── proxy/           # Proxy implementations
        ├── manager.py
        ├── tcp.py
        ├── udp.py
        └── http.py
```

## License

MIT License - See LICENSE file for details

## Support

For issues and questions, please open an issue on the project repository.
