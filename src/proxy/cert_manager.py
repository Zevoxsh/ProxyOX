"""
Gestionnaire de certificats SSL auto-signés pour le proxy HTTPS
Génère automatiquement des certificats pour chaque domaine/IP
"""
import ssl
import logging
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from datetime import datetime, timedelta
import ipaddress

logger = logging.getLogger("cert_manager")

class CertificateManager:
    """Gère la génération et le stockage des certificats SSL"""
    
    def __init__(self, cert_dir="certs"):
        self.cert_dir = Path(cert_dir)
        self.cert_dir.mkdir(exist_ok=True)
        self.ca_cert_path = self.cert_dir / "ca.crt"
        self.ca_key_path = self.cert_dir / "ca.key"
        
        # Créer une CA (Certificate Authority) si elle n'existe pas
        if not self.ca_cert_path.exists() or not self.ca_key_path.exists():
            self._generate_ca()
    
    def _generate_ca(self):
        """Génère une autorité de certification (CA) racine"""
        logger.info("🔐 Generating Root CA certificate...")
        
        # Générer une clé privée pour la CA
        ca_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Créer le certificat CA
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "FR"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Paris"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Paris"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ProxyOX"),
            x509.NameAttribute(NameOID.COMMON_NAME, "ProxyOX Root CA"),
        ])
        
        ca_cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            ca_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=3650)  # 10 ans
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
                key_encipherment=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        ).sign(ca_key, hashes.SHA256(), default_backend())
        
        # Sauvegarder la clé privée CA
        with open(self.ca_key_path, "wb") as f:
            f.write(ca_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        # Sauvegarder le certificat CA
        with open(self.ca_cert_path, "wb") as f:
            f.write(ca_cert.public_bytes(serialization.Encoding.PEM))
        
        logger.info(f"✅ Root CA generated: {self.ca_cert_path}")
        logger.info(f"⚠️  To trust this CA, import {self.ca_cert_path} in your browser/system")
    
    def generate_certificate(self, hostname, ip_addresses=None):
        """
        Génère un certificat SSL pour un hostname/IP donné
        
        Args:
            hostname: Le nom de domaine (ex: "localhost", "example.com")
            ip_addresses: Liste d'adresses IP à inclure (ex: ["127.0.0.1", "0.0.0.0"])
        
        Returns:
            Tuple (cert_path, key_path) ou None si erreur
        """
        if ip_addresses is None:
            ip_addresses = []
        
        # Nom des fichiers basé sur le hostname
        safe_hostname = hostname.replace("*", "wildcard").replace(".", "_")
        cert_path = self.cert_dir / f"{safe_hostname}.crt"
        key_path = self.cert_dir / f"{safe_hostname}.key"
        
        # Si le certificat existe déjà et est valide, le réutiliser
        if cert_path.exists() and key_path.exists():
            if self._is_cert_valid(cert_path):
                logger.info(f"♻️  Reusing existing certificate: {cert_path}")
                return str(cert_path), str(key_path)
        
        logger.info(f"🔐 Generating SSL certificate for: {hostname}")
        
        # Charger la CA
        with open(self.ca_key_path, "rb") as f:
            ca_key = serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())
        
        with open(self.ca_cert_path, "rb") as f:
            ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
        
        # Générer une clé privée pour ce certificat
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Créer le certificat
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "FR"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Paris"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Paris"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ProxyOX"),
            x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        ])
        
        # Construire les Subject Alternative Names (SANs)
        san_list = [x509.DNSName(hostname)]
        
        # Ajouter des variations communes
        if hostname == "localhost":
            san_list.append(x509.DNSName("localhost.localdomain"))
        
        # Ajouter les adresses IP
        for ip in ip_addresses:
            try:
                san_list.append(x509.IPAddress(ipaddress.ip_address(ip)))
            except ValueError:
                logger.warning(f"Invalid IP address: {ip}")
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            ca_cert.subject
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=365)  # 1 an
        ).add_extension(
            x509.SubjectAlternativeName(san_list),
            critical=False,
        ).add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        ).add_extension(
            x509.ExtendedKeyUsage([
                x509.ExtendedKeyUsageOID.SERVER_AUTH,
            ]),
            critical=True,
        ).sign(ca_key, hashes.SHA256(), default_backend())
        
        # Sauvegarder la clé privée
        with open(key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        # Sauvegarder le certificat
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        logger.info(f"✅ Certificate generated: {cert_path}")
        return str(cert_path), str(key_path)
    
    def _is_cert_valid(self, cert_path):
        """Vérifie si un certificat est encore valide"""
        try:
            with open(cert_path, "rb") as f:
                cert = x509.load_pem_x509_certificate(f.read(), default_backend())
            
            # Vérifier la date d'expiration
            now = datetime.utcnow()
            if now < cert.not_valid_before or now > cert.not_valid_after:
                return False
            
            # Vérifier qu'il reste au moins 30 jours
            days_left = (cert.not_valid_after - now).days
            if days_left < 30:
                logger.warning(f"Certificate expires in {days_left} days, will regenerate")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error checking certificate validity: {e}")
            return False
    
    def get_ssl_context(self, hostname="localhost", ip_addresses=None):
        """
        Crée un contexte SSL pour le serveur
        
        Args:
            hostname: Le nom de domaine
            ip_addresses: Liste d'IPs à inclure dans le certificat
        
        Returns:
            ssl.SSLContext configuré
        """
        cert_path, key_path = self.generate_certificate(hostname, ip_addresses)
        
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(cert_path, key_path)
        
        # Configuration pour accepter plus de clients
        ssl_context.options |= ssl.OP_NO_SSLv2
        ssl_context.options |= ssl.OP_NO_SSLv3
        ssl_context.options |= ssl.OP_NO_TLSv1
        ssl_context.options |= ssl.OP_NO_TLSv1_1
        
        return ssl_context
