import asyncio
import logging
import time
from collections import deque

logger = logging.getLogger("udp_proxy")

class UDPProxy:
    def __init__(self, listen_host, listen_port, target_host, target_port):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.target_host = target_host
        self.target_port = target_port
        self.transport = None
        self.bytes_in = 0
        self.bytes_out = 0
        self.packets_in = 0
        self.packets_out = 0
        self.start_time = None
        self.status = "stopped"
        self.last_error = None
        self.last_error_time = None
        self.packet_history = deque(maxlen=60)
        self.bytes_history = deque(maxlen=60)
        self.peak_packets_per_sec = 0
        self.total_bytes_transferred = 0

    class Protocol(asyncio.DatagramProtocol):
        def __init__(self, proxy):
            self.proxy = proxy
            self.upstream_transport = None

        def connection_made(self, transport):
            self.transport = transport
            logger.info(f"UDP proxy listening: {self.proxy.listen_host}:{self.proxy.listen_port}")

        def datagram_received(self, data, addr):
            self.proxy.bytes_in += len(data)
            self.proxy.packets_in += 1
            loop = asyncio.get_event_loop()
            loop.create_task(self.forward(data))

        async def forward(self, data):
            loop = asyncio.get_event_loop()
            transport, _ = await loop.create_datagram_endpoint(lambda: asyncio.DatagramProtocol(), remote_addr=(self.proxy.target_host, self.proxy.target_port))
            transport.sendto(data)
            self.proxy.bytes_out += len(data)
            self.proxy.packets_out += 1
            transport.close()

    async def start(self):
        loop = asyncio.get_event_loop()
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: self.Protocol(self),
            local_addr=(self.listen_host, self.listen_port)
        )
        self.start_time = time.time()
        self.status = "running"
        asyncio.create_task(self._update_history())
        logger.info(f"UDP proxy started: {self.listen_host}:{self.listen_port} -> {self.target_host}:{self.target_port}")
    
    async def _update_history(self):
        """Met à jour l'historique toutes les secondes"""
        last_packets_in = 0
        last_packets_out = 0
        last_bytes_in = 0
        last_bytes_out = 0
        while self.status == "running":
            await asyncio.sleep(1)
            packets_in_delta = self.packets_in - last_packets_in
            packets_out_delta = self.packets_out - last_packets_out
            bytes_in_delta = self.bytes_in - last_bytes_in
            bytes_out_delta = self.bytes_out - last_bytes_out
            
            total_packets = packets_in_delta + packets_out_delta
            if total_packets > self.peak_packets_per_sec:
                self.peak_packets_per_sec = total_packets
            
            self.packet_history.append({
                'time': time.time(),
                'packets_in': packets_in_delta,
                'packets_out': packets_out_delta
            })
            self.bytes_history.append({
                'time': time.time(),
                'bytes_in': bytes_in_delta,
                'bytes_out': bytes_out_delta
            })
            
            last_packets_in = self.packets_in
            last_packets_out = self.packets_out
            last_bytes_in = self.bytes_in
            last_bytes_out = self.bytes_out
            self.total_bytes_transferred = self.bytes_in + self.bytes_out

    async def stop(self):
        if self.transport:
            self.transport.close()
            self.status = "stopped"
            logger.info(f"UDP proxy stopped: {self.listen_host}:{self.listen_port}")
