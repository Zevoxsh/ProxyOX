#!/usr/bin/env python3
"""
Script de diagnostic pour ProxyOX
Vérifie que le proxy est bien configuré et accessible
"""
import socket
import ssl
import sys

def check_port_listening(host, port):
    """Vérifie si un port est en écoute"""
    print(f"\n🔍 Vérification si le port {port} est en écoute sur {host}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✅ Port {port} est OUVERT et en écoute")
            return True
        else:
            print(f"❌ Port {port} est FERMÉ (code: {result})")
            return False
    except Exception as e:
        print(f"❌ Erreur lors de la vérification du port {port}: {e}")
        return False

def check_tls_connection(host, port):
    """Vérifie si une connexion TLS est possible"""
    print(f"\n🔍 Test de connexion TLS sur {host}:{port}...")
    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE  # Accepter les certificats auto-signés
        
        with socket.create_connection((host, port), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                print(f"✅ Connexion TLS établie")
                print(f"   Version TLS: {ssock.version()}")
                cert = ssock.getpeercert()
                if cert:
                    print(f"   Certificat: {cert}")
                else:
                    print(f"   Certificat auto-signé détecté")
                return True
    except ssl.SSLError as e:
        print(f"❌ Erreur SSL/TLS: {e}")
        return False
    except socket.timeout:
        print(f"❌ Timeout - le serveur ne répond pas")
        return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def check_firewall():
    """Conseils pour vérifier le firewall"""
    print("\n🔥 Vérifications firewall à effectuer:")
    print("   Sur Linux:")
    print("     sudo iptables -L -n | grep 443")
    print("     sudo ufw status")
    print("     sudo firewall-cmd --list-all")
    print("\n   Sur Windows:")
    print("     netsh advfirewall firewall show rule name=all | findstr 443")
    print("     Get-NetFirewallRule | Where-Object {$_.DisplayName -like '*443*'}")

def main():
    print("=" * 60)
    print("🔧 Diagnostic ProxyOX - Mode Flexible Cloudflare")
    print("=" * 60)
    
    # Configuration
    listen_host = "0.0.0.0"
    listen_port = 443
    
    # Test 1: Port en écoute localement
    print("\n📋 TEST 1: Port en écoute local")
    local_ok = check_port_listening("127.0.0.1", listen_port)
    
    # Test 2: Port accessible sur toutes les interfaces
    print("\n📋 TEST 2: Port accessible sur 0.0.0.0")
    # Note: On ne peut pas tester 0.0.0.0 directement, on teste l'IP locale
    
    # Test 3: Connexion TLS
    print("\n📋 TEST 3: Connexion TLS")
    if local_ok:
        tls_ok = check_tls_connection("127.0.0.1", listen_port)
    else:
        print("⚠️  Impossible de tester TLS - port non accessible")
        tls_ok = False
    
    # Conseils firewall
    check_firewall()
    
    # Résumé
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ")
    print("=" * 60)
    
    if local_ok and tls_ok:
        print("✅ Le proxy semble fonctionner correctement en local")
        print("\n⚠️  Si Cloudflare ne peut pas se connecter:")
        print("   1. Vérifiez que le port 443 est ouvert dans votre firewall")
        print("   2. Vérifiez que le port 443 est forwardé si vous êtes derrière un NAT")
        print("   3. Vérifiez les logs du proxy: tail -f /var/log/proxyox.log")
        print("   4. Sur Cloudflare, vérifiez que SSL/TLS est en mode 'Flexible' ou 'Full'")
    elif local_ok and not tls_ok:
        print("⚠️  Port ouvert mais TLS ne fonctionne pas")
        print("   - Vérifiez que flexible: true est bien dans config.yaml")
        print("   - Vérifiez que le module cryptography est installé: pip install cryptography")
    else:
        print("❌ Le proxy ne semble pas démarré ou accessible")
        print("   - Vérifiez que ProxyOX est bien lancé")
        print("   - Vérifiez les logs au démarrage")
        print("   - Sur Linux, le port 443 nécessite sudo: sudo python src/main.py")
    
    print("\n💡 Commandes utiles:")
    print("   - Vérifier si le port écoute: netstat -tulpn | grep 443  (Linux)")
    print("   - Vérifier si le port écoute: netstat -an | findstr 443  (Windows)")
    print("   - Tester depuis l'extérieur: curl -k https://byakura.ovh")
    print("   - Voir les logs: python src/main.py")

if __name__ == "__main__":
    main()
