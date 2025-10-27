import asyncio
import yaml
import structlog
import logging
from aiohttp import web
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
    # Charger la config
    with open("config.yaml", "r") as f:
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

        await manager.create_proxy(mode, listen_host, listen_port, target_host, target_port)

    print("✅ All proxies running. Starting dashboard...")

    # --- Lancer le dashboard web ---
    dashboard = Dashboard(manager)
    app = dashboard.create_app()

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 9090)
    await site.start()

    print("🌐 Dashboard running on http://127.0.0.1:9090")

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
