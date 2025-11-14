#!/usr/bin/env python3
"""
Vérification de la configuration Cloudflare pour le mode flexible
"""
import sys

print("=" * 70)
print("☁️  CHECKLIST CLOUDFLARE - MODE FLEXIBLE")
print("=" * 70)

print("\n📋 Configuration DNS Cloudflare:")
print("   [ ] byakura.ovh pointe vers l'IP de votre VPS")
print("   [ ] Le nuage orange (proxy) est ACTIVÉ sur le DNS")

print("\n🔒 Configuration SSL/TLS:")
print("   [ ] Allez dans SSL/TLS → Overview")
print("   [ ] Mode de chiffrement: 'Flexible' ou 'Full'")
print("   [ ] Si 'Full': un certificat valide doit être sur votre VPS")
print("   [ ] Si 'Flexible': HTTP entre Cloudflare et votre serveur (non sécurisé)")

print("\n⚙️  Configuration ProxyOX (config.yaml):")
print("   [ ] bind: 0.0.0.0:443")
print("   [ ] flexible: true")
print("   [ ] mode: tcp")

print("\n🔥 Configuration Firewall VPS:")
print("   [ ] Port 443 ouvert en entrée (INPUT)")
print("   [ ] Commande Linux: sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT")
print("   [ ] ou: sudo ufw allow 443/tcp")

print("\n🚀 Démarrage ProxyOX:")
print("   [ ] Sur Linux: sudo python3 src/main.py")
print("   [ ] (sudo nécessaire pour le port 443)")
print("   [ ] Vérifier les logs: cherchez 'STARTED and LISTENING on 0.0.0.0:443'")

print("\n🔍 Tests de diagnostic:")
print("   1. Sur le VPS:")
print("      sudo python3 diagnostic.py")
print("      sudo netstat -tulpn | grep 443")
print()
print("   2. Depuis l'extérieur:")
print("      curl -v https://byakura.ovh")
print("      nmap -p 443 <IP_VPS>")

print("\n⚠️  PROBLÈMES COURANTS:")
print()
print("1️⃣  'Connection refused' ou pas de requête:")
print("   → Firewall bloque le port 443")
print("   → ProxyOX n'est pas démarré avec sudo")
print("   → bind sur 127.0.0.1 au lieu de 0.0.0.0")
print()
print("2️⃣  'SSL handshake failed':")
print("   → flexible: true n'est pas activé dans config.yaml")
print("   → Le module cryptography n'est pas installé")
print()
print("3️⃣  Cloudflare affiche 'Error 521 - Web server is down':")
print("   → Le port 443 n'est pas accessible sur votre VPS")
print("   → Le serveur backend est inaccessible")
print()
print("4️⃣  'Error 525 - SSL handshake failed':")
print("   → Mode SSL/TLS incorrect sur Cloudflare")
print("   → Utilisez 'Flexible' ou installez un vrai certificat pour 'Full'")

print("\n" + "=" * 70)
print("📞 AIDE AU DEBUG")
print("=" * 70)

print("\nSur le VPS, exécutez:")
print("  1. sudo python3 diagnostic.py")
print("  2. sudo python3 src/main.py")
print("     (notez les messages de démarrage)")
print("  3. Dans un autre terminal:")
print("     curl -k https://127.0.0.1:443")
print()
print("Si le test local fonctionne mais pas depuis Cloudflare:")
print("  → C'est un problème de firewall/réseau")
print()
print("Si le test local ne fonctionne pas:")
print("  → C'est un problème de configuration ProxyOX")

print("\n✅ Configuration recommandée pour byakura.ovh:")
print()
print("config.yaml:")
print("-" * 40)
print("""frontends:
  - name: cloudflare-fe
    bind: 0.0.0.0:443
    mode: tcp
    default_backend: your-server
    flexible: true

backends:
  - name: your-server
    server: 10.10.0.201:443
""")
print("-" * 40)

print("\n💾 Commande de démarrage:")
print("  sudo python3 src/main.py")
print()
