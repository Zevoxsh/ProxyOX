from aiohttp import web, ClientSession
import asyncio
import logging
import time
from collections import deque

logger = logging.getLogger("http_proxy")

class HttpProxy:
    def __init__(self, listen_host, listen_port, target_host, target_port):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.target_host = target_host
        self.target_port = target_port
        self.runner = None
        self.bytes_in = 0
        self.bytes_out = 0
        self.total_requests = 0
        self.active_requests = 0
        self.failed_requests = 0
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

    async def handle_request(self, request):
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
            async with ClientSession() as session:
                async with session.request(request.method, f"http://{self.target_host}:{self.target_port}{request.rel_url}", data=data, headers=request.headers) as resp:
                    resp_data = await resp.read()
                    self.bytes_out += len(resp_data)
                    
                    duration = time.time() - req_start
                    
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
                    
                    return web.Response(body=resp_data, status=resp.status, headers=resp.headers)
        except Exception as e:
            self.failed_requests += 1
            self.last_error = str(e)
            self.last_error_time = time.time()
            raise
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
        logger.info(f"HTTP proxy started: {self.listen_host}:{self.listen_port} -> {self.target_host}:{self.target_port}")
    
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
