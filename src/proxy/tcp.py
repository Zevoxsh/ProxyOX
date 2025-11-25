import asyncio
import logging
import time
import ssl
from collections import deque
from pathlib import Path
from .ip_filter import IPFilter

logger = logging.getLogger("tcp_proxy")

class TCPProxy:
    def __init__(self, listen_host, listen_port, target_host, target_port, use_tls=False, certfile=None, keyfile=None, backend_ssl=False, max_connections=100, rate_limit=1000, ip_filter=None):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.target_host = target_host
        self.target_port = target_port
        self.use_tls = use_tls  # SSL pour écouter (côté client)
        self.backend_ssl = backend_ssl  # SSL pour se connecter au backend
        self.certfile = certfile
        self.keyfile = keyfile
        self.max_connections = max_connections
        self.rate_limit = rate_limit  # Connexions par seconde
        self.ip_filter = ip_filter  # Filtre IP
        self.server = None
        self.bytes_in = 0
        self.bytes_out = 0
        self.active_connections = 0
        self.total_connections = 0
        self.failed_connections = 0
        self.blocked_ips = 0  # Nombre d'IPs bloquées
        self.start_time = None
        self.status = "stopped"
        self.last_error = None
        self.last_error_time = None
        self.connection_history = deque(maxlen=100)  # Garde les 100 dernières connexions
        self.bytes_history = deque(maxlen=60)  # 60 secondes d'historique
        self.peak_connections = 0
        self.total_bytes_transferred = 0
        self.rate_limiter = deque(maxlen=rate_limit)  # Timestamps des dernières connexions

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
        # IP Filtering
        client_addr = client_writer.get_extra_info('peername')
        client_ip = client_addr[0] if client_addr else None
        
        if self.ip_filter and client_ip and not self.ip_filter.is_allowed(client_ip):
            self.blocked_ips += 1
            self.failed_connections += 1
            logger.warning(f"Blocked connection from {client_ip}")
            client_writer.close()
            await client_writer.wait_closed()
            return
        
        # Rate limiting
        now = time.time()
        self.rate_limiter.append(now)
        
        # Compter les connexions de la dernière seconde
        recent_conns = [t for t in self.rate_limiter if now - t <= 1.0]
        if len(recent_conns) > self.rate_limit:
            self.failed_connections += 1
            logger.warning(f"Rate limit exceeded: {len(recent_conns)}/{self.rate_limit}")
            client_writer.close()
            await client_writer.wait_closed()
            return
        
        # Max connections check
        if self.active_connections >= self.max_connections:
            self.failed_connections += 1
            logger.warning(f"Max connections reached: {self.active_connections}/{self.max_connections}")
            client_writer.close()
            await client_writer.wait_closed()
            return
        
        self.active_connections += 1
        self.total_connections += 1
        if self.active_connections > self.peak_connections:
            self.peak_connections = self.active_connections
        
        conn_start = time.time()
        client_addr = client_writer.get_extra_info('peername')
        logger.info(f"[TCP] New connection from {client_addr} (total: {self.total_connections}, active: {self.active_connections})")
        
        try:
            logger.info(f"[TCP] Connecting to upstream {self.target_host}:{self.target_port} for client {client_addr}")
            
            # Créer un contexte SSL si le backend utilise HTTPS
            ssl_context = None
            if self.backend_ssl:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE  # Accepte les certificats auto-signés
                logger.info(f"[TCP] Connecting with SSL to backend")
            
            upstream_reader, upstream_writer = await asyncio.open_connection(
                self.target_host, 
                self.target_port,
                ssl=ssl_context
            )
            logger.info(f"[TCP] Connected to upstream {self.target_host}:{self.target_port} {'(SSL)' if self.backend_ssl else ''}")
        except Exception as e:
            logger.error(f"❌ Cannot connect upstream {self.target_host}:{self.target_port}: {e}")
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
        ssl_context = None
        if self.use_tls:
            # Mode flexible Cloudflare : TLS côté client, TCP vers backend
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            
            if self.certfile and self.keyfile:
                if Path(self.certfile).exists() and Path(self.keyfile).exists():
                    ssl_context.load_cert_chain(certfile=self.certfile, keyfile=self.keyfile)
                    logger.info(f"TLS enabled with cert: {self.certfile}")
                else:
                    logger.warning(f"TLS cert/key files not found, using self-signed certificate")
                    # Générer un certificat auto-signé pour le développement
                    ssl_context = self._create_self_signed_context()
            else:
                logger.info("TLS enabled with self-signed certificate")
                ssl_context = self._create_self_signed_context()
        
        try:
            self.server = await asyncio.start_server(
                self.handle_client, 
                self.listen_host, 
                self.listen_port,
                ssl=ssl_context
            )
            self.start_time = time.time()
            self.status = "running"
            asyncio.create_task(self._update_bytes_history())
            tls_status = " (TLS)" if self.use_tls else ""
            logger.info(f"✅ TCP proxy{tls_status} STARTED and LISTENING on {self.listen_host}:{self.listen_port} -> {self.target_host}:{self.target_port}")
            logger.info(f"[TCP] Server is ready to accept connections on port {self.listen_port}")
        except Exception as e:
            logger.error(f"❌ FAILED to start TCP proxy on {self.listen_host}:{self.listen_port}: {e}")
            self.status = "failed"
            self.last_error = str(e)
            self.last_error_time = time.time()
            raise
    
    def _create_self_signed_context(self):
        """Crée un contexte SSL avec certificat auto-signé pour le développement"""
        import tempfile
        import os
        from datetime import datetime, timedelta
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            
            # Générer une clé privée
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            
            # Créer un certificat auto-signé
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "ProxyOX"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "Local"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ProxyOX"),
                x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
            ])
            
            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                private_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.utcnow()
            ).not_valid_after(
                datetime.utcnow() + timedelta(days=365)
            ).add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.DNSName("*.localhost"),
                ]),
                critical=False,
            ).sign(private_key, hashes.SHA256())
            
            # Créer des fichiers temporaires
            cert_pem = cert.public_bytes(serialization.Encoding.PEM)
            key_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            # Écrire dans des fichiers temporaires
            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.crt') as cert_file:
                cert_file.write(cert_pem)
                cert_filename = cert_file.name
            
            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.key') as key_file:
                key_file.write(key_pem)
                key_filename = key_file.name
            
            # Créer le contexte SSL
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(certfile=cert_filename, keyfile=key_filename)
            
            # Nettoyer les fichiers temporaires (ils sont déjà chargés en mémoire)
            try:
                os.unlink(cert_filename)
                os.unlink(key_filename)
            except:
                pass
            
            return ssl_context
            
        except ImportError:
            logger.warning("cryptography module not available, TLS will not work without cert files")
            return None
    
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
