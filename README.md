# ProxyOX

A high-performance asynchronous proxy server with built-in monitoring dashboard.

## Features

- **Multi-Protocol Support**: TCP, UDP, and HTTP proxying
- **Asynchronous I/O**: Built with Python asyncio for high performance
- **Real-time Dashboard**: Web-based monitoring interface with live graphs
- **Authentication**: Secure dashboard access with HTTP Basic Auth
- **Flexible Configuration**: YAML-based configuration with frontend/backend separation
- **Statistics**: Track connections, requests, bytes transferred, packets, and more
- **Protocol Intelligence**: Special handling for HTTP/HTTPS with detailed metrics
- **Custom Naming**: Named proxies for easy identification in the dashboard
- **SSL/TLS Support**: Backend SSL encryption for TCP proxies
- **Global Statistics**: Aggregate metrics across all proxies

## Quick Start

### Manual Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/proxyox.git
cd proxyox
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create dashboard credentials file (`.env` in project root):
```env
DASHBOARD_USER=proxyox
DASHBOARD_PASS=changeme
```

4. Configure your proxies in `config.yaml` (see Configuration section below)

5. Run the proxy:
```bash
python src/main.py
```

6. Access the dashboard at `http://localhost:8080`

## Configuration

### Configuration Structure

ProxyOX uses a **frontend/backend** configuration model. Frontends define listening interfaces, while backends define target servers.

The `config.yaml` file structure:

```yaml
global:
  log-level: info          # Logging level (debug, info, warning, error)
  use-uvloop: false        # Use uvloop for better performance (Linux only)
  timeout: 300             # Connection timeout in seconds
  max-connections: 100     # Maximum concurrent connections per proxy

frontends:
  - name: http-redirect            # Friendly name for dashboard
    bind: 0.0.0.0:80              # Listen address:port
    mode: tcp                      # Protocol: tcp, udp, or http
    default_backend: tcp-https-server   # Backend name to forward to
    backend_ssl: true              # Enable SSL encryption to backend

  - name: tcp-fe
    bind: 0.0.0.0:443
    mode: tcp
    default_backend: tcp-https-server
    backend_ssl: false             # Passthrough mode (no SSL wrapping)

  - name: udp-fe
    bind: 127.0.0.1:9001
    mode: udp
    default_backend: udp-server

  - name: http-fe
    bind: 127.0.0.1:8081
    mode: http
    default_backend: http-server

backends:
  - name: tcp-https-server         # Backend name (referenced by frontends)
    server: 10.10.0.201:443        # Target server address:port

  - name: udp-server
    server: 10.10.0.201:9443

  - name: http-server
    server: 10.10.0.200:8006
```

### Protocol Modes

#### TCP Mode
- General-purpose TCP relay
- Supports backend SSL encryption (`backend_ssl: true`)
- Use cases: HTTPS forwarding, database proxying, custom protocols
- Metrics: Active connections, bytes sent/received

#### UDP Mode
- Stateless UDP relay
- Ideal for DNS, QUIC, gaming protocols
- Metrics: Packets sent/received, bytes sent/received

#### HTTP Mode
- HTTP/1.1 aware proxy
- Additional metrics: Request count, response times, HTTP methods
- Use cases: REST APIs, web services

### Frontend Options

| Option | Required | Description |
|--------|----------|-------------|
| `name` | Yes | Friendly name displayed in dashboard |
| `bind` | Yes | Listen address and port (e.g., `0.0.0.0:80`) |
| `mode` | Yes | Protocol type: `tcp`, `udp`, or `http` |
| `default_backend` | Yes | Backend name to forward traffic to |
| `backend_ssl` | No | (TCP only) Wrap backend connection in SSL/TLS |

### Backend Options

| Option | Required | Description |
|--------|----------|-------------|
| `name` | Yes | Unique backend identifier |
| `server` | Yes | Target server address and port |

### Example Configurations

#### HTTP to HTTPS Conversion
```yaml
frontends:
  - name: http-to-https
    bind: 0.0.0.0:80
    mode: tcp
    default_backend: https-server
    backend_ssl: true    # Converts plain HTTP to HTTPS

backends:
  - name: https-server
    server: 192.168.1.100:443
```

#### HTTPS Passthrough
```yaml
frontends:
  - name: https-passthrough
    bind: 0.0.0.0:443
    mode: tcp
    default_backend: web-server
    backend_ssl: false   # No SSL wrapping, passes encrypted traffic as-is

backends:
  - name: web-server
    server: 192.168.1.100:443
```

#### DNS Proxy
```yaml
frontends:
  - name: dns-proxy
    bind: 0.0.0.0:53
    mode: udp
    default_backend: cloudflare-dns

backends:
  - name: cloudflare-dns
    server: 1.1.1.1:53
```

## Dashboard

The dashboard runs on port **8080** by default and provides real-time monitoring.

### Authentication

Default credentials (change in `.env` file):
- Username: `proxyox`
- Password: `changeme`

⚠️ **Security Warning**: Change these credentials in the `.env` file after installation!

### Dashboard Features

Access the dashboard at `http://your-server:8080`

**Overview:**
- **Global Statistics**: Total connections, total requests, bytes sent/received across all proxies
- **Real-time Graphs**: Live charts with 1-second updates showing traffic patterns
- **Individual Proxy Cards**: Each proxy displays its custom name and protocol-specific metrics

**Per-Proxy Metrics:**
- **TCP Proxies**: Active connections, bytes sent/received, uptime
- **UDP Proxies**: Packets sent/received, bytes sent/received, uptime
- **HTTP Proxies**: Total requests, avg response time, bytes sent/received, uptime

**Interactive Features:**
- Search and filter proxies by name or protocol
- Click proxy cards for detailed modal view with configuration and activity graph
- Export data to CSV
- Adjustable refresh interval and chart history
- Toast notifications for connection status

**White Theme:** Clean, professional interface optimized for monitoring

## Requirements

- Python 3.11+
- aiohttp
- pyyaml
- structlog

## Project Structure

```
proxyox/
├── config.yaml           # Configuration file
├── .env                  # Dashboard credentials
├── requirements.txt      # Python dependencies
├── README.md            # This file
└── src/
    ├── main.py          # Entry point
    ├── config.py        # Configuration loader
    ├── dashboard/       # Web dashboard
    │   ├── __init__.py
    │   ├── app.py       # Web server & WebSocket
    │   └── static/
    │       └── index.html   # Dashboard UI
    └── proxy/           # Proxy implementations
        ├── __init__.py
        ├── manager.py   # Proxy manager
        ├── tcp.py       # TCP proxy
        ├── udp.py       # UDP proxy
        ├── http.py      # HTTP proxy
        ├── tls.py       # TLS utilities
        └── metrics.py   # Metrics tracking
```

## Uninstallation

If you used the `install.sh` script (Linux only):
```bash
sudo bash uninstall.sh
```

For manual installations, simply delete the project directory and `.env` file.

## License

MIT License - See LICENSE file for details

## Support

For issues and questions, please open an issue on the project repository.
