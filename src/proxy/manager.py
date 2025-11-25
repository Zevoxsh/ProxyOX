import structlog
import time
from pathlib import Path
from .tcp import TCPProxy
from .udp import UDPProxy
from .http import HttpProxy
from .ip_filter import IPFilter

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

    async def create_proxy(self, proto, listen_host, listen_port, target_host, target_port, 
                          use_tls=False, certfile=None, keyfile=None, backend_ssl=False, 
                          backend_https=False, proxy_name=None, domain_routes=None, max_connections=100, rate_limit=1000):
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
            await self.register_http(proxy_id, listen_host, listen_port, target_host, target_port, backend_https, domain_routes, max_connections, rate_limit)
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

    async def register_http(self, proxy_id, listen_host, listen_port, target_host, target_port, backend_https=False, domain_routes=None, max_connections=100, rate_limit=1000):
        """Register an HTTP proxy"""
        logger.info(f"🔥 REGISTER_HTTP CALLED: {proxy_id} on {listen_host}:{listen_port} -> {target_host}:{target_port}")
        logger.info(f"🔥 Domain routes: {domain_routes}")
        if proxy_id in self.http_proxies:
            logger.warning(f"HTTP proxy {proxy_id} already registered")
            return
        proxy = HttpProxy(listen_host, listen_port, target_host, target_port, backend_https, domain_routes, max_connections, rate_limit, self.ip_filter)
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
