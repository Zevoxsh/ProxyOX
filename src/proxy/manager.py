import structlog
import time
from .tcp import TCPProxy
from .udp import UDPProxy
from .http import HttpProxy
from .flexible import FlexibleProxy
from .smart import SmartProxy

logger = structlog.get_logger()

class ProxyManager:
    def __init__(self):
        self.tcp_proxies = {}
        self.udp_proxies = {}
        self.http_proxies = {}
        self.flexible_proxies = {}
        self.smart_proxies = {}

    async def create_proxy(self, proto, listen_host, listen_port, target_host, target_port, use_tls=False, certfile=None, keyfile=None, flexible=False, auto_detect=False):
        proxy_id = f"{proto}_{listen_host}_{listen_port}"
        if proto == "tcp":
            if auto_detect:
                # Mode AUTO: détection automatique HTTP/HTTPS
                await self.register_smart(proxy_id, listen_host, listen_port, target_host, target_port, certfile, keyfile)
            elif flexible:
                # Mode flexible: HTTPS avec SSL
                await self.register_flexible(proxy_id, listen_host, listen_port, target_host, target_port, certfile, keyfile)
            else:
                # Mode normal: TCP avec ou sans TLS
                await self.register_tcp(proxy_id, listen_host, listen_port, target_host, target_port, use_tls, certfile, keyfile)
        elif proto == "udp":
            await self.register_udp(proxy_id, listen_host, listen_port, target_host, target_port)
        elif proto == "http":
            await self.register_http(proxy_id, listen_host, listen_port, target_host, target_port)
        else:
            logger.error("Unknown proxy type", proto=proto)

    async def register_tcp(self, proxy_id, listen_host, listen_port, target_host, target_port, use_tls=False, certfile=None, keyfile=None):
        if proxy_id in self.tcp_proxies:
            return
        try:
            proxy = TCPProxy(listen_host, listen_port, target_host, target_port, use_tls, certfile, keyfile)
            await proxy.start()
            self.tcp_proxies[proxy_id] = proxy
        except Exception as e:
            logger.error(f"Failed to register TCP proxy {proxy_id}", error=str(e))
            raise

    async def register_udp(self, proxy_id, listen_host, listen_port, target_host, target_port):
        if proxy_id in self.udp_proxies:
            return
        proxy = UDPProxy(listen_host, listen_port, target_host, target_port)
        await proxy.start()
        self.udp_proxies[proxy_id] = proxy

    async def register_http(self, proxy_id, listen_host, listen_port, target_host, target_port):
        if proxy_id in self.http_proxies:
            return
        proxy = HttpProxy(listen_host, listen_port, target_host, target_port)
        await proxy.start()
        self.http_proxies[proxy_id] = proxy

    async def register_flexible(self, proxy_id, listen_host, listen_port, target_host, target_port, certfile=None, keyfile=None):
        if proxy_id in self.flexible_proxies:
            return
        try:
            proxy = FlexibleProxy(listen_host, listen_port, target_host, target_port, certfile, keyfile)
            await proxy.start()
            self.flexible_proxies[proxy_id] = proxy
        except Exception as e:
            logger.error(f"Failed to register Flexible proxy {proxy_id}", error=str(e))
            raise

    async def register_smart(self, proxy_id, listen_host, listen_port, target_host, target_port, certfile=None, keyfile=None):
        if proxy_id in self.smart_proxies:
            return
        try:
            proxy = SmartProxy(listen_host, listen_port, target_host, target_port, certfile, keyfile)
            await proxy.start()
            self.smart_proxies[proxy_id] = proxy
        except Exception as e:
            logger.error(f"Failed to register Smart proxy {proxy_id}", error=str(e))
            raise

    def get_stats(self):
        stats = []
        for p in self.tcp_proxies.values():
            uptime = int(time.time() - p.start_time) if p.start_time else 0
            stats.append({
                "protocol": "TCP",
                "listen": f"{p.listen_host}:{p.listen_port}",
                "target": f"{p.target_host}:{p.target_port}",
                "bytes_in": p.bytes_in,
                "bytes_out": p.bytes_out,
                "active_connections": p.active_connections,
                "total_connections": p.total_connections,
                "failed_connections": p.failed_connections,
                "peak_connections": p.peak_connections,
                "status": p.status,
                "uptime": uptime,
                "last_error": p.last_error,
                "last_error_time": p.last_error_time,
                "bytes_history": list(p.bytes_history),
                "connection_history": list(p.connection_history)[-10:],  # 10 dernières
                "total_bytes_transferred": p.total_bytes_transferred,
            })
        for p in self.udp_proxies.values():
            uptime = int(time.time() - p.start_time) if p.start_time else 0
            stats.append({
                "protocol": "UDP",
                "listen": f"{p.listen_host}:{p.listen_port}",
                "target": f"{p.target_host}:{p.target_port}",
                "bytes_in": p.bytes_in,
                "bytes_out": p.bytes_out,
                "packets_in": p.packets_in,
                "packets_out": p.packets_out,
                "peak_packets_per_sec": p.peak_packets_per_sec,
                "status": p.status,
                "uptime": uptime,
                "last_error": p.last_error,
                "last_error_time": p.last_error_time,
                "bytes_history": list(p.bytes_history),
                "packet_history": list(p.packet_history),
                "total_bytes_transferred": p.total_bytes_transferred,
            })
        for p in self.http_proxies.values():
            uptime = int(time.time() - p.start_time) if p.start_time else 0
            stats.append({
                "protocol": "HTTP",
                "listen": f"{p.listen_host}:{p.listen_port}",
                "target": f"{p.target_host}:{p.target_port}",
                "bytes_in": p.bytes_in,
                "bytes_out": p.bytes_out,
                "total_requests": p.total_requests,
                "active_requests": p.active_requests,
                "failed_requests": p.failed_requests,
                "peak_requests": p.peak_requests,
                "avg_response_time": p.avg_response_time,
                "method_stats": p.method_stats,
                "status": p.status,
                "uptime": uptime,
                "last_error": p.last_error,
                "last_error_time": p.last_error_time,
                "bytes_history": list(p.bytes_history),
                "request_history": list(p.request_history)[-10:],  # 10 dernières
                "total_bytes_transferred": p.total_bytes_transferred,
            })
        for p in self.flexible_proxies.values():
            uptime = int(time.time() - p.start_time) if p.start_time else 0
            stats.append({
                "protocol": "FLEXIBLE (HTTP/HTTPS Auto-detect)",
                "listen": f"{p.listen_host}:{p.listen_port}",
                "target": f"{p.target_host}:{p.target_port}",
                "bytes_in": p.bytes_in,
                "bytes_out": p.bytes_out,
                "active_connections": p.active_connections,
                "total_connections": p.total_connections,
                "https_connections": p.https_connections,
                "http_connections": p.http_connections,
                "failed_connections": p.failed_connections,
                "peak_connections": p.peak_connections,
                "status": p.status,
                "uptime": uptime,
                "last_error": p.last_error,
                "last_error_time": p.last_error_time,
                "bytes_history": list(p.bytes_history),
                "connection_history": list(p.connection_history)[-10:],  # 10 dernières
                "total_bytes_transferred": p.total_bytes_transferred,
            })
        for p in self.smart_proxies.values():
            uptime = int(time.time() - p.start_time) if p.start_time else 0
            stats.append({
                "protocol": "SMART (HTTP/HTTPS Auto-detect)",
                "listen": f"{p.listen_host}:{p.listen_port}",
                "target": f"{p.target_host}:{p.target_port}",
                "bytes_in": p.bytes_in,
                "bytes_out": p.bytes_out,
                "active_connections": p.active_connections,
                "total_connections": p.total_connections,
                "https_connections": p.https_connections,
                "http_connections": p.http_connections,
                "failed_connections": p.failed_connections,
                "peak_connections": p.peak_connections,
                "status": p.status,
                "uptime": uptime,
                "last_error": p.last_error,
                "last_error_time": p.last_error_time,
                "bytes_history": list(p.bytes_history),
                "connection_history": list(p.connection_history)[-10:],
                "total_bytes_transferred": p.total_bytes_transferred,
            })
        return stats

    async def stop_all(self):
        for proxy in self.tcp_proxies.values():
            await proxy.stop()
        for proxy in self.udp_proxies.values():
            await proxy.stop()
        for proxy in self.http_proxies.values():
            await proxy.stop()
        for proxy in self.flexible_proxies.values():
            await proxy.stop()
        for proxy in self.smart_proxies.values():
            await proxy.stop()
        logger.info("All proxies stopped")
