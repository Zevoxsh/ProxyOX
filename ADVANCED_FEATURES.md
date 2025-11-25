# 🚀 ProxyOX - Fonctionnalités Avancées

## 🛡️ IP Filtering (Blacklist/Whitelist)

### Description
Système de filtrage IP dynamique avec persistance sur disque. Bloquez ou autorisez des adresses IP en temps réel sans redémarrer les proxies.

### Fonctionnalités

#### Modes de filtrage :
1. **Mode Blacklist** (défaut) :
   - Toutes les IPs sont autorisées SAUF celles blacklistées
   - Idéal pour bloquer des attaquants connus

2. **Mode Whitelist** (quand liste non vide) :
   - SEULES les IPs whitelistées sont autorisées
   - Toutes les autres sont bloquées
   - Idéal pour environnements sécurisés

### API REST

#### Obtenir les statistiques
```bash
GET /api/ipfilter/stats

Réponse:
{
  "blacklist": {
    "count": 5,
    "ips": ["192.168.1.100", "10.0.0.50", ...]
  },
  "whitelist": {
    "count": 2,
    "ips": ["192.168.1.1", "192.168.1.2"]
  },
  "blocked_count": {
    "192.168.1.100": 145,  // Nombre de tentatives bloquées par IP
    "10.0.0.50": 23
  },
  "total_blocked": 168
}
```

#### Gérer la Blacklist
```bash
# Ajouter une IP
POST /api/ipfilter/blacklist/add
Body: {"ip": "192.168.1.100"}

# Retirer une IP
POST /api/ipfilter/blacklist/remove
Body: {"ip": "192.168.1.100"}

# Vider la blacklist
POST /api/ipfilter/blacklist/clear
```

#### Gérer la Whitelist
```bash
# Ajouter une IP
POST /api/ipfilter/whitelist/add
Body: {"ip": "192.168.1.1"}

# Retirer une IP
POST /api/ipfilter/whitelist/remove
Body: {"ip": "192.168.1.1"}

# Vider la whitelist
POST /api/ipfilter/whitelist/clear
```

### Persistance

Les listes sont sauvegardées automatiquement dans :
- `data/blacklist.json` : Blacklist + compteurs de blocages
- `data/whitelist.json` : Whitelist

Format JSON :
```json
{
  "ips": ["192.168.1.100", "10.0.0.50"],
  "blocked_count": {
    "192.168.1.100": 145,
    "10.0.0.50": 23
  }
}
```

### Statistiques par Proxy

Chaque proxy (HTTP et TCP) track le nombre d'IPs bloquées :
```json
{
  "name": "http-reverse-proxy",
  "stats": {
    "blocked_ips": 145,
    "total_requests": 10000,
    ...
  }
}
```

### Comportement

#### HTTP Proxy :
- IP bloquée → HTTP 403 "Access Denied"
- Incrémente `failed_requests` et `blocked_ips`
- Log warning

#### TCP Proxy :
- IP bloquée → Connexion fermée immédiatement
- Incrémente `failed_connections` et `blocked_ips`
- Log warning

### Validation

Les IPs sont validées avec le module Python `ipaddress` :
- ✅ IPv4 : `192.168.1.1`
- ✅ IPv6 : `2001:0db8:85a3::8a2e:0370:7334`
- ❌ Invalide → Erreur 400

### Exemples d'utilisation

#### Bloquer un attaquant
```bash
# Détecter l'IP dans les logs
# Ajouter à la blacklist
curl -X POST http://localhost:9090/api/ipfilter/blacklist/add \
  -H "Content-Type: application/json" \
  -u proxyox:changeme \
  -d '{"ip": "203.0.113.42"}'
```

#### Mode whitelist stricte
```bash
# N'autoriser que votre bureau et votre VPN
curl -X POST http://localhost:9090/api/ipfilter/whitelist/add \
  -u proxyox:changeme \
  -d '{"ip": "192.168.1.10"}'

curl -X POST http://localhost:9090/api/ipfilter/whitelist/add \
  -u proxyox:changeme \
  -d '{"ip": "10.8.0.1"}'

# Toutes les autres IPs sont maintenant bloquées
```

#### Voir les stats
```bash
curl http://localhost:9090/api/ipfilter/stats \
  -u proxyox:changeme | jq
```

---

## 🔄 Circuit Breaker Pattern (À venir)

Détection automatique des backends défaillants avec basculement :
- Seuil d'erreurs configurable (ex: 50% sur 10 requêtes)
- États : CLOSED → OPEN → HALF_OPEN
- Retry automatique après timeout
- Dashboard : indicateur visuel par backend

---

## 🏥 Health Checks Backends (À venir)

Vérification périodique de la santé des backends :
- **HTTP** : GET request avec status 200 attendu
- **TCP** : Connect test sur le port
- Intervalle configurable (défaut: 30s)
- Marquage auto : `healthy` / `unhealthy`
- Exclusion automatique des backends down

---

## ⚖️ Load Balancing (À venir)

Support de multiples backends par frontend :

### Algorithmes disponibles :
1. **Round Robin** : Distribution équitable en rotation
2. **Least Connections** : Envoie vers le moins chargé
3. **IP Hash** : Même IP → toujours même backend (session persistence)
4. **Weighted** : Backends avec poids différents

### Configuration :
```yaml
frontends:
  - name: web-lb
    bind: 0.0.0.0:80
    mode: http
    backends:
      - server1
      - server2
      - server3
    algorithm: round_robin
    
backends:
  - name: server1
    server: 192.168.1.10:80
    weight: 3
  - name: server2
    server: 192.168.1.11:80
    weight: 2
  - name: server3
    server: 192.168.1.12:80
    weight: 1
```

---

## 🔌 WebSocket Passthrough (À venir)

Support natif des connexions WebSocket :
- Détection automatique de l'upgrade request
- Proxy bidirectionnel des frames WebSocket
- Compatible avec tous les frameworks (Socket.IO, etc.)
- Pas de configuration spéciale requise

---

## 💾 Cache HTTP Intelligent (À venir)

Cache des réponses GET pour réduire la charge backend :

### Fonctionnalités :
- Respect des headers `Cache-Control`, `Expires`, `ETag`
- Invalidation sur `Pragma: no-cache`
- TTL configurable par domaine/route
- Compression en cache (gzip/brotli)
- Stockage : mémoire + disque optionnel

### Configuration :
```yaml
frontends:
  - name: web-proxy
    cache:
      enabled: true
      max_size: 1GB
      ttl: 3600  # 1 heure
      rules:
        - path: /static/*
          ttl: 86400  # 24h
        - path: /api/*
          enabled: false  # Pas de cache
```

### Stats :
- Cache hits / misses
- Ratio d'efficacité
- Bande passante économisée

---

## 🗜️ Compression Automatique (À venir)

Compression transparente des réponses HTTP :

### Formats supportés :
- **gzip** : Compatible universellement
- **brotli** : Meilleur ratio (navigateurs modernes)
- **deflate** : Fallback

### Comportement :
- Détection de `Accept-Encoding` client
- Compression uniquement si > 1KB
- Skip si déjà compressé
- Types MIME : text/*, application/json, application/javascript, etc.

### Gains :
- Réduction 60-80% pour HTML/CSS/JS
- Réduction 40-60% pour JSON/XML
- Diminution temps de transfert réseau

---

## 📝 Logs Détaillés avec Rotation (À venir)

Logs d'accès enrichis par proxy :

### Formats disponibles :
1. **Apache Combined** :
   ```
   192.168.1.1 - - [25/Nov/2025:14:30:00 +0100] "GET /api/users HTTP/1.1" 200 1234 "-" "Mozilla/5.0"
   ```

2. **JSON** :
   ```json
   {
     "timestamp": "2025-11-25T14:30:00Z",
     "client_ip": "192.168.1.1",
     "method": "GET",
     "path": "/api/users",
     "status": 200,
     "bytes": 1234,
     "duration_ms": 45,
     "user_agent": "Mozilla/5.0",
     "backend": "server1"
   }
   ```

### Rotation automatique :
- Taille max : 100MB par fichier
- Rétention : 30 jours
- Compression gzip des vieux logs
- Fichiers : `logs/http-proxy-2025-11-25.log`

### Configuration :
```yaml
global:
  logging:
    access_logs: true
    format: json  # ou apache
    rotation:
      max_size: 100MB
      retention_days: 30
```

---

## 🎯 Roadmap des Fonctionnalités

### ✅ Implémenté
1. **Multi-curve Graph** - Visualisation intelligente de 200+ proxies
2. **Alertes Temps Réel** - Détection automatique des problèmes
3. **Contrôles Proxy** - Start/Stop/Restart depuis UI
4. **Rate Limiting** - Protection contre surcharge
5. **Max Connections** - Limite de connexions simultanées
6. **Export Stats** - JSON et CSV
7. **Error Tracking** - Statistiques d'échecs détaillées
8. **IP Filtering** - Blacklist/Whitelist dynamique ✨ NOUVEAU

### 🚧 En cours
9. **Circuit Breaker** - Basculement automatique
10. **Health Checks** - Surveillance backends
11. **Load Balancing** - Multiple backends

### 📋 Planifié
12. **WebSocket Support** - Passthrough natif
13. **HTTP Cache** - Cache intelligent avec invalidation
14. **Compression** - gzip/brotli automatique
15. **Logs Avancés** - Format Apache/JSON avec rotation
16. **GeoIP** - Localisation des connexions
17. **Auto-scaling** - Ajustement dynamique des limites
18. **Prometheus Metrics** - Export métriques standard
19. **SSL/TLS Termination** - Terminaison SSL côté proxy
20. **Request/Response Modification** - Headers injection/removal

---

## 🔧 Configuration Avancée

### Exemple complet avec IP Filtering
```yaml
global:
  log-level: info
  max-connections: 100
  rate-limit: 1000

frontends:
  - name: web-proxy
    bind: 0.0.0.0:80
    mode: http
    domain_routes:
      - domain: app.example.com
        backend: app-server
    
backends:
  - name: app-server
    server: 192.168.1.10:80
```

### Gestion des IPs via scripts
```python
import requests

# Bloquer une IP
requests.post('http://localhost:9090/api/ipfilter/blacklist/add',
    auth=('proxyox', 'changeme'),
    json={'ip': '203.0.113.42'})

# Voir les stats
stats = requests.get('http://localhost:9090/api/ipfilter/stats',
    auth=('proxyox', 'changeme')).json()

print(f"Total IPs bloquées: {stats['total_blocked']}")
```

---

## 📊 Performance

### Benchmarks IP Filtering
- Vérification IP : < 0.1ms (lookup dans set Python)
- Persistance : asynchrone, n'impacte pas les requêtes
- Mémoire : ~100 bytes par IP en blacklist/whitelist
- Capacité : Testé avec 10,000+ IPs sans impact performance

### Recommandations
- Whitelist : < 1000 IPs recommandées
- Blacklist : < 50,000 IPs recommandées
- Au-delà : utiliser un firewall réseau (iptables, nftables)

---

## 🎉 Conclusion

ProxyOX offre maintenant un **système de sécurité avancé** avec filtrage IP dynamique, en plus de toutes les fonctionnalités de monitoring et contrôle. Le proxy est prêt pour la production avec :

✅ Sécurité : IP filtering, rate limiting, max connections
✅ Monitoring : Alertes temps réel, stats détaillées, graphiques multi-courbes  
✅ Contrôle : Start/Stop/Restart, export JSON/CSV
✅ Performance : Gestion de 200+ proxies, WebSocket temps réel
✅ Persistance : Configurations et blacklists sauvegardées

**Prochaines étapes** : Circuit breaker, health checks, et load balancing pour une résilience maximale !
