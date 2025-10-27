"""
Prometheus metrics for the proxy package.
"""
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry


METRICS_REGISTRY = CollectorRegistry()


TCP_CONNECTIONS = Counter(
'proxy_tcp_connections_total', 'Total proxied TCP connections', registry=METRICS_REGISTRY
)
TCP_ACTIVE = Gauge('proxy_tcp_active_connections', 'Active TCP connections', registry=METRICS_REGISTRY)
TCP_BYTES_SENT = Counter('proxy_tcp_bytes_sent_total', 'Total TCP bytes sent', registry=METRICS_REGISTRY)
TCP_BYTES_RECV = Counter('proxy_tcp_bytes_recv_total', 'Total TCP bytes received', registry=METRICS_REGISTRY)


UDP_PACKETS = Counter('proxy_udp_packets_total', 'Total proxied UDP packets', registry=METRICS_REGISTRY)
UDP_ASSOCIATIONS = Gauge('proxy_udp_associations', 'Active UDP associations', registry=METRICS_REGISTRY)


HTTP_REQUESTS = Counter('proxy_http_requests_total', 'Total proxied HTTP requests', registry=METRICS_REGISTRY)
HTTP_ACTIVE = Gauge('proxy_http_active_requests', 'Active proxied HTTP requests', registry=METRICS_REGISTRY)
HTTP_LATENCY = Histogram('proxy_http_request_latency_seconds', 'HTTP proxy latency', registry=METRICS_REGISTRY)