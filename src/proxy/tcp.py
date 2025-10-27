import asyncio
import logging
import time
from collections import deque

logger = logging.getLogger("tcp_proxy")

class TCPProxy:
    def __init__(self, listen_host, listen_port, target_host, target_port):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.target_host = target_host
        self.target_port = target_port
        self.server = None
        self.bytes_in = 0
        self.bytes_out = 0
        self.active_connections = 0
        self.total_connections = 0
        self.failed_connections = 0
        self.start_time = None
        self.status = "stopped"
        self.last_error = None
        self.last_error_time = None
        self.connection_history = deque(maxlen=100)  # Garde les 100 dernières connexions
        self.bytes_history = deque(maxlen=60)  # 60 secondes d'historique
        self.peak_connections = 0
        self.total_bytes_transferred = 0

    async def relay(self, reader, writer):
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
                
                peer = writer.get_extra_info("peername")
                if peer and peer[0] == self.listen_host:
                    self.bytes_in += len(data)
                else:
                    self.bytes_out += len(data)
        except Exception:
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def handle_client(self, client_reader, client_writer):
        self.active_connections += 1
        self.total_connections += 1
        if self.active_connections > self.peak_connections:
            self.peak_connections = self.active_connections
        
        conn_start = time.time()
        client_addr = client_writer.get_extra_info('peername')
        
        try:
            upstream_reader, upstream_writer = await asyncio.open_connection(self.target_host, self.target_port)
        except Exception as e:
            logger.error(f"Cannot connect upstream: {e}")
            self.failed_connections += 1
            self.last_error = str(e)
            self.last_error_time = time.time()
            client_writer.close()
            await client_writer.wait_closed()
            self.active_connections -= 1
            
            # Enregistrer la connexion échouée
            self.connection_history.append({
                'time': conn_start,
                'client': str(client_addr),
                'duration': time.time() - conn_start,
                'bytes_in': 0,
                'bytes_out': 0,
                'status': 'failed'
            })
            return

        conn_bytes_in = 0
        conn_bytes_out = 0
        
        t1 = asyncio.create_task(self.relay(client_reader, upstream_writer))
        t2 = asyncio.create_task(self.relay(upstream_reader, client_writer))

        await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)
        t1.cancel()
        t2.cancel()

        try:
            upstream_writer.close()
            await upstream_writer.wait_closed()
            client_writer.close()
            await client_writer.wait_closed()
        except Exception:
            pass
        finally:
            self.active_connections -= 1
            duration = time.time() - conn_start
            
            # Enregistrer la connexion réussie
            self.connection_history.append({
                'time': conn_start,
                'client': str(client_addr),
                'duration': duration,
                'bytes_in': conn_bytes_in,
                'bytes_out': conn_bytes_out,
                'status': 'success'
            })

    async def start(self):
        self.server = await asyncio.start_server(self.handle_client, self.listen_host, self.listen_port)
        self.start_time = time.time()
        self.status = "running"
        asyncio.create_task(self._update_bytes_history())
        logger.info(f"TCP proxy started: {self.listen_host}:{self.listen_port} -> {self.target_host}:{self.target_port}")
    
    async def _update_bytes_history(self):
        """Met à jour l'historique des bytes toutes les secondes"""
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
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.status = "stopped"
            logger.info(f"TCP proxy stopped: {self.listen_host}:{self.listen_port}")
