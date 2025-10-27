import json
from aiohttp import web, WSMsgType
import structlog
import asyncio
import mimetypes
import time
import base64
import os
from pathlib import Path
from dotenv import load_dotenv


logger = structlog.get_logger()

# Load environment variables
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"

# Load .env file
load_dotenv(env_path)

# Get credentials from environment
DASHBOARD_USERNAME = os.getenv("DASHBOARD_USERNAME", "proxyox")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "changeme")

# Log authentication settings (without showing password)
logger.info(f"Dashboard authentication configured", 
            username=DASHBOARD_USERNAME, 
            env_file_exists=env_path.exists(),
            password_set=bool(DASHBOARD_PASSWORD and DASHBOARD_PASSWORD != "changeme"))

# Configuration des types MIME
mimetypes.init()
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('application/json', '.json')

class Dashboard:
    def __init__(self, proxy_manager):
        self.proxy_manager = proxy_manager
        self.app = web.Application(middlewares=[self.auth_middleware])
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
    
    @web.middleware
    async def auth_middleware(self, request, handler):
        """Middleware to check authentication on all requests"""
        # Check authentication
        if not self.check_auth(request):
            return self.require_auth()
        
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
    
    def require_auth(self):
        """Return 401 response requiring authentication"""
        return web.Response(
            status=401,
            text='Authentication required',
            headers={
                'WWW-Authenticate': 'Basic realm="ProxyOX Dashboard"'
            }
        )

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
