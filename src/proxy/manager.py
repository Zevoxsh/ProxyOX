import structlog
import time
from pathlib import Path
from .tcp import TCPProxy
from .udp import UDPProxy
from .http import HttpProxy
from .ip_filter import IPFilter
from .cert_manager import CertificateManager

logger = structlog.get_logger()

class ProxyManager:
    def __init__(self, data_dir=None):
        self.tcp_proxies = {}
        self.udp_proxies = {}
        self.http_proxies = {}
        
        # Initialiser le filtre IP global
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent / "data"
        self.ip_filter = IPFilter(Path(data_dir))
        
        # Initialiser le gestionnaire de certificats SSL
        cert_dir = Path(data_dir) / "certs"
        self.cert_manager = CertificateManager(cert_dir=str(cert_dir))

    async def create_proxy(self, proto, listen_host, listen_port, target_host, target_port, 
                          use_tls=False, certfile=None, keyfile=None, backend_ssl=False, 
                          backend_https=False, proxy_name=None, domain_routes=None, max_connections=100, rate_limit=1000, use_https=False):
        """Create and register a proxy of the specified type"""
        proxy_id = proxy_name or f"{proto}_{listen_host}_{listen_port}"
        
        logger.info(f"🔥 CREATE_PROXY: proto={proto}, id={proxy_id}, {listen_host}:{listen_port} -> {target_host}:{target_port}")
        logger.info(f"🔥 domain_routes={domain_routes}")
        
        if proto == "tcp":
            await self.register_tcp(proxy_id, listen_host, listen_port, target_host, target_port, 
                                   use_tls, certfile, keyfile, backend_ssl, max_connections, rate_limit)
        elif proto == "udp":
            await self.register_udp(proxy_id, listen_host, listen_port, target_host, target_port)
        elif proto == "http":
            await self.register_http(proxy_id, listen_host, listen_port, target_host, target_port, backend_https, domain_routes, max_connections, rate_limit, use_https)
        else:
            logger.error("Unknown proxy type", proto=proto)

    async def register_tcp(self, proxy_id, listen_host, listen_port, target_host, target_port, 
                          use_tls=False, certfile=None, keyfile=None, backend_ssl=False, max_connections=100, rate_limit=1000):
        """Register a TCP proxy"""
        if proxy_id in self.tcp_proxies:
            return
        try:
            proxy = TCPProxy(listen_host, listen_port, target_host, target_port, use_tls, certfile, keyfile, backend_ssl, max_connections, rate_limit, self.ip_filter)
            await proxy.start()
            self.tcp_proxies[proxy_id] = proxy
        except Exception as e:
            logger.error(f"Failed to register TCP proxy {proxy_id}", error=str(e))
            raise

    async def register_udp(self, proxy_id, listen_host, listen_port, target_host, target_port):
        """Register a UDP proxy"""
        if proxy_id in self.udp_proxies:
            return
        proxy = UDPProxy(listen_host, listen_port, target_host, target_port)
        await proxy.start()
        self.udp_proxies[proxy_id] = proxy

    async def register_http(self, proxy_id, listen_host, listen_port, target_host, target_port, backend_https=False, domain_routes=None, max_connections=100, rate_limit=1000, use_https=False):
        """Register an HTTP proxy"""
        logger.info(f"🔥 REGISTER_HTTP CALLED: {proxy_id} on {listen_host}:{listen_port} -> {target_host}:{target_port}")
        logger.info(f"🔥 Client HTTPS: {use_https}, Backend HTTPS: {backend_https}")
        logger.info(f"🔥 Domain routes: {domain_routes}")
        if proxy_id in self.http_proxies:
            logger.warning(f"HTTP proxy {proxy_id} already registered")
            return
        proxy = HttpProxy(listen_host, listen_port, target_host, target_port, backend_https, domain_routes, max_connections, rate_limit, self.ip_filter, use_https, self.cert_manager)
        await proxy.start()
        self.http_proxies[proxy_id] = proxy
        logger.info(f"✅ HTTP proxy {proxy_id} registered. Total HTTP proxies: {len(self.http_proxies)}")

    def _get_uptime(self, proxy):
        """Calculate proxy uptime in seconds"""
        return int(time.time() - proxy.start_time) if proxy.start_time else 0

    def get_stats(self):
        """Get statistics for all proxies in JSON format"""
        proxies = []
        
        # TCP proxies
        for proxy_id, p in self.tcp_proxies.items():
            proxies.append({
                "name": proxy_id,
                "protocol": "TCP",
                "listen": f"{p.listen_host}:{p.listen_port}",
                "target": f"{p.target_host}:{p.target_port}",
                "backend_ssl": getattr(p, 'backend_ssl', False),
                "status": p.status,
                "uptime": self._get_uptime(p),
                "max_connections": getattr(p, 'max_connections', 100),
                "rate_limit": getattr(p, 'rate_limit', 1000),
                "stats": {
                    "bytes_sent": p.bytes_out,
                    "bytes_received": p.bytes_in,
                    "active_connections": p.active_connections,
                    "total_connections": p.total_connections,
                    "failed_connections": getattr(p, 'failed_connections', 0),
                    "blocked_ips": getattr(p, 'blocked_ips', 0),
                }
            })
        
        # UDP proxies
        for proxy_id, p in self.udp_proxies.items():
            proxies.append({
                "name": proxy_id,
                "protocol": "UDP",
                "listen": f"{p.listen_host}:{p.listen_port}",
                "target": f"{p.target_host}:{p.target_port}",
                "backend_ssl": False,
                "status": p.status,
                "uptime": self._get_uptime(p),
                "stats": {
                    "packets_sent": p.packets_out,
                    "packets_received": p.packets_in,
                    "bytes_sent": p.bytes_out,
                    "bytes_received": p.bytes_in,
                }
            })
        
        # HTTP proxies
        for proxy_id, p in self.http_proxies.items():
            # Si c'est un reverse proxy avec domain_routes, afficher différemment
            if hasattr(p, 'domain_routes') and p.domain_routes:
                target_display = f"Reverse Proxy ({len(p.domain_routes)} domains)"
            else:
                target_display = f"{p.target_host}:{p.target_port}"
                
            stats = {
                "requests": p.total_requests,
                "total_requests": p.total_requests,
                "active_requests": p.active_requests,
                "failed_requests": p.failed_requests,
                "blocked_ips": getattr(p, 'blocked_ips', 0),
                "responses": p.total_requests - p.failed_requests,
                "avg_response_time": p.avg_response_time,
                "bytes_sent": p.bytes_out,
                "bytes_received": p.bytes_in,
            }
            
            # Ajouter les stats par domaine si disponibles
            if hasattr(p, 'domain_stats') and p.domain_stats:
                stats["domains"] = p.domain_stats
                
            proxies.append({
                "name": proxy_id,
                "protocol": "HTTP",
                "listen": f"{p.listen_host}:{p.listen_port}",
                "target": target_display,
                "backend_ssl": getattr(p, 'backend_https', False),
                "status": p.status,
                "uptime": self._get_uptime(p),
                "max_connections": getattr(p, 'max_connections', 100),
                "rate_limit": getattr(p, 'rate_limit', 1000),
                "stats": stats
            })
        
        # Ajouter les stats globales du filtre IP
        ip_filter_stats = self.ip_filter.get_stats()
        
        return {
            "proxies": proxies,
            "ip_filter": ip_filter_stats
        }

    async def stop_all(self):
        """Stop all registered proxies"""
        for proxy in self.tcp_proxies.values():
            await proxy.stop()
        for proxy in self.udp_proxies.values():
            await proxy.stop()
        for proxy in self.http_proxies.values():
            await proxy.stop()
        logger.info("All proxies stopped")
        
    async def start_proxy(self, name, mode, bind_address, bind_port, backend_address=None,
                         domain_routes=None, max_connections=100, rate_limit=1000,
                         timeout=300, backend_ssl=False, use_https=False, blacklist=None, whitelist=None):
        """Start a single proxy from configuration"""
        # Update IP filters if provided
        if blacklist:
            for ip in blacklist:
                self.ip_filter.add_to_blacklist(ip, reason=f"Config for {name}")
        if whitelist:
            for ip in whitelist:
                self.ip_filter.add_to_whitelist(ip, reason=f"Config for {name}")
                
        # Parse backend address
        target_host = None
        target_port = None
        if backend_address:
            if ':' in backend_address:
                target_host, target_port = backend_address.rsplit(':', 1)
                target_port = int(target_port)
            else:
                target_host = backend_address
                target_port = 80 if mode == 'http' else 443
                
        # Create proxy based on mode
        await self.create_proxy(
            proto=mode,
            listen_host=bind_address,
            listen_port=bind_port,
            target_host=target_host,
            target_port=target_port,
            backend_ssl=backend_ssl,
            backend_https=backend_ssl,
            proxy_name=name,
            domain_routes=domain_routes,
            max_connections=max_connections,
            rate_limit=rate_limit,
            use_https=use_https
        )
        
        logger.info("Proxy started successfully", name=name, mode=mode)
        return True
        
    async def stop_proxy(self, name):
        """Stop a specific proxy by name"""
        # Try to find and stop the proxy
        if name in self.tcp_proxies:
            await self.tcp_proxies[name].stop()
            del self.tcp_proxies[name]
            logger.info("TCP proxy stopped", name=name)
            return True
        elif name in self.udp_proxies:
            await self.udp_proxies[name].stop()
            del self.udp_proxies[name]
            logger.info("UDP proxy stopped", name=name)
            return True
        elif name in self.http_proxies:
            await self.http_proxies[name].stop()
            del self.http_proxies[name]
            logger.info("HTTP proxy stopped", name=name)
            return True
        else:
            logger.warning("Proxy not found", name=name)
            return False
            
    def get_proxy_status(self, name):
        """Get runtime status of a specific proxy"""
        # Check all proxy types
        if name in self.tcp_proxies:
            p = self.tcp_proxies[name]
            return {
                'type': 'tcp',
                'status': p.status,
                'active': p.active_connections,
                'total': p.total_connections,
                'bytes_sent': p.bytes_out,
                'bytes_received': p.bytes_in
            }
        elif name in self.udp_proxies:
            p = self.udp_proxies[name]
            return {
                'type': 'udp',
                'status': p.status,
                'packets_sent': p.packets_out,
                'packets_received': p.packets_in
            }
        elif name in self.http_proxies:
            p = self.http_proxies[name]
            return {
                'type': 'http',
                'status': p.status,
                'active': p.active_requests,
                'total': p.total_requests,
                'failed': p.failed_requests,
                'bytes_sent': p.bytes_out,
                'bytes_received': p.bytes_in
            }
        return None
        
    def get_all_stats(self):
        """Get stats for all proxies in simplified format"""
        stats = {}
        
        # TCP proxies
        for name, p in self.tcp_proxies.items():
            stats[name] = {
                'mode': 'tcp',
                'status': p.status,
                'connections': p.total_connections,
                'active': p.active_connections,
                'bytes_sent': p.bytes_out,
                'bytes_received': p.bytes_in,
                'errors': getattr(p, 'failed_connections', 0)
            }
            
        # UDP proxies
        for name, p in self.udp_proxies.items():
            stats[name] = {
                'mode': 'udp',
                'status': p.status,
                'packets_sent': p.packets_out,
                'packets_received': p.packets_in,
                'bytes_sent': p.bytes_out,
                'bytes_received': p.bytes_in
            }
            
        # HTTP proxies
        for name, p in self.http_proxies.items():
            stats[name] = {
                'mode': 'http',
                'status': p.status,
                'connections': p.total_requests,
                'active': p.active_requests,
                'failed': p.failed_requests,
                'bytes_sent': p.bytes_out,
                'bytes_received': p.bytes_in,
                'errors': p.failed_requests
            }
            
        return stats
        
    async def reload_single_proxy_from_db(self, proxy_name):
        """Reload a single proxy from database without affecting others"""
        if not hasattr(self, 'db') or not self.db:
            logger.warning("Database not attached to ProxyManager - cannot reload")
            return
            
        try:
            # Get proxy config from database
            proxies = await self.db.get_proxies()
            proxy_config = None
            for p in proxies:
                if p['name'] == proxy_name:
                    proxy_config = p
                    break
            
            if not proxy_config:
                logger.error("Proxy not found in database", name=proxy_name)
                return
            
            # Stop the proxy if it exists
            await self.stop_proxy(proxy_name)
            
            # Get backend and domain routes
            backend = None
            if proxy_config.get('default_backend_id'):
                backend = await self.db.get_backend(proxy_config['default_backend_id'])
            
            domain_routes_config = await self.db.get_domain_routes_for_proxy(proxy_config['id'])
            domain_routes = {}
            for route in domain_routes_config:
                domain = route['domain']
                backend_for_domain = await self.db.get_backend(route['backend_id'])
                if backend_for_domain:
                    domain_routes[domain] = {
                        'host': backend_for_domain['server_address'],
                        'port': backend_for_domain['server_port'],
                        'use_https': backend_for_domain.get('use_ssl', False)
                    }
            
            # Create the proxy with new config
            if backend:
                await self.create_proxy(
                    proto=proxy_config['mode'],
                    listen_host=proxy_config['bind_address'],
                    listen_port=proxy_config['bind_port'],
                    target_host=backend['server_address'],
                    target_port=backend['server_port'],
                    use_tls=proxy_config.get('use_tls', False),
                    backend_ssl=backend.get('use_ssl', False),
                    backend_https=backend.get('use_ssl', False),
                    proxy_name=proxy_config['name'],
                    domain_routes=domain_routes if domain_routes else None,
                    max_connections=proxy_config.get('max_connections', 100),
                    rate_limit=proxy_config.get('rate_limit', 1000),
                    use_https=proxy_config.get('use_https', False)
                )
            else:
                logger.warning("No backend configured for proxy", name=proxy_name)
            
            logger.info("Single proxy reloaded from database", name=proxy_name)
            
        except Exception as e:
            logger.error("Failed to reload single proxy", name=proxy_name, error=str(e), exc_info=True)
    
    async def reload_from_database(self):
        """Reload configuration from database"""
        if hasattr(self, 'db') and self.db:
            # Stop all current proxies
            await self.stop_all()
            
            # Reimport to avoid circular dependency
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from main import load_config_from_db
            
            # Reload configuration
            logger.info("Reloading configuration from database")
            await load_config_from_db(self, self.db)
        else:
            logger.warning("Database not attached to ProxyManager - cannot reload")
