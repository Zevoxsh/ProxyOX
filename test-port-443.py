#!/usr/bin/env python3
"""
Test simple pour vérifier si le port 443 peut être utilisé
"""
import asyncio
import sys

async def test_port_443():
    print("🔍 Test d'écoute sur le port 443...")
    try:
        server = await asyncio.start_server(
            lambda r, w: None,
            "0.0.0.0",
            443
        )
        print("✅ SUCCESS: Le port 443 est accessible")
        print("   → ProxyOX devrait pouvoir démarrer sur ce port")
        server.close()
        await server.wait_closed()
        return True
    except PermissionError:
        print("❌ PERMISSION DENIED: Le port 443 nécessite des privilèges root")
        print("   → Sur Linux: Lancez avec 'sudo python3 src/main.py'")
        print("   → Sur Windows: Lancez PowerShell en tant qu'administrateur")
        return False
    except OSError as e:
        if "already in use" in str(e).lower() or "address already in use" in str(e).lower():
            print("⚠️  Port 443 déjà utilisé par un autre processus")
            print("   → Vérifiez: sudo netstat -tulpn | grep 443")
            print("   → Ou arrêtez le processus qui utilise ce port")
        else:
            print(f"❌ ERREUR: {e}")
        return False
    except Exception as e:
        print(f"❌ ERREUR INATTENDUE: {e}")
        return False

async def test_tls():
    print("\n🔍 Test de génération de certificat auto-signé...")
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        from datetime import datetime, timedelta
        
        # Test simple de génération
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        subject = issuer = x509.Name([
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
            datetime.utcnow() + timedelta(days=1)
        ).sign(private_key, hashes.SHA256())
        
        print("✅ SUCCESS: Certificat auto-signé généré")
        print("   → Le mode flexible devrait fonctionner")
        return True
        
    except ImportError:
        print("❌ ERREUR: Module 'cryptography' non installé")
        print("   → Installez avec: pip install cryptography")
        return False
    except Exception as e:
        print(f"❌ ERREUR lors de la génération du certificat: {e}")
        return False

async def main():
    print("=" * 60)
    print("🧪 TEST DES PRÉREQUIS POUR LE MODE FLEXIBLE")
    print("=" * 60)
    
    port_ok = await test_port_443()
    tls_ok = await test_tls()
    
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ")
    print("=" * 60)
    
    if port_ok and tls_ok:
        print("✅ Tous les tests sont OK")
        print("   Le proxy devrait fonctionner en mode flexible!")
        print("\n💡 Lancez maintenant:")
        print("   sudo python3 src/main.py")
    else:
        print("❌ Certains tests ont échoué")
        print("\n🔧 Actions requises:")
        if not port_ok:
            print("   1. Lancez le proxy avec sudo (Linux) ou en admin (Windows)")
        if not tls_ok:
            print("   2. Installez cryptography: pip install cryptography")

if __name__ == "__main__":
    asyncio.run(main())
