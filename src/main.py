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

from src.proxy.manager import ProxyManager
from src.dashboard.app import Dashboard

# --- Logging setup ---
logging.basicConfig(level=logging.INFO)
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    processors=[structlog.processors.KeyValueRenderer()]
)

# --- Main entrypoint ---
async def main():
    # Charger la config (use absolute path)
    config_path = project_root / "config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    manager = ProxyManager()

    # Démarrer les proxys définis dans la config
    for fe in config.get("frontends", []):
        mode = fe.get("mode", "tcp").lower()
        listen_host, listen_port = fe["bind"].split(":")
        listen_port = int(listen_port)

        backend_name = fe["default_backend"]
        server = next(s for s in config.get("backends", []) if s["name"] == backend_name)
        target_host, target_port = server["server"].split(":")
        target_port = int(target_port)

        # Support pour le mode TLS si nécessaire
        use_tls = fe.get("tls", False)
        certfile = fe.get("certfile")
        keyfile = fe.get("keyfile")

        try:
            await manager.create_proxy(mode, listen_host, listen_port, target_host, target_port, use_tls, certfile, keyfile)
            print(f"✅ {mode.upper()} proxy: {listen_host}:{listen_port} -> {target_host}:{target_port}")
        except Exception as e:
            print(f"❌ FAILED to start {mode.upper()} proxy on {listen_host}:{listen_port}: {e}")
            import traceback
            traceback.print_exc()
            # Continue avec les autres proxies

    print("✅ All proxies running. Starting dashboard...")

    # --- Lancer le dashboard web ---
    # Get dashboard settings from .env
    dashboard_host = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    dashboard_port = int(os.getenv("DASHBOARD_PORT", "8080"))
    
    dashboard = Dashboard(manager)
    app = dashboard.create_app()

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, dashboard_host, dashboard_port)
    await site.start()

    print(f"🌐 Dashboard running on http://{dashboard_host}:{dashboard_port}")
    print(f"🔐 Login required - check /etc/proxyox/.env for credentials")

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
