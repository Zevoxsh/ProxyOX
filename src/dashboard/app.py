import json
from aiohttp import web, WSMsgType
import structlog
import asyncio
import mimetypes
import time
from pathlib import Path


logger = structlog.get_logger()

# Configuration des types MIME
mimetypes.init()
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('application/json', '.json')

# Get project root directory
project_root = Path(__file__).parent.parent.parent

class Dashboard:
    def __init__(self, proxy_manager):
        self.proxy_manager = proxy_manager
        self.app = web.Application()
        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/ws", self.websocket_handler)
        
        # Use absolute paths
        static_path = project_root / "src" / "dashboard" / "static"
        assets_path = static_path / "assets"
        
        self.app.router.add_static("/static/", path=str(static_path), name="static")
        if assets_path.exists():
            self.app.router.add_static("/assets/", path=str(assets_path), name="assets")

    def create_app(self):
        return self.app

    async def handle_index(self, request):
        index_path = project_root / "src" / "dashboard" / "static" / "index.html"
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        # Use new JS file name to bypass cache
        html = html.replace('dashboard.js?v=62', 'dashboard-v2.js')
        return web.Response(text=html, content_type="text/html")

    async def websocket_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        logger.info("Client connected to dashboard")

        try:
            while True:
                stats = self.proxy_manager.get_stats()
                await ws.send_str(json.dumps(stats))
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            await ws.close()
            logger.info("Client disconnected")
        return ws
