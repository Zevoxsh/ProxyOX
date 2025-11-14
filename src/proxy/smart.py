"""
Smart Proxy avec auto-détection HTTP/HTTPS
Détecte automatiquement si la connexion entrante est HTTP ou HTTPS
et adapte le comportement en conséquence.
"""

import asyncio
import logging
import time
import ssl
from collections import deque
from pathlib import Path

logger = logging.getLogger("smart_proxy")

class SmartProxy:
    """
    Proxy intelligent qui détecte automatiquement HTTP vs HTTPS
    - Lit les premiers octets de la connexion
    - Détecte si c'est du TLS (0x16) ou du HTTP (lettres ASCII)
    - Route vers le handler approprié
    """
    
    def __init__(self, listen_host, listen_port, target_host, target_port, certfile=None, keyfile=None):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.target_host = target_host
        self.target_port = target_port
        self.certfile = certfile
        self.keyfile = keyfile
        self.server = None
        self.ssl_context = None
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
        """Point d'entrée pour chaque nouvelle connexion"""
        self.active_connections += 1
        self.total_connections += 1
        
        if self.active_connections > self.peak_connections:
            self.peak_connections = self.active_connections
        
        conn_start = time.time()
        client_addr = writer.get_extra_info('peername')
        
        try:
            # Lire le premier octet pour détecter le type de connexion
            first_byte_data = await asyncio.wait_for(reader.read(1), timeout=5.0)
            
            if not first_byte_data:
                logger.warning(f"[SMART] Empty connection from {client_addr}")
                writer.close()
                await writer.wait_closed()
                self.active_connections -= 1
                return
            
            first_byte = first_byte_data[0]
            
            # Détection automatique du protocole
            if self._is_tls_handshake(first_byte):
                # C'est du HTTPS - Mode Cloudflare Full
                logger.info(f"[SMART] 🔒 HTTPS detected from {client_addr} (Cloudflare Full mode)")
                self.https_connections += 1
                await self._handle_https(first_byte_data, reader, writer, client_addr, conn_start)
            else:
                # C'est du HTTP - Mode Cloudflare Flexible
                logger.info(f"[SMART] 📄 HTTP detected from {client_addr} (Cloudflare Flexible mode)")
                self.http_connections += 1
                await self._handle_http(first_byte_data, reader, writer, client_addr, conn_start)
                
        except asyncio.TimeoutError:
            logger.warning(f"[SMART] ⏱️ Timeout from {client_addr}")
            self.failed_connections += 1
            writer.close()
            await writer.wait_closed()
            self.active_connections -= 1
        except Exception as e:
            logger.error(f"[SMART] ❌ Error from {client_addr}: {e}")
            self.failed_connections += 1
            self.last_error = str(e)
            self.last_error_time = time.time()
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
            self.active_connections -= 1

    def _is_tls_handshake(self, first_byte):
        """
        Détecte si c'est un handshake TLS
        TLS commence par: 0x16 (handshake), 0x14 (change cipher), 0x15 (alert), 0x17 (app data)
        HTTP commence par: G (GET), P (POST), H (HEAD), etc. (0x47, 0x50, 0x48...)
        """
        return first_byte in (0x16, 0x14, 0x15, 0x17)

    async def _handle_https(self, first_byte_data, plain_reader, plain_writer, client_addr, conn_start):
        """
        Gère une connexion HTTPS (Mode Cloudflare Full)
        1. Upgrade la connexion vers SSL
        2. Déchiffre le trafic
        3. Envoie en HTTP au backend
        """
        try:
            # On doit upgrader la connexion vers SSL
            # Comme on a déjà lu 1 byte, on doit le remettre dans le stream
            
            # Créer un buffer avec le premier byte + le reste
            remaining_data = await plain_reader.read(8192)
            full_data = first_byte_data + remaining_data
            
            # Créer un SSLContext
            if not self.ssl_context:
                self.ssl_context = self._get_ssl_context()
            
            if not self.ssl_context:
                logger.error("[SMART] Cannot create SSL context for HTTPS")
                plain_writer.close()
                await plain_writer.wait_closed()
                self.active_connections -= 1
                return
            
            # On ne peut pas upgrader un stream déjà créé facilement
            # Solution: créer un nouveau socket SSL dès le début
            # Pour l'instant, on va simplement logger et fermer
            logger.warning(f"[SMART] HTTPS upgrade not yet implemented, closing connection")
            logger.info(f"[SMART] Detected TLS handshake: {first_byte_data[0]:02x}")
            
            plain_writer.close()
            await plain_writer.wait_closed()
            self.active_connections -= 1
            
            # TODO: Implémenter l'upgrade SSL proprement
            
        except Exception as e:
            logger.error(f"[SMART] Error in HTTPS handler: {e}")
            self.failed_connections += 1
            try:
                plain_writer.close()
                await plain_writer.wait_closed()
            except:
                pass
            self.active_connections -= 1

    async def _handle_http(self, first_byte_data, reader, writer, client_addr, conn_start):
        """
        Gère une connexion HTTP simple (Mode Cloudflare Flexible)
        Simple relay TCP vers le backend
        """
        try:
            # Connexion au backend
            logger.info(f"[SMART] Connecting to backend {self.target_host}:{self.target_port}")
            upstream_reader, upstream_writer = await asyncio.open_connection(
                self.target_host,
                self.target_port
            )
            
            # Envoyer le premier byte au backend
            upstream_writer.write(first_byte_data)
            await upstream_writer.drain()
            
            # Relayer le reste
            await self._relay_bidirectional(reader, writer, upstream_reader, upstream_writer, client_addr, conn_start, "HTTP")
            
        except Exception as e:
            logger.error(f"[SMART] Error in HTTP handler: {e}")
            self.failed_connections += 1
            self.last_error = str(e)
            self.last_error_time = time.time()
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
            self.active_connections -= 1

    async def _relay_bidirectional(self, client_reader, client_writer, upstream_reader, upstream_writer, client_addr, conn_start, mode):
        """Relaye les données dans les deux sens"""
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
                logger.debug(f"[SMART] Client->Upstream ended: {e}")
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
                logger.debug(f"[SMART] Upstream->Client ended: {e}")
            finally:
                try:
                    client_writer.write_eof()
                except:
                    pass

        # Lancer les deux relais en parallèle
        t1 = asyncio.create_task(relay_client_to_upstream())
        t2 = asyncio.create_task(relay_upstream_to_client())

        await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)
        
        t1.cancel()
        t2.cancel()
        
        # Fermer les connexions
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
        
        # Stats
        duration = time.time() - conn_start
        self.connection_history.append({
            'time': conn_start,
            'client': str(client_addr),
            'duration': duration,
            'bytes_in': conn_bytes_in,
            'bytes_out': conn_bytes_out,
            'status': 'success',
            'mode': mode
        })
        
        self.active_connections -= 1
        logger.info(f"[SMART] ✅ {mode} connection from {client_addr}: {duration:.2f}s, ↓{conn_bytes_in}B ↑{conn_bytes_out}B")

    def _get_ssl_context(self):
        """Crée un contexte SSL pour accepter HTTPS"""
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        
        if self.certfile and self.keyfile:
            if Path(self.certfile).exists() and Path(self.keyfile).exists():
                ssl_context.load_cert_chain(certfile=self.certfile, keyfile=self.keyfile)
                logger.info(f"[SMART] Using custom SSL cert: {self.certfile}")
                return ssl_context
        
        # Générer un certificat auto-signé
        logger.info("[SMART] Generating self-signed certificate")
        return self._create_self_signed_context()

    def _create_self_signed_context(self):
        """Génère un certificat auto-signé"""
        import tempfile
        import os
        from datetime import datetime, timedelta
        
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            
            private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "ProxyOX"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "Smart Proxy"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ProxyOX Auto"),
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
            
            cert_pem = cert.public_bytes(serialization.Encoding.PEM)
            key_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.crt') as f:
                f.write(cert_pem)
                cert_file = f.name
            
            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.key') as f:
                f.write(key_pem)
                key_file = f.name
            
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(certfile=cert_file, keyfile=key_file)
            
            try:
                os.unlink(cert_file)
                os.unlink(key_file)
            except:
                pass
            
            return ssl_context
            
        except ImportError:
            logger.error("[SMART] cryptography module not available")
            return None
        except Exception as e:
            logger.error(f"[SMART] Error creating self-signed cert: {e}")
            return None

    async def start(self):
        """Démarre le serveur en mode auto-détection"""
        try:
            # Démarrer SANS SSL - on détecte manuellement
            self.server = await asyncio.start_server(
                self.handle_client,
                self.listen_host,
                self.listen_port
            )
            
            self.start_time = time.time()
            self.status = "running"
            asyncio.create_task(self._update_bytes_history())
            
            logger.info(f"✅ SMART PROXY STARTED on {self.listen_host}:{self.listen_port}")
            logger.info(f"   - Target: {self.target_host}:{self.target_port}")
            logger.info(f"   - Auto-detection: HTTP and HTTPS")
            logger.info(f"   - Cloudflare Flexible: HTTP → HTTP ✅")
            logger.info(f"   - Cloudflare Full: HTTPS → HTTP ⚠️ (partial support)")
            
        except Exception as e:
            logger.error(f"❌ Failed to start smart proxy on {self.listen_host}:{self.listen_port}: {e}")
            self.status = "failed"
            self.last_error = str(e)
            self.last_error_time = time.time()
            raise

    async def _update_bytes_history(self):
        """Historique des bytes"""
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
        """Arrête le serveur"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.status = "stopped"
            logger.info(f"[SMART] Proxy stopped")

    def get_stats(self):
        """Statistiques"""
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
