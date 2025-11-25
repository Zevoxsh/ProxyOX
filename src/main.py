import asyncio
import yaml
import structlog
import logging
import sys
import os
from pathlib import Path
from aiohttp import web
from dotenv import load_dotenv

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv(project_root / ".env")

# Handle imports whether running from project root or src directory
try:
    from src.proxy.manager import ProxyManager
    from src.dashboard.app import Dashboard
except ModuleNotFoundError:
    from proxy.manager import ProxyManager
    from dashboard.app import Dashboard

# Logging setup
logging.basicConfig(level=logging.INFO)
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    processors=[structlog.processors.KeyValueRenderer()]
)

async def main():
    """Main entrypoint for ProxyOX"""
    # Load config
    config_path = project_root / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    manager = ProxyManager()
    
    # Get global settings
    global_config = config.get("global", {})
    max_connections = global_config.get("max-connections", 100)
    rate_limit = global_config.get("rate-limit", 1000)

    # Start proxies from config
    for fe in config.get("frontends", []):
        print(f"🔍 DEBUG: Frontend raw data: {fe}")
        mode = fe.get("mode", "tcp").lower()
        print(f"🔍 DEBUG: Extracted mode='{mode}' from frontend '{fe.get('name')}'")
        listen_host, listen_port = fe["bind"].split(":")
        listen_port = int(listen_port)

        backend_name = fe.get("default_backend")
        backend = next((s for s in config.get("backends", []) if s["name"] == backend_name), None)
        
        target_host = None
        target_port = None
        backend_https = False
        
        if backend:
            target_host, target_port = backend["server"].split(":")
            target_port = int(target_port)
            backend_https = backend.get("https", False)
        
        use_tls = fe.get("tls", False)
        certfile = fe.get("certfile")
        keyfile = fe.get("keyfile")
        backend_ssl = fe.get("backend_ssl", False) or backend_https
        proxy_name = fe.get("name", f"{mode}_{listen_host}_{listen_port}")
        
        # Support pour les routes de domaines (reverse proxy)
        domain_routes = None
        if mode == "http" and "domain_routes" in fe:
            domain_routes = {}
            print(f"🔍 DEBUG: Found domain_routes in config for {proxy_name}")
            for route in fe["domain_routes"]:
                domain = route["domain"]
                route_backend_name = route["backend"]
                route_backend = next((s for s in config.get("backends", []) if s["name"] == route_backend_name), None)
                if route_backend:
                    route_host, route_port = route_backend["server"].split(":")
                    domain_routes[domain] = {
                        "host": route_host,
                        "port": int(route_port),
                        "https": route_backend.get("https", False)
                    }
                    print(f"  ✅ Route added: {domain} -> {route_host}:{route_port}")
                else:
                    print(f"  ❌ Backend not found: {route_backend_name}")
            print(f"🔍 Total routes configured: {len(domain_routes)}")
        else:
            print(f"🔍 No domain_routes for {proxy_name} (mode={mode}, has_routes={'domain_routes' in fe})")

        try:
            await manager.create_proxy(mode, listen_host, listen_port, target_host, target_port, 
                                      use_tls, certfile, keyfile, backend_ssl, backend_https, proxy_name, domain_routes, max_connections, rate_limit)
            backend_protocol = "HTTPS" if (backend_ssl or backend_https) else "HTTP"
            if domain_routes:
                print(f"✅ {mode.upper()} reverse proxy: {listen_host}:{listen_port} with {len(domain_routes)} domain routes")
            elif target_host:
                print(f"✅ {mode.upper()} proxy: {listen_host}:{listen_port} -> {target_host}:{target_port} ({backend_protocol})")
            else:
                print(f"✅ {mode.upper()} proxy: {listen_host}:{listen_port} (routing only)")
        except Exception as e:
            print(f"❌ FAILED to start {mode.upper()} proxy on {listen_host}:{listen_port}: {e}")

    print("✅ All proxies running. Starting dashboard...")

    # Start dashboard
    dashboard_host = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    dashboard_port = int(os.getenv("DASHBOARD_PORT", "8090"))
    
    dashboard = Dashboard(manager)
    app = dashboard.create_app()

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, dashboard_host, dashboard_port)
    await site.start()

    print(f"🌐 Dashboard running on http://{dashboard_host}:{dashboard_port}")
    print(f"🔐 Login required - check .env for credentials")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping all proxies and dashboard...")
        await manager.stop_all()
        await runner.cleanup()
        print("✅ All stopped.")

if __name__ == "__main__":
    asyncio.run(main())
