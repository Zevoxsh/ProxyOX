import json
from aiohttp import web
import structlog
import asyncio
import base64
import os
import sys
import yaml
import signal
import csv
import platform
from io import StringIO
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

logger = structlog.get_logger()

# Get project root (ProxyOX directory)
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"

load_dotenv(env_path)

DASHBOARD_USERNAME = os.getenv("DASHBOARD_USERNAME", "proxyox")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "changeme")

logger.info("Dashboard authentication configured",
            username=DASHBOARD_USERNAME,
            env_file_exists=env_path.exists(),
            password_set=bool(DASHBOARD_PASSWORD and DASHBOARD_PASSWORD != "changeme"))

class Dashboard:
    def __init__(self, proxy_manager):
        self.proxy_manager = proxy_manager
        self.app = web.Application(middlewares=[self.auth_middleware])
        self.maintenance_mode = False
        self.connection_history = []
        self.max_history = 1000
        
        # Routes API
        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/ws", self.websocket_handler)
        self.app.router.add_get("/api/stats", self.api_stats)
        self.app.router.add_post("/api/restart", self.api_restart)
        self.app.router.add_post("/api/reload-config", self.api_reload_config)
        self.app.router.add_get("/api/config/validate", self.api_validate_config)
        self.app.router.add_get("/api/export/json", self.api_export_json)
        self.app.router.add_get("/api/export/csv", self.api_export_csv)
        self.app.router.add_get("/api/history", self.api_connection_history)
        self.app.router.add_post("/api/maintenance", self.api_toggle_maintenance)
        self.app.router.add_get("/api/system/info", self.api_system_info)
        self.app.router.add_post("/api/proxy/{proxy_name}/stop", self.api_stop_proxy)
        self.app.router.add_post("/api/proxy/{proxy_name}/start", self.api_start_proxy)
        
        # Serve static files
        static_path = Path(__file__).parent / "static"
        if static_path.exists():
            self.app.router.add_static("/static/", path=str(static_path), name="static")
            assets_path = static_path / "assets"
            if assets_path.exists():
                self.app.router.add_static("/assets/", path=str(assets_path), name="assets")

    def create_app(self):
        return self.app

    @web.middleware
    async def auth_middleware(self, request, handler):
        """Middleware to check authentication on all requests"""
        # Exclure les fichiers statiques et le WebSocket de l'authentification
        if (request.path.startswith('/assets/') or 
            request.path.startswith('/static/') or
            request.path == '/ws'):
            return await handler(request)
        
        # Authentification requise pour la page principale et les APIs
        if not self.check_auth(request):
            return web.Response(
                status=401,
                text='Authentication required',
                headers={'WWW-Authenticate': 'Basic realm="ProxyOX Dashboard"'}
            )
        return await handler(request)

    def check_auth(self, request):
        """Check HTTP Basic Authentication"""
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return False

        try:
            scheme, credentials = auth_header.split(' ', 1)
            if scheme.lower() != 'basic':
                return False

            decoded = base64.b64decode(credentials).decode('utf-8')
            username, password = decoded.split(':', 1)

            return username == DASHBOARD_USERNAME and password == DASHBOARD_PASSWORD
        except Exception:
            return False

    async def handle_index(self, request):
        """Serve the dashboard"""
        dashboard_path = Path(__file__).parent / "static" / "index.html"
        with open(dashboard_path, "r", encoding="utf-8") as f:
            html = f.read()
        return web.Response(text=html, content_type="text/html")

    async def websocket_handler(self, request):
        """Handle WebSocket connections for real-time stats"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        logger.info("Client connected to dashboard")

        try:
            while True:
                stats = self.proxy_manager.get_stats()
                stats['maintenance_mode'] = self.maintenance_mode
                stats['timestamp'] = datetime.now().isoformat()
                
                # Log pour debug
                logger.debug(f"Sending stats: {len(stats.get('proxies', []))} proxies")
                for proxy in stats.get('proxies', []):
                    logger.debug(f"  - {proxy['name']}: {proxy.get('stats', {})}")
                
                await ws.send_str(json.dumps(stats))
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            await ws.close()
            logger.info("Client disconnected")
        return ws
    
    async def api_stats(self, request):
        """API endpoint for current stats"""
        stats = self.proxy_manager.get_stats()
        stats['maintenance_mode'] = self.maintenance_mode
        stats['timestamp'] = datetime.now().isoformat()
        return web.json_response(stats)
    
    async def api_restart(self, request):
        """API endpoint to restart the service"""
        try:
            logger.info("🔄 Restart requested via API")
            
            # Schedule restart after sending response
            asyncio.create_task(self._delayed_restart())
            
            return web.json_response({
                "status": "success",
                "message": "Service restart initiated. Restarting in 2 seconds...",
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Restart failed: {e}")
            return web.json_response({
                "status": "error",
                "message": str(e)
            }, status=500)
    
    async def _delayed_restart(self):
        """Delayed restart to allow response to be sent"""
        await asyncio.sleep(2)
        logger.info("🔄 Executing service restart...")
        
        # On Unix/Linux
        if platform.system() != "Windows":
            os.kill(os.getpid(), signal.SIGTERM)
        else:
            # On Windows
            os.kill(os.getpid(), signal.SIGTERM)
    
    async def api_reload_config(self, request):
        """API endpoint to reload configuration"""
        try:
            logger.info("📋 Configuration reload requested via API")
            
            # Validate config first
            config_path = project_root / "config.yaml"
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            
            # Basic validation
            if "frontends" not in config or "backends" not in config:
                return web.json_response({
                    "status": "error",
                    "message": "Invalid configuration: missing frontends or backends"
                }, status=400)
            
            return web.json_response({
                "status": "success",
                "message": "Configuration validated. Please restart the service to apply changes.",
                "timestamp": datetime.now().isoformat()
            })
        except yaml.YAMLError as e:
            logger.error(f"Config reload failed: {e}")
            return web.json_response({
                "status": "error",
                "message": f"YAML parsing error: {str(e)}"
            }, status=400)
        except Exception as e:
            logger.error(f"Config reload failed: {e}")
            return web.json_response({
                "status": "error",
                "message": str(e)
            }, status=500)
    
    async def api_validate_config(self, request):
        """Validate configuration file"""
        try:
            config_path = project_root / "config.yaml"
            
            # Check file exists
            if not config_path.exists():
                return web.json_response({
                    "status": "error",
                    "valid": False,
                    "message": "Configuration file not found"
                }, status=404)
            
            # Try to parse YAML
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            
            # Basic validation
            errors = []
            warnings = []
            
            if not isinstance(config, dict):
                errors.append("Config must be a dictionary")
            
            if "frontends" not in config:
                errors.append("Missing 'frontends' section")
            elif not isinstance(config["frontends"], list):
                errors.append("'frontends' must be a list")
            
            if "backends" not in config:
                errors.append("Missing 'backends' section")
            elif not isinstance(config["backends"], list):
                errors.append("'backends' must be a list")
            
            # Validate frontends
            backend_names = {be.get("name") for be in config.get("backends", []) if "name" in be}
            
            for idx, fe in enumerate(config.get("frontends", [])):
                fe_name = fe.get("name", f"Frontend #{idx + 1}")
                
                if "bind" not in fe:
                    errors.append(f"{fe_name}: missing 'bind' address")
                
                if "default_backend" not in fe and "domain_routes" not in fe:
                    errors.append(f"{fe_name}: must specify 'default_backend' or 'domain_routes'")
                
                # Check backend references
                if "default_backend" in fe and fe["default_backend"] not in backend_names:
                    errors.append(f"{fe_name}: references non-existent backend '{fe['default_backend']}'")
                
                # Check domain routes
                if "domain_routes" in fe:
                    for route in fe.get("domain_routes", []):
                        if "backend" in route and route["backend"] not in backend_names:
                            errors.append(f"{fe_name}: route references non-existent backend '{route['backend']}'")
            
            # Validate backends
            seen_names = set()
            for idx, be in enumerate(config.get("backends", [])):
                if "name" not in be:
                    errors.append(f"Backend #{idx + 1}: missing 'name'")
                else:
                    if be["name"] in seen_names:
                        errors.append(f"Backend '{be['name']}': duplicate name")
                    seen_names.add(be["name"])
                
                if "server" not in be:
                    errors.append(f"Backend #{idx + 1}: missing 'server' address")
            
            return web.json_response({
                "status": "success" if len(errors) == 0 else "error",
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "message": "Configuration is valid ✅" if len(errors) == 0 else f"Found {len(errors)} error(s) ❌",
                "timestamp": datetime.now().isoformat()
            })
        except yaml.YAMLError as e:
            return web.json_response({
                "status": "error",
                "valid": False,
                "message": f"YAML parsing error: {str(e)}",
                "errors": [str(e)],
                "warnings": []
            }, status=400)
        except Exception as e:
            logger.error(f"Config validation failed: {e}")
            return web.json_response({
                "status": "error",
                "message": str(e)
            }, status=500)
    
    async def api_export_json(self, request):
        """Export current stats as JSON"""
        try:
            stats = self.proxy_manager.get_stats()
            stats['exported_at'] = datetime.now().isoformat()
            stats['maintenance_mode'] = self.maintenance_mode
            
            filename = f"proxyox_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            return web.Response(
                text=json.dumps(stats, indent=2),
                content_type='application/json',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"'
                }
            )
        except Exception as e:
            logger.error(f"Export JSON failed: {e}")
            return web.json_response({
                "status": "error",
                "message": str(e)
            }, status=500)
    
    async def api_export_csv(self, request):
        """Export current stats as CSV"""
        try:
            stats = self.proxy_manager.get_stats()
            
            output = StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow([
                'Proxy Name', 'Protocol', 'Listen Address', 'Target Address',
                'Status', 'Uptime (s)', 'Backend SSL', 
                'Bytes Sent', 'Bytes Received', 'Connections/Requests'
            ])
            
            # Data rows
            for proxy in stats.get('proxies', []):
                stat_values = proxy.get('stats', {})
                writer.writerow([
                    proxy.get('name', 'N/A'),
                    proxy.get('protocol', 'N/A'),
                    proxy.get('listen', 'N/A'),
                    proxy.get('target', 'N/A'),
                    proxy.get('status', 'N/A'),
                    proxy.get('uptime', 0),
                    proxy.get('backend_ssl', False),
                    stat_values.get('bytes_sent', 0),
                    stat_values.get('bytes_received', 0),
                    stat_values.get('total_connections', stat_values.get('requests', 0))
                ])
            
            filename = f"proxyox_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            return web.Response(
                text=output.getvalue(),
                content_type='text/csv',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"'
                }
            )
        except Exception as e:
            logger.error(f"Export CSV failed: {e}")
            return web.json_response({
                "status": "error",
                "message": str(e)
            }, status=500)
    
    async def api_connection_history(self, request):
        """Get connection history"""
        limit = int(request.query.get('limit', 100))
        return web.json_response({
            "history": self.connection_history[-limit:],
            "total": len(self.connection_history)
        })
    
    async def api_toggle_maintenance(self, request):
        """Toggle maintenance mode"""
        try:
            data = await request.json()
            enabled = data.get('enabled', not self.maintenance_mode)
            self.maintenance_mode = enabled
            
            logger.info(f"🔧 Maintenance mode {'enabled' if enabled else 'disabled'}")
            
            return web.json_response({
                "status": "success",
                "maintenance_mode": self.maintenance_mode,
                "message": f"Maintenance mode {'enabled ⚠️' if enabled else 'disabled ✅'}",
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Toggle maintenance failed: {e}")
            return web.json_response({
                "status": "error",
                "message": str(e)
            }, status=500)
    
    async def api_system_info(self, request):
        """Get system information"""
        try:
            import psutil
            
            return web.json_response({
                "system": {
                    "platform": platform.system(),
                    "platform_release": platform.release(),
                    "platform_version": platform.version(),
                    "architecture": platform.machine(),
                    "hostname": platform.node(),
                    "python_version": platform.python_version(),
                },
                "resources": {
                    "cpu_percent": psutil.cpu_percent(interval=1),
                    "cpu_count": psutil.cpu_count(),
                    "memory_total": psutil.virtual_memory().total,
                    "memory_available": psutil.virtual_memory().available,
                    "memory_percent": psutil.virtual_memory().percent,
                    "disk_usage": {
                        "total": psutil.disk_usage('/').total,
                        "used": psutil.disk_usage('/').used,
                        "free": psutil.disk_usage('/').free,
                        "percent": psutil.disk_usage('/').percent,
                    }
                },
                "timestamp": datetime.now().isoformat()
            })
        except ImportError:
            return web.json_response({
                "status": "warning",
                "message": "Install psutil for detailed system information: pip install psutil",
                "system": {
                    "platform": platform.system(),
                    "python_version": platform.python_version(),
                },
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"System info failed: {e}")
            return web.json_response({
                "status": "error",
                "message": str(e)
            }, status=500)
    
    async def api_stop_proxy(self, request):
        """Stop a specific proxy"""
        proxy_name = request.match_info['proxy_name']
        
        try:
            # Find and stop the proxy
            proxy = None
            if proxy_name in self.proxy_manager.tcp_proxies:
                proxy = self.proxy_manager.tcp_proxies[proxy_name]
            elif proxy_name in self.proxy_manager.udp_proxies:
                proxy = self.proxy_manager.udp_proxies[proxy_name]
            elif proxy_name in self.proxy_manager.http_proxies:
                proxy = self.proxy_manager.http_proxies[proxy_name]
            
            if proxy:
                await proxy.stop()
                logger.info(f"🛑 Stopped proxy: {proxy_name}")
                return web.json_response({
                    "status": "success",
                    "message": f"Proxy '{proxy_name}' stopped",
                    "timestamp": datetime.now().isoformat()
                })
            else:
                return web.json_response({
                    "status": "error",
                    "message": f"Proxy '{proxy_name}' not found"
                }, status=404)
        except Exception as e:
            logger.error(f"Stop proxy failed: {e}")
            return web.json_response({
                "status": "error",
                "message": str(e)
            }, status=500)
    
    async def api_start_proxy(self, request):
        """Start a specific proxy"""
        proxy_name = request.match_info['proxy_name']
        
        try:
            # Find and start the proxy
            proxy = None
            if proxy_name in self.proxy_manager.tcp_proxies:
                proxy = self.proxy_manager.tcp_proxies[proxy_name]
            elif proxy_name in self.proxy_manager.udp_proxies:
                proxy = self.proxy_manager.udp_proxies[proxy_name]
            elif proxy_name in self.proxy_manager.http_proxies:
                proxy = self.proxy_manager.http_proxies[proxy_name]
            
            if proxy:
                await proxy.start()
                logger.info(f"✅ Started proxy: {proxy_name}")
                return web.json_response({
                    "status": "success",
                    "message": f"Proxy '{proxy_name}' started",
                    "timestamp": datetime.now().isoformat()
                })
            else:
                return web.json_response({
                    "status": "error",
                    "message": f"Proxy '{proxy_name}' not found"
                }, status=404)
        except Exception as e:
            logger.error(f"Start proxy failed: {e}")
            return web.json_response({
                "status": "error",
                "message": str(e)
            }, status=500)

