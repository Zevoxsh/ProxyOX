from aiohttp import web, ClientSession, TCPConnector
import asyncio
import logging
import time
import ssl
from collections import deque
from .ip_filter import IPFilter
from pathlib import Path

logger = logging.getLogger("http_proxy")

class HttpProxy:
    def __init__(self, listen_host, listen_port, target_host=None, target_port=None, backend_https=False, domain_routes=None, max_connections=100, rate_limit=1000, ip_filter=None):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.target_host = target_host
        self.target_port = target_port
        self.backend_https = backend_https  # Support HTTPS vers backend
        self.domain_routes = domain_routes or {}  # Routes basées sur les domaines
        self.max_connections = max_connections
        self.rate_limit = rate_limit  # Requêtes par seconde
        self.ip_filter = ip_filter  # Filtre IP
        self.runner = None
        self.bytes_in = 0
        self.bytes_out = 0
        self.total_requests = 0
        self.active_requests = 0
        self.failed_requests = 0
        self.blocked_ips = 0  # Nombre d'IPs bloquées
        self.start_time = None
        self.status = "stopped"
        self.last_error = None
        self.last_error_time = None
        self.request_history = deque(maxlen=100)
        self.bytes_history = deque(maxlen=60)
        self.peak_requests = 0
        self.total_bytes_transferred = 0
        self.avg_response_time = 0
        self.method_stats = {}
        self.domain_stats = {}  # Stats par domaine
        self.rate_limiter = deque(maxlen=rate_limit)  # Timestamps des dernières requêtes

    async def handle_request(self, request):
        # IP Filtering
        client_ip = request.remote
        if self.ip_filter and not self.ip_filter.is_allowed(client_ip):
            self.blocked_ips += 1
            self.failed_requests += 1
            logger.warning(f"Blocked request from {client_ip}")
            return web.Response(text="Access Denied", status=403)
        
        # Rate limiting
        now = time.time()
        self.rate_limiter.append(now)
        
        # Compter les requêtes de la dernière seconde
        recent_requests = [t for t in self.rate_limiter if now - t <= 1.0]
        if len(recent_requests) > self.rate_limit:
            self.failed_requests += 1
            logger.warning(f"Rate limit exceeded: {len(recent_requests)}/{self.rate_limit}")
            return web.Response(text="Rate limit exceeded", status=429)
        
        # Max connections check
        if self.active_requests >= self.max_connections:
            self.failed_requests += 1
            logger.warning(f"Max connections reached: {self.active_requests}/{self.max_connections}")
            return web.Response(text="Too many concurrent requests", status=503)
        
        self.active_requests += 1
        self.total_requests += 1
        if self.active_requests > self.peak_requests:
            self.peak_requests = self.active_requests
        
        req_start = time.time()
        method = request.method
        
        # Statistiques par méthode HTTP
        if method not in self.method_stats:
            self.method_stats[method] = 0
        self.method_stats[method] += 1
        
        try:
            data = await request.read()
            self.bytes_in += len(data)
            
            # Déterminer le backend en fonction du nom de domaine (Host header)
            host_header = request.headers.get('Host', '').split(':')[0]  # Enlever le port si présent
            
            # Log pour debug
            logger.info(f"[HTTP] Request from {host_header} - Available routes: {list(self.domain_routes.keys()) if self.domain_routes else 'None'}")
            
            # Chercher une route correspondante au domaine
            backend_config = None
            if host_header and self.domain_routes:
                backend_config = self.domain_routes.get(host_header)
            
            # Tracker les stats par domaine
            domain_key = host_header if host_header else "unknown"
            if domain_key not in self.domain_stats:
                self.domain_stats[domain_key] = {
                    'requests': 0,
                    'bytes_sent': 0,
                    'bytes_received': 0
                }
            self.domain_stats[domain_key]['requests'] += 1
            
            # Si aucune route trouvée, utiliser le backend par défaut
            if backend_config:
                target_host = backend_config['host']
                target_port = backend_config['port']
                backend_https = backend_config.get('https', False)
                logger.info(f"Routing {host_header} to {target_host}:{target_port} (HTTPS: {backend_https})")
            elif self.target_host:
                target_host = self.target_host
                target_port = self.target_port
                backend_https = self.backend_https
            else:
                return web.Response(text="No backend configured for this domain", status=502)
            
            # Construire l'URL du backend (HTTP ou HTTPS)
            protocol = "https" if backend_https else "http"
            backend_url = f"{protocol}://{target_host}:{target_port}{request.rel_url}"
            
            # Créer une session avec SSL désactivé pour les certificats auto-signés
            connector = None
            if backend_https:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                connector = TCPConnector(ssl=ssl_context, force_close=True)
            
            # Préparer les headers (filtrer les headers problématiques)
            headers = {}
            # Headers à ne pas transférer (gérés automatiquement par aiohttp)
            skip_headers = {
                'host', 'connection', 'keep-alive', 'proxy-connection',
                'transfer-encoding', 'upgrade', 'content-length',
                'te', 'trailer', 'proxy-authorization', 'proxy-authenticate',
                'accept-encoding'  # Désactiver la compression pour éviter les erreurs de décodage
            }
            
            for key, value in request.headers.items():
                if key.lower() not in skip_headers:
                    headers[key] = value
            
            # Définir le Host pour le backend
            headers['Host'] = target_host
            # Forcer HTTP/1.1 et connection close pour éviter les problèmes
            headers['Connection'] = 'close'
            # Désactiver la compression
            headers['Accept-Encoding'] = 'identity'
            
            async with ClientSession(connector=connector) as session:
                async with session.request(request.method, backend_url, data=data, headers=headers, allow_redirects=False) as resp:
                    resp_data = await resp.read()
                    self.bytes_out += len(resp_data)
                    
                    duration = time.time() - req_start
                    
                    # Tracker les bytes par domaine
                    self.domain_stats[domain_key]['bytes_sent'] += len(resp_data)
                    self.domain_stats[domain_key]['bytes_received'] += len(data)
                    
                    # Enregistrer la requête
                    self.request_history.append({
                        'time': req_start,
                        'method': method,
                        'path': str(request.rel_url),
                        'status': resp.status,
                        'duration': duration,
                        'bytes_in': len(data),
                        'bytes_out': len(resp_data)
                    })
                    
                    # Mise à jour du temps de réponse moyen
                    total_time = sum(r['duration'] for r in self.request_history)
                    self.avg_response_time = total_time / len(self.request_history)
                    
                    # Filtrer les headers de réponse problématiques
                    response_headers = {}
                    skip_response_headers = {
                        'connection', 'keep-alive', 'transfer-encoding',
                        'content-encoding', 'content-length'
                    }
                    for key, value in resp.headers.items():
                        if key.lower() not in skip_response_headers:
                            response_headers[key] = value
                    
                    return web.Response(body=resp_data, status=resp.status, headers=response_headers)
        except Exception as e:
            self.failed_requests += 1
            self.last_error = str(e)
            self.last_error_time = time.time()
            logger.error(f"HTTP proxy error: {e}")
            return web.Response(text=f"Proxy Error: {str(e)}", status=502)
        finally:
            self.active_requests -= 1

    async def start(self):
        app = web.Application()
        app.router.add_route('*', '/{tail:.*}', self.handle_request)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.listen_host, self.listen_port)
        await site.start()
        self.start_time = time.time()
        self.status = "running"
        asyncio.create_task(self._update_history())
        
        # Log des routes configurées
        if self.domain_routes:
            logger.info(f"✅ HTTP proxy STARTED with {len(self.domain_routes)} domain routes on {self.listen_host}:{self.listen_port}")
            for domain, config in self.domain_routes.items():
                logger.info(f"  - {domain} -> {config['host']}:{config['port']} (HTTPS: {config.get('https', False)})")
        else:
            logger.info(f"✅ HTTP proxy STARTED: {self.listen_host}:{self.listen_port} -> {self.target_host}:{self.target_port}")
    
    async def _update_history(self):
        """Met à jour l'historique toutes les secondes"""
        last_bytes_in = 0
        last_bytes_out = 0
        while self.status == "running":
            await asyncio.sleep(1)
            bytes_in_delta = self.bytes_in - last_bytes_in
            bytes_out_delta = self.bytes_out - last_bytes_out
            
            self.bytes_history.append({
                'time': time.time(),
                'bytes_in': bytes_in_delta,
                'bytes_out': bytes_out_delta
            })
            
            last_bytes_in = self.bytes_in
            last_bytes_out = self.bytes_out
            self.total_bytes_transferred = self.bytes_in + self.bytes_out

    async def stop(self):
        if self.runner:
            await self.runner.cleanup()
            self.status = "stopped"
            logger.info(f"HTTP proxy stopped: {self.listen_host}:{self.listen_port}")
