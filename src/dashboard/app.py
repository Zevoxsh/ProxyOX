"""
ProxyOX Professional Dashboard with JWT Authentication and Database
"""
import json
from aiohttp import web
import structlog
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.mysql_manager import MySQLDatabaseManager
from auth import AuthManager
from security.rate_limiter import RateLimiter

logger = structlog.get_logger()

def serialize_datetime(obj):
    """Convert datetime objects to ISO format strings for JSON serialization"""
    if isinstance(obj, dict):
        return {k: serialize_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    return obj

class Dashboard:
    """Professional dashboard with JWT auth and database backend"""
    
    def __init__(self, proxy_manager, mysql_host: str, mysql_port: int, 
                 mysql_user: str, mysql_password: str, mysql_database: str):
        """Initialize dashboard"""
        self.proxy_manager = proxy_manager
        self.db = MySQLDatabaseManager(
            host=mysql_host,
            port=mysql_port,
            user=mysql_user,
            password=mysql_password,
            database=mysql_database
        )
        self.auth: Optional[AuthManager] = None
        
        # Initialize rate limiter for login protection (5 attempts per 5 minutes)
        self.login_limiter = RateLimiter(max_attempts=5, window_seconds=300)
        
        # Setup app with middleware
        self.app = web.Application(middlewares=[
            self.cors_middleware,
            self.auth_middleware
        ])
        
        self._setup_routes()
        
    async def initialize(self):
        """Initialize database and auth"""
        await self.db.initialize()
        
        # Get JWT secret from environment (SECURITY: never store in database)
        jwt_secret = os.getenv('JWT_SECRET')
        if not jwt_secret:
            raise ValueError("JWT_SECRET must be set in .env file")
        
        jwt_expiry = int(os.getenv('JWT_EXPIRY', '3600'))
        refresh_expiry = int(os.getenv('REFRESH_TOKEN_EXPIRY', '604800'))
        
        self.auth = AuthManager(
            self.db,
            jwt_secret=jwt_secret,
            jwt_expiry=jwt_expiry,
            refresh_expiry=refresh_expiry
        )
        
        logger.info("Dashboard initialized with database backend")
        
    def _setup_routes(self):
        """Setup all API routes"""
        
        # ===== PUBLIC ROUTES (no auth required) =====
        self.app.router.add_post("/api/auth/login", self.api_login)
        
        # ===== DASHBOARD =====
        self.app.router.add_get("/", self.handle_dashboard)
        self.app.router.add_get("/ws", self.websocket_handler)
        
        # ===== AUTH ROUTES =====
        self.app.router.add_post("/api/auth/logout", self.api_logout)
        self.app.router.add_post("/api/auth/refresh", self.api_refresh_token)
        self.app.router.add_get("/api/auth/me", self.api_current_user)
        
        # ===== PROXY MANAGEMENT =====
        self.app.router.add_get("/api/proxies", self.api_list_proxies)
        self.app.router.add_get("/api/proxies/{proxy_id}", self.api_get_proxy)
        self.app.router.add_post("/api/proxies", self.api_create_proxy)
        self.app.router.add_put("/api/proxies/{proxy_id}", self.api_update_proxy)
        self.app.router.add_delete("/api/proxies/{proxy_id}", self.api_delete_proxy)
        
        # Proxy control
        self.app.router.add_post("/api/proxies/{proxy_id}/start", self.api_start_proxy)
        self.app.router.add_post("/api/proxies/{proxy_id}/stop", self.api_stop_proxy)
        self.app.router.add_post("/api/proxies/{proxy_id}/restart", self.api_restart_proxy)
        
        # ===== BACKEND MANAGEMENT =====
        self.app.router.add_get("/api/backends", self.api_list_backends)
        self.app.router.add_get("/api/backends/{backend_id}", self.api_get_backend)
        self.app.router.add_post("/api/backends", self.api_create_backend)
        self.app.router.add_put("/api/backends/{backend_id}", self.api_update_backend)
        self.app.router.add_delete("/api/backends/{backend_id}", self.api_delete_backend)
        
        # ===== DOMAIN ROUTING =====
        self.app.router.add_get("/api/domain-routes", self.api_list_domain_routes)
        self.app.router.add_get("/api/proxies/{proxy_id}/routes", self.api_get_proxy_routes)
        self.app.router.add_post("/api/domain-routes", self.api_create_domain_route)
        self.app.router.add_delete("/api/domain-routes/{route_id}", self.api_delete_domain_route)
        
        # ===== IP FILTERING =====
        self.app.router.add_get("/api/ip-filters", self.api_list_ip_filters)
        self.app.router.add_post("/api/ip-filters", self.api_add_ip_filter)
        self.app.router.add_delete("/api/ip-filters/{filter_id}", self.api_remove_ip_filter)
        
        # ===== STATISTICS =====
        self.app.router.add_get("/api/stats", self.api_stats)
        self.app.router.add_get("/api/stats/export/json", self.api_export_json)
        self.app.router.add_get("/api/stats/export/csv", self.api_export_csv)
        
        # ===== TRAFFIC HISTORY =====
        self.app.router.add_post("/api/traffic-history/save", self.api_save_traffic_history)
        self.app.router.add_get("/api/traffic-history/{date}", self.api_get_traffic_history)
        
        # ===== SETTINGS =====
        self.app.router.add_get("/api/settings", self.api_list_settings)
        self.app.router.add_put("/api/settings/{key}", self.api_update_setting)
        
        # ===== AUDIT LOGS =====
        self.app.router.add_get("/api/audit-logs", self.api_list_audit_logs)
        
        # ===== SYSTEM =====
        self.app.router.add_get("/api/system/info", self.api_system_info)
        self.app.router.add_post("/api/system/reload", self.api_reload_config)
        
        # ===== STATIC FILES =====
        static_path = Path(__file__).parent / "static"
        if static_path.exists():
            self.app.router.add_static("/static/", path=str(static_path), name="static")
            assets_path = static_path / "assets"
            if assets_path.exists():
                self.app.router.add_static("/assets/", path=str(assets_path), name="assets")
                
    @web.middleware
    async def cors_middleware(self, request, handler):
        """CORS middleware for API access"""
        if request.method == "OPTIONS":
            return web.Response(
                headers={
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, Authorization'
                }
            )
            
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
        
    @web.middleware
    async def auth_middleware(self, request, handler):
        """JWT authentication middleware"""
        logger.info("🔒 AUTH MIDDLEWARE CALLED", path=request.path, method=request.method)
        
        # Public routes (no auth required)
        public_routes = [
            '/api/auth/login',
            '/api/auth/refresh',  # Add refresh to public routes
            '/static/',
            '/assets/',
            '/ws',
            '/favicon.ico'
        ]
        
        # Exact match routes (don't use startswith)
        public_exact_routes = [
            '/',  # Dashboard page itself (login form is there)
        ]
        
        # Public GET-only routes (read access without auth)
        public_get_routes = [
            '/api/stats',
            '/api/proxies',
            '/api/backends',
            '/api/domain-routes',
            '/api/ip-filters',
            '/api/traffic-history'
        ]
        
        # Check if route is public (with startswith for directories)
        for route in public_routes:
            if request.path == route or request.path.startswith(route):
                logger.info("✅ Public route matched", route=route, path=request.path)
                request['user'] = None
                return await handler(request)
        
        # Check exact match routes
        for route in public_exact_routes:
            if request.path == route:
                logger.info("✅ Public exact route matched", route=route, path=request.path)
                request['user'] = None
                return await handler(request)
        
        # Check if it's a public GET route
        if request.method == 'GET':
            for route in public_get_routes:
                if request.path == route or request.path.startswith(route):
                    logger.info("✅ Public GET route matched", route=route, path=request.path)
                    request['user'] = None
                    return await handler(request)
        
        logger.info("⚠️ Auth required route", path=request.path, method=request.method)
        
        # Debug: log auth header
        auth_header = request.headers.get('Authorization')
        logger.info("Auth middleware check", path=request.path, method=request.method, has_auth_header=bool(auth_header), auth_preview=auth_header[:30] if auth_header else None)
        
        # Check if auth is initialized
        if not self.auth:
            logger.error("Auth manager not initialized!", path=request.path)
            return web.json_response(
                {'error': 'Server not ready', 'code': 'SERVER_ERROR'},
                status=500
            )
        
        # Verify JWT token
        user = await self.auth.require_auth(request)
        
        if not user:
            logger.warning("Auth failed - no user returned", path=request.path, method=request.method, has_header=bool(auth_header))
            return web.json_response(
                {'error': 'Authentication required', 'code': 'AUTH_REQUIRED'},
                status=401
            )
            
        # Attach user to request
        request['user'] = user
        logger.info("Auth success - user attached", user_id=user['id'], username=user['username'], path=request.path)
        
        return await handler(request)
        
    def create_app(self):
        """Create and return aiohttp app"""
        return self.app
        
    # ========== AUTHENTICATION ENDPOINTS ==========
    
    async def api_login(self, request):
        """Login endpoint - returns JWT tokens"""
        try:
            data = await request.json()
            username = data.get('username')
            password = data.get('password')
            
            if not username or not password:
                return web.json_response(
                    {'error': 'Username and password required'},
                    status=400
                )
            
            # Check rate limit
            ip_address = request.remote
            if not await self.login_limiter.is_allowed(ip_address):
                block_info = await self.login_limiter.get_block_info(ip_address)
                if block_info:
                    _, blocked_until = block_info
                    retry_after = int((blocked_until - datetime.now()).total_seconds())
                    logger.warning("Login rate limit exceeded", ip=ip_address)
                    return web.json_response(
                        {
                            'error': 'Too many login attempts',
                            'retry_after': retry_after
                        },
                        status=429
                    )
                
            # Get client info
            user_agent = request.headers.get('User-Agent')
            
            # Authenticate
            result = await self.auth.authenticate(
                username, password, ip_address, user_agent
            )
            
            if not result:
                logger.warning("Login failed", username=username, ip=ip_address)
                return web.json_response(
                    {'error': 'Invalid credentials'},
                    status=401
                )
                
            access_token, refresh_token, user_data = result
            
            return web.json_response({
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': 'Bearer',
                'expires_in': self.auth.jwt_expiry,
                'user': user_data
            })
            
        except Exception as e:
            logger.error("Login error", error=str(e))
            return web.json_response(
                {'error': 'Internal server error'},
                status=500
            )
            
    async def api_logout(self, request):
        """Logout endpoint - invalidate session"""
        try:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header[7:]
                await self.auth.logout(token)
                
            return web.json_response({'message': 'Logged out successfully'})
            
        except Exception as e:
            logger.error("Logout error", error=str(e))
            return web.json_response({'error': 'Internal server error'}, status=500)
            
    async def api_refresh_token(self, request):
        """Refresh access token"""
        try:
            data = await request.json()
            refresh_token = data.get('refresh_token')
            
            if not refresh_token:
                return web.json_response(
                    {'error': 'Refresh token required'},
                    status=400
                )
                
            new_access_token = await self.auth.refresh_access_token(refresh_token)
            
            if not new_access_token:
                return web.json_response(
                    {'error': 'Invalid refresh token'},
                    status=401
                )
                
            return web.json_response({
                'access_token': new_access_token,
                'token_type': 'Bearer',
                'expires_in': self.auth.jwt_expiry
            })
            
        except Exception as e:
            logger.error("Token refresh error", error=str(e))
            return web.json_response({'error': 'Internal server error'}, status=500)
            
    async def api_current_user(self, request):
        """Get current user info"""
        return web.json_response({'user': request['user']})
        
    # ========== PROXY ENDPOINTS ==========
    
    async def api_list_proxies(self, request):
        """List all proxies"""
        try:
            enabled_only = request.query.get('enabled') == 'true'
            proxies = await self.db.list_proxies(enabled_only)
            
            # Add runtime status from proxy_manager and update status field
            for proxy in proxies:
                runtime_status = self.proxy_manager.get_proxy_status(proxy['name'])
                if runtime_status:
                    proxy['runtime_status'] = runtime_status
                    # Update status field with actual runtime status
                    proxy['status'] = runtime_status.get('status', 'stopped')
                    # Add total_requests from runtime status for graphing
                    proxy['total_requests'] = runtime_status.get('total', 0)
                    proxy['active_requests'] = runtime_status.get('active', 0)
                    proxy['failed_requests'] = runtime_status.get('failed', 0)
                else:
                    proxy['runtime_status'] = {}
                    proxy['status'] = 'stopped'
                    proxy['total_requests'] = 0
                    proxy['active_requests'] = 0
                    proxy['failed_requests'] = 0
            
            # Serialize datetime objects
            proxies = serialize_datetime(proxies)
            
            return web.json_response({'proxies': proxies})
            
        except Exception as e:
            logger.error("List proxies error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    async def api_get_proxy(self, request):
        """Get single proxy"""
        try:
            proxy_id = int(request.match_info['proxy_id'])
            proxy = await self.db.get_proxy(proxy_id)
            
            if not proxy:
                return web.json_response({'error': 'Proxy not found'}, status=404)
                
            # Add runtime status
            runtime_status = self.proxy_manager.get_proxy_status(proxy['name'])
            proxy['runtime_status'] = runtime_status or {}
            
            # Get domain routes
            routes = await self.db.list_domain_routes(proxy_id)
            proxy['domain_routes'] = routes
            
            proxy = serialize_datetime(proxy)
            return web.json_response({'proxy': proxy})
            
        except Exception as e:
            logger.error("Get proxy error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    async def api_create_proxy(self, request):
        """Create new proxy"""
        try:
            data = await request.json()
            
            # Get user from request (set by auth middleware)
            user = request.get('user')
            
            if not user:
                logger.error("Create proxy failed: No user in request")
                return web.json_response(
                    {'error': 'Authentication required'},
                    status=401
                )
            
            # Validate required fields
            required = ['name', 'bind_address', 'bind_port', 'mode']
            for field in required:
                if field not in data:
                    return web.json_response(
                        {'error': f'Missing required field: {field}'},
                        status=400
                    )
            
            # Validate backend if provided
            if 'default_backend_id' in data and data['default_backend_id']:
                backend = await self.db.get_backend(data['default_backend_id'])
                if not backend:
                    return web.json_response(
                        {'error': f'Backend with ID {data["default_backend_id"]} not found'},
                        status=400
                    )
                    
            proxy_id = await self.db.create_proxy(data, user['id'])
            
            # Reload only this proxy (not all proxies)
            proxy = await self.db.get_proxy(proxy_id)
            if proxy:
                try:
                    await self.proxy_manager.reload_single_proxy_from_db(proxy['name'])
                    await self.proxy_manager.start_proxy(proxy['name'])
                    logger.info("Auto-started proxy", name=proxy['name'])
                except Exception as e:
                    logger.warning("Failed to auto-start proxy", name=proxy['name'], error=str(e))
            
            return web.json_response({
                'message': 'Proxy created successfully',
                'proxy_id': proxy_id
            }, status=201)
            
        except Exception as e:
            logger.error("Create proxy error", error=str(e), exc_info=True)
            return web.json_response({'error': str(e)}, status=500)
            
    async def api_update_proxy(self, request):
        """Update proxy"""
        try:
            proxy_id = int(request.match_info['proxy_id'])
            data = await request.json()
            
            user = request.get('user')
            if not user:
                return web.json_response({'error': 'Authentication required'}, status=401)
            
            await self.db.update_proxy(proxy_id, data, user['id'])
            
            # Reload only this proxy (not all proxies)
            proxy = await self.db.get_proxy(proxy_id)
            if proxy:
                try:
                    # Reload from DB and restart with new config
                    await self.proxy_manager.reload_single_proxy_from_db(proxy['name'])
                    await self.proxy_manager.start_proxy(proxy['name'])
                    logger.info("Auto-restarted proxy", name=proxy['name'])
                except Exception as e:
                    logger.warning("Failed to auto-restart proxy", name=proxy['name'], error=str(e))
            
            return web.json_response({'message': 'Proxy updated successfully'})
            
        except Exception as e:
            logger.error("Update proxy error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    async def api_delete_proxy(self, request):
        """Delete proxy"""
        try:
            proxy_id = int(request.match_info['proxy_id'])
            
            user = request.get('user')
            if not user:
                return web.json_response({'error': 'Authentication required'}, status=401)
            
            # Stop proxy first if running
            proxy = await self.db.get_proxy(proxy_id)
            if proxy:
                await self.proxy_manager.stop_proxy(proxy['name'])
                
            await self.db.delete_proxy(proxy_id, user['id'])
            
            return web.json_response({'message': 'Proxy deleted successfully'})
            
        except Exception as e:
            logger.error("Delete proxy error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    async def api_start_proxy(self, request):
        """Start proxy"""
        try:
            proxy_id = int(request.match_info['proxy_id'])
            proxy = await self.db.get_proxy(proxy_id)
            
            if not proxy:
                return web.json_response({'error': 'Proxy not found'}, status=404)
                
            success = await self.proxy_manager.start_proxy(proxy['name'])
            
            if success:
                return web.json_response({'message': f"Proxy '{proxy['name']}' started"})
            else:
                return web.json_response(
                    {'error': f"Failed to start proxy '{proxy['name']}'"},
                    status=500
                )
                
        except Exception as e:
            logger.error("Start proxy error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    async def api_stop_proxy(self, request):
        """Stop proxy"""
        try:
            proxy_id = int(request.match_info['proxy_id'])
            proxy = await self.db.get_proxy(proxy_id)
            
            if not proxy:
                return web.json_response({'error': 'Proxy not found'}, status=404)
                
            success = await self.proxy_manager.stop_proxy(proxy['name'])
            
            if success:
                return web.json_response({'message': f"Proxy '{proxy['name']}' stopped"})
            else:
                return web.json_response(
                    {'error': f"Failed to stop proxy '{proxy['name']}'"},
                    status=500
                )
                
        except Exception as e:
            logger.error("Stop proxy error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    async def api_restart_proxy(self, request):
        """Restart proxy"""
        try:
            proxy_id = int(request.match_info['proxy_id'])
            proxy = await self.db.get_proxy(proxy_id)
            
            if not proxy:
                return web.json_response({'error': 'Proxy not found'}, status=404)
                
            await self.proxy_manager.stop_proxy(proxy['name'])
            await asyncio.sleep(0.5)
            success = await self.proxy_manager.start_proxy(proxy['name'])
            
            if success:
                return web.json_response({'message': f"Proxy '{proxy['name']}' restarted"})
            else:
                return web.json_response(
                    {'error': f"Failed to restart proxy '{proxy['name']}'"},
                    status=500
                )
                
        except Exception as e:
            logger.error("Restart proxy error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    # ========== BACKEND ENDPOINTS ==========
    
    async def api_list_backends(self, request):
        """List all backends"""
        try:
            enabled_only = request.query.get('enabled') == 'true'
            backends = await self.db.list_backends(enabled_only)
            backends = serialize_datetime(backends)
            return web.json_response({'backends': backends})
            
        except Exception as e:
            logger.error("List backends error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    async def api_get_backend(self, request):
        """Get single backend"""
        try:
            backend_id = int(request.match_info['backend_id'])
            backend = await self.db.get_backend(backend_id)
            
            if not backend:
                return web.json_response({'error': 'Backend not found'}, status=404)
            
            backend = serialize_datetime(backend)
            return web.json_response({'backend': backend})
            
        except Exception as e:
            logger.error("Get backend error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    async def api_create_backend(self, request):
        """Create new backend"""
        try:
            data = await request.json()
            
            user = request.get('user')
            if not user:
                return web.json_response({'error': 'Authentication required'}, status=401)
            
            # Validate required fields
            required = ['name', 'server_address', 'server_port']
            for field in required:
                if field not in data:
                    return web.json_response(
                        {'error': f'Missing required field: {field}'},
                        status=400
                    )
                    
            backend_id = await self.db.create_backend(data, user['id'])
            
            # Reload proxy manager configuration
            await self.proxy_manager.reload_from_database()
            
            return web.json_response({
                'message': 'Backend created successfully',
                'backend_id': backend_id
            }, status=201)
            
        except Exception as e:
            logger.error("Create backend error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    async def api_update_backend(self, request):
        """Update backend"""
        try:
            backend_id = int(request.match_info['backend_id'])
            data = await request.json()
            
            user = request.get('user')
            if not user:
                return web.json_response({'error': 'Authentication required'}, status=401)
            
            await self.db.update_backend(backend_id, data, user['id'])
            
            # Reload proxy manager configuration
            await self.proxy_manager.reload_from_database()
            
            return web.json_response({'message': 'Backend updated successfully'})
            
        except Exception as e:
            logger.error("Update backend error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    async def api_delete_backend(self, request):
        """Delete backend"""
        try:
            backend_id = int(request.match_info['backend_id'])
            
            user = request.get('user')
            if not user:
                return web.json_response({'error': 'Authentication required'}, status=401)
            
            await self.db.delete_backend(backend_id, user['id'])
            
            # Reload proxy manager configuration
            await self.proxy_manager.reload_from_database()
            
            return web.json_response({'message': 'Backend deleted successfully'})
            
        except Exception as e:
            logger.error("Delete backend error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    # ========== DOMAIN ROUTE ENDPOINTS ==========
    
    async def api_list_domain_routes(self, request):
        """List all domain routes"""
        try:
            routes = await self.db.list_domain_routes()
            routes = serialize_datetime(routes)
            return web.json_response({'routes': routes})
            
        except Exception as e:
            logger.error("List routes error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    async def api_get_proxy_routes(self, request):
        """Get routes for specific proxy"""
        try:
            proxy_id = int(request.match_info['proxy_id'])
            routes = await self.db.list_domain_routes(proxy_id)
            routes = serialize_datetime(routes)
            return web.json_response({'routes': routes})
            
        except Exception as e:
            logger.error("Get proxy routes error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    async def api_create_domain_route(self, request):
        """Create domain route"""
        try:
            data = await request.json()
            
            user = request.get('user')
            if not user:
                return web.json_response({'error': 'Authentication required'}, status=401)
            
            # Validate required fields
            required = ['proxy_id', 'domain', 'backend_id']
            for field in required:
                if field not in data:
                    return web.json_response(
                        {'error': f'Missing required field: {field}'},
                        status=400
                    )
                    
            route_id = await self.db.create_domain_route(data, user['id'])
            
            # Reload proxy manager configuration
            await self.proxy_manager.reload_from_database()
            
            return web.json_response({
                'message': 'Domain route created successfully',
                'route_id': route_id
            }, status=201)
            
        except Exception as e:
            logger.error("Create route error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    async def api_delete_domain_route(self, request):
        """Delete domain route"""
        try:
            route_id = int(request.match_info['route_id'])
            
            user = request.get('user')
            if not user:
                return web.json_response({'error': 'Authentication required'}, status=401)
            
            await self.db.delete_domain_route(route_id, user['id'])
            
            # Reload proxy manager configuration
            await self.proxy_manager.reload_from_database()
            
            return web.json_response({'message': 'Domain route deleted successfully'})
            
        except Exception as e:
            logger.error("Delete route error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    # ========== IP FILTER ENDPOINTS ==========
    
    async def api_list_ip_filters(self, request):
        """List IP filters"""
        try:
            filter_type = request.query.get('type')
            proxy_id = request.query.get('proxy_id')
            if proxy_id:
                proxy_id = int(proxy_id)
                
            filters = await self.db.list_ip_filters(filter_type, proxy_id)
            return web.json_response({'filters': filters})
            
        except Exception as e:
            logger.error("List filters error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    async def api_add_ip_filter(self, request):
        """Add IP filter"""
        try:
            data = await request.json()
            
            user = request.get('user')
            if not user:
                return web.json_response({'error': 'Authentication required'}, status=401)
            
            # Validate required fields
            if 'ip_address' not in data or 'filter_type' not in data:
                return web.json_response(
                    {'error': 'ip_address and filter_type required'},
                    status=400
                )
                
            filter_id = await self.db.add_ip_filter(
                data['ip_address'],
                data['filter_type'],
                data.get('proxy_id'),
                data.get('reason'),
                user['id']
            )
            
            # Reload proxy manager configuration
            await self.proxy_manager.reload_from_database()
            
            return web.json_response({
                'message': 'IP filter added successfully',
                'filter_id': filter_id
            }, status=201)
            
        except Exception as e:
            logger.error("Add filter error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    async def api_remove_ip_filter(self, request):
        """Remove IP filter"""
        try:
            filter_id = int(request.match_info['filter_id'])
            
            user = request.get('user')
            if not user:
                return web.json_response({'error': 'Authentication required'}, status=401)
            
            await self.db.remove_ip_filter(filter_id, user['id'])
            
            # Reload proxy manager configuration
            await self.proxy_manager.reload_from_database()
            
            return web.json_response({'message': 'IP filter removed successfully'})
            
        except Exception as e:
            logger.error("Remove filter error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    # ========== STATISTICS ENDPOINTS ==========
    
    async def api_stats(self, request):
        """Get real-time statistics"""
        try:
            stats = {
                'proxies': [],
                'global': {
                    'total_connections': 0,
                    'active_connections': 0,
                    'total_bytes_sent': 0,
                    'total_bytes_received': 0,
                    'uptime': 0
                },
                'timestamp': datetime.now().isoformat()
            }
            
            # Get stats from proxy manager
            for proxy_name, proxy_stats in self.proxy_manager.get_all_stats().items():
                stats['proxies'].append({
                    'name': proxy_name,
                    **proxy_stats
                })
                
                # Aggregate global stats
                stats['global']['total_connections'] += proxy_stats.get('connections', 0)
                stats['global']['active_connections'] += proxy_stats.get('active', 0)
                stats['global']['total_bytes_sent'] += proxy_stats.get('bytes_sent', 0)
                stats['global']['total_bytes_received'] += proxy_stats.get('bytes_received', 0)
                
            return web.json_response(stats)
            
        except Exception as e:
            logger.error("Stats error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    async def api_export_json(self, request):
        """Export stats as JSON"""
        try:
            stats = await self.api_stats(request)
            return web.Response(
                text=stats.text,
                content_type='application/json',
                headers={
                    'Content-Disposition': f'attachment; filename="proxyox-stats-{datetime.now().strftime("%Y%m%d-%H%M%S")}.json"'
                }
            )
            
        except Exception as e:
            logger.error("Export JSON error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    async def api_export_csv(self, request):
        """Export stats as CSV"""
        try:
            # Get stats
            all_stats = self.proxy_manager.get_all_stats()
            
            # Build CSV
            import csv
            from io import StringIO
            
            output = StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow([
                'Proxy Name', 'Connections Total', 'Connections Active',
                'Bytes Sent', 'Bytes Received', 'Errors', 'Status'
            ])
            
            # Data
            for proxy_name, stats in all_stats.items():
                writer.writerow([
                    proxy_name,
                    stats.get('connections', 0),
                    stats.get('active', 0),
                    stats.get('bytes_sent', 0),
                    stats.get('bytes_received', 0),
                    stats.get('errors', 0),
                    stats.get('status', 'unknown')
                ])
                
            csv_content = output.getvalue()
            
            return web.Response(
                text=csv_content,
                content_type='text/csv',
                headers={
                    'Content-Disposition': f'attachment; filename="proxyox-stats-{datetime.now().strftime("%Y%m%d-%H%M%S")}.csv"'
                }
            )
            
        except Exception as e:
            logger.error("Export CSV error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    # ========== SETTINGS ENDPOINTS ==========
    
    async def api_list_settings(self, request):
        """List all settings"""
        try:
            settings = await self.db.list_settings(include_secrets=False)
            return web.json_response({'settings': settings})
            
        except Exception as e:
            logger.error("List settings error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    async def api_update_setting(self, request):
        """Update setting"""
        try:
            key = request.match_info['key']
            data = await request.json()
            
            user = request.get('user')
            if not user:
                return web.json_response({'error': 'Authentication required'}, status=401)
            
            if 'value' not in data:
                return web.json_response({'error': 'Value required'}, status=400)
                
            await self.db.set_setting(key, data['value'], user['id'])
            
            return web.json_response({'message': f"Setting '{key}' updated successfully"})
            
        except Exception as e:
            logger.error("Update setting error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    # ========== AUDIT LOG ENDPOINTS ==========
    
    async def api_list_audit_logs(self, request):
        """List audit logs"""
        try:
            limit = int(request.query.get('limit', 100))
            user_id = request.query.get('user_id')
            if user_id:
                user_id = int(user_id)
                
            logs = await self.db.list_audit_logs(limit, user_id)
            return web.json_response({'logs': logs})
            
        except Exception as e:
            logger.error("List audit logs error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    # ========== SYSTEM ENDPOINTS ==========
    
    async def api_system_info(self, request):
        """Get system information"""
        import platform
        import psutil
        
        try:
            info = {
                'platform': platform.system(),
                'platform_version': platform.version(),
                'python_version': platform.python_version(),
                'cpu_count': psutil.cpu_count(),
                'cpu_percent': psutil.cpu_percent(interval=0.1),
                'memory': {
                    'total': psutil.virtual_memory().total,
                    'available': psutil.virtual_memory().available,
                    'percent': psutil.virtual_memory().percent
                },
                'disk': {
                    'total': psutil.disk_usage('/').total,
                    'used': psutil.disk_usage('/').used,
                    'free': psutil.disk_usage('/').free,
                    'percent': psutil.disk_usage('/').percent
                }
            }
            
            return web.json_response({'system': info})
            
        except Exception as e:
            logger.error("System info error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    async def api_reload_config(self, request):
        """Reload configuration from database"""
        try:
            await self.proxy_manager.reload_from_database()
            return web.json_response({'message': 'Configuration reloaded successfully'})
            
        except Exception as e:
            logger.error("Reload config error", error=str(e))
            return web.json_response({'error': str(e)}, status=500)
            
    # ========== DASHBOARD AND WEBSOCKET ==========
    
    async def handle_dashboard(self, request):
        """Serve the dashboard HTML"""
        dashboard_path = Path(__file__).parent / "static" / "index.html"
        
        if not dashboard_path.exists():
            return web.Response(text="Dashboard not found", status=404)
            
        with open(dashboard_path, "r", encoding="utf-8") as f:
            html = f.read()
            
        return web.Response(text=html, content_type="text/html")
        
    async def websocket_handler(self, request):
        """Handle WebSocket connections for real-time updates"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        logger.info("WebSocket client connected")
        
        try:
            # Send stats every second
            while not ws.closed:
                stats = {
                    'type': 'stats',
                    'data': self.proxy_manager.get_all_stats(),
                    'timestamp': datetime.now().isoformat()
                }
                
                await ws.send_json(stats)
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error("WebSocket error", error=str(e))
        finally:
            logger.info("WebSocket client disconnected")
            
        return ws
    
    # ========== TRAFFIC HISTORY ==========
    
    async def api_save_traffic_history(self, request):
        """Save traffic history data to database"""
        try:
            data = await request.json()
            
            # Expected format: { "date": "2025-11-26", "history": { "proxy1": [0,1,2,...288], "proxy2": [...] } }
            date = data.get('date')
            history = data.get('history', {})
            
            if not date:
                return web.json_response({'error': 'Missing date parameter'}, status=400)
            
            # Save each proxy's history
            saved_count = 0
            for proxy_name, intervals in history.items():
                if not isinstance(intervals, list) or len(intervals) != 288:
                    logger.warning(f"Invalid history data for proxy {proxy_name}")
                    continue
                
                # Save each interval with non-zero values
                for interval_index, request_count in enumerate(intervals):
                    if request_count > 0:
                        await self.db.save_traffic_history(proxy_name, date, interval_index, request_count)
                        saved_count += 1
            
            logger.info(f"Saved {saved_count} traffic history records for date {date}")
            return web.json_response({
                'message': 'Traffic history saved successfully',
                'records_saved': saved_count
            })
            
        except Exception as e:
            logger.error("Save traffic history error", error=str(e), exc_info=True)
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_get_traffic_history(self, request):
        """Get traffic history for a specific date"""
        try:
            date = request.match_info.get('date')
            
            if not date:
                return web.json_response({'error': 'Missing date parameter'}, status=400)
            
            # Get all proxies traffic history for the date
            history = await self.db.get_all_proxies_traffic_history(date)
            
            return web.json_response({
                'date': date,
                'history': history
            })
            
        except Exception as e:
            logger.error("Get traffic history error", error=str(e), exc_info=True)
            return web.json_response({'error': str(e)}, status=500)

            
        return ws

