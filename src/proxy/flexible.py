"""
Proxy flexible qui détecte automatiquement HTTP et HTTPS (modes Cloudflare Flexible et Full)
- Détection auto: HTTP (client) -> HTTP (backend)
- Mode avec SSL: HTTPS (client) -> HTTP (backend) - Cloudflare Flexible
"""

import asyncio
import logging
import time
import ssl
from collections import deque
from pathlib import Path

logger = logging.getLogger("flexible_proxy")

class FlexibleProxy:
    """
    Proxy pour Cloudflare Flexible SSL:
    - Accepte les connexions HTTPS côté client (avec certificat auto-signé)
    - Transmet en HTTP simple vers le backend
    - Cloudflare gère le TLS avec les vrais certificats
    """
    
    def __init__(self, listen_host, listen_port, target_host, target_port, certfile=None, keyfile=None):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.target_host = target_host
        self.target_port = target_port
        self.certfile = certfile
        self.keyfile = keyfile
        self.server = None
        self.bytes_in = 0
        self.bytes_out = 0
        self.active_connections = 0
        self.total_connections = 0
        self.failed_connections = 0
        self.https_connections = 0
        self.http_connections = 0
        self.start_time = None
        self.status = "stopped"
        self.last_error = None
        self.last_error_time = None
        self.connection_history = deque(maxlen=100)
        self.bytes_history = deque(maxlen=60)
        self.peak_connections = 0
        self.total_bytes_transferred = 0

    async def handle_client(self, reader, writer):
        """Gère une connexion client (HTTPS déchiffré automatiquement par asyncio)"""
        self.active_connections += 1
        self.total_connections += 1
        self.https_connections += 1  # Toutes les connexions sur ce serveur sont HTTPS
        
        if self.active_connections > self.peak_connections:
            self.peak_connections = self.active_connections
        
        conn_start = time.time()
        client_addr = writer.get_extra_info('peername')
        logger.info(f"[FLEXIBLE] New HTTPS connection from {client_addr}")
        
        try:
            # Connexion au backend en HTTP simple (non chiffré)
            logger.info(f"[FLEXIBLE] Connecting to backend HTTP {self.target_host}:{self.target_port}")
            upstream_reader, upstream_writer = await asyncio.open_connection(
                self.target_host,
                self.target_port
            )
            
            # Relayer les données (HTTPS déchiffré -> HTTP simple)
            await self._relay_connection(reader, writer, upstream_reader, upstream_writer, client_addr, conn_start)
            
        except Exception as e:
            logger.error(f"[FLEXIBLE] Error handling connection from {client_addr}: {e}")
            self.failed_connections += 1
            self.last_error = str(e)
            self.last_error_time = time.time()
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
            self.active_connections -= 1

    async def _relay_connection(self, client_reader, client_writer, upstream_reader, upstream_writer, client_addr, conn_start):
        """Relaye les données entre client et backend"""
        conn_bytes_in = 0
        conn_bytes_out = 0
        
        async def relay_client_to_upstream():
            nonlocal conn_bytes_in
            try:
                while True:
                    data = await client_reader.read(8192)
                    if not data:
                        break
                    upstream_writer.write(data)
                    await upstream_writer.drain()
                    conn_bytes_in += len(data)
                    self.bytes_in += len(data)
            except Exception as e:
                logger.debug(f"[FLEXIBLE] Client->Upstream relay ended: {e}")
            finally:
                try:
                    upstream_writer.write_eof()
                except:
                    pass

        async def relay_upstream_to_client():
            nonlocal conn_bytes_out
            try:
                while True:
                    data = await upstream_reader.read(8192)
                    if not data:
                        break
                    client_writer.write(data)
                    await client_writer.drain()
                    conn_bytes_out += len(data)
                    self.bytes_out += len(data)
            except Exception as e:
                logger.debug(f"[FLEXIBLE] Upstream->Client relay ended: {e}")
            finally:
                try:
                    client_writer.write_eof()
                except:
                    pass

        # Lancer les deux relais en parallèle
        t1 = asyncio.create_task(relay_client_to_upstream())
        t2 = asyncio.create_task(relay_upstream_to_client())

        await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)
        
        # Annuler les tâches restantes
        t1.cancel()
        t2.cancel()
        
        # Nettoyer les connexions
        try:
            upstream_writer.close()
            await upstream_writer.wait_closed()
        except:
            pass
        
        try:
            client_writer.close()
            await client_writer.wait_closed()
        except:
            pass
        
        # Enregistrer les stats
        duration = time.time() - conn_start
        self.connection_history.append({
            'time': conn_start,
            'client': str(client_addr),
            'duration': duration,
            'bytes_in': conn_bytes_in,
            'bytes_out': conn_bytes_out,
            'status': 'success',
            'mode': 'HTTPS->HTTP'
        })
        
        self.active_connections -= 1
        logger.info(f"[FLEXIBLE] Connection closed from {client_addr} (HTTPS->HTTP), duration: {duration:.2f}s, in: {conn_bytes_in}, out: {conn_bytes_out}")

    def _get_ssl_context(self):
        """Obtient ou crée un contexte SSL pour accepter les connexions HTTPS"""
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        
        if self.certfile and self.keyfile:
            if Path(self.certfile).exists() and Path(self.keyfile).exists():
                ssl_context.load_cert_chain(certfile=self.certfile, keyfile=self.keyfile)
                logger.info(f"[FLEXIBLE] Using custom SSL cert: {self.certfile}")
                return ssl_context
        
        # Générer un certificat auto-signé
        logger.info("[FLEXIBLE] Generating self-signed certificate for HTTPS")
        return self._create_self_signed_context()

    def _create_self_signed_context(self):
        """Crée un contexte SSL avec certificat auto-signé"""
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
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ProxyOX Flexible"),
                x509.NameAttribute(NameOID.COMMON_NAME, "*.proxyox.local"),
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
                    x509.DNSName("*.proxyox.local"),
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
            
            # Nettoyer les fichiers temporaires
            try:
                os.unlink(cert_filename)
                os.unlink(key_filename)
            except:
                pass
            
            return ssl_context
            
        except ImportError:
            logger.error("[FLEXIBLE] cryptography module not available, cannot create self-signed cert")
            return None
        except Exception as e:
            logger.error(f"[FLEXIBLE] Error creating self-signed cert: {e}")
            return None

    async def start(self):
        """Démarre le serveur proxy flexible avec support SSL"""
        try:
            # Créer le contexte SSL pour accepter les connexions HTTPS
            ssl_context = self._get_ssl_context()
            
            if not ssl_context:
                logger.error("[FLEXIBLE] Cannot create SSL context, aborting")
                raise RuntimeError("SSL context creation failed")
            
            # Démarrer le serveur AVEC SSL pour accepter HTTPS
            # Le SSL déchiffre automatiquement, puis on envoie en HTTP vers le backend
            self.server = await asyncio.start_server(
                self.handle_client,
                self.listen_host,
                self.listen_port,
                ssl=ssl_context
            )
            self.start_time = time.time()
            self.status = "running"
            asyncio.create_task(self._update_bytes_history())
            
            logger.info(f"✅ FLEXIBLE PROXY STARTED on {self.listen_host}:{self.listen_port}")
            logger.info(f"   - Target: {self.target_host}:{self.target_port}")
            logger.info(f"   - Mode: HTTPS (client) -> HTTP (backend)")
            logger.info(f"   - Perfect for Cloudflare Flexible SSL")
            
        except Exception as e:
            logger.error(f"❌ FAILED to start flexible proxy on {self.listen_host}:{self.listen_port}: {e}")
            self.status = "failed"
            self.last_error = str(e)
            self.last_error_time = time.time()
            raise

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
        """Arrête le serveur proxy"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.status = "stopped"
            logger.info(f"[FLEXIBLE] Proxy stopped: {self.listen_host}:{self.listen_port}")

    def get_stats(self):
        """Retourne les statistiques du proxy"""
        uptime = time.time() - self.start_time if self.start_time else 0
        return {
            'status': self.status,
            'uptime': uptime,
            'total_connections': self.total_connections,
            'https_connections': self.https_connections,
            'http_connections': self.http_connections,
            'active_connections': self.active_connections,
            'failed_connections': self.failed_connections,
            'peak_connections': self.peak_connections,
            'bytes_in': self.bytes_in,
            'bytes_out': self.bytes_out,
            'total_bytes': self.total_bytes_transferred,
            'last_error': self.last_error,
            'last_error_time': self.last_error_time
        }
