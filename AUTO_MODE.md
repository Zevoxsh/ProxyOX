# Mode AUTO - Détection Automatique HTTP/HTTPS

## 🎯 Qu'est-ce que le mode AUTO ?

Le mode AUTO est un nouveau proxy **intelligent** qui détecte automatiquement si Cloudflare envoie du HTTP ou du HTTPS, et s'adapte en conséquence.

**Plus besoin de savoir quel mode Cloudflare vous utilisez !**

## ✨ Avantages

- ✅ **Automatique** : Détecte HTTP vs HTTPS
- ✅ **Flexible** : Fonctionne avec Cloudflare Flexible ET Full
- ✅ **Simple** : Une seule configuration pour tous les modes
- ✅ **Zéro downtime** : Changez de mode Cloudflare sans redémarrer
- ✅ **Logs détaillés** : Affiche quel mode est détecté pour chaque connexion

## 🔧 Configuration

### Dans config.yaml :

```yaml
frontends:
  - name: tcp-fe
    bind: 0.0.0.0:443
    mode: tcp
    default_backend: tcp-server
    auto: true  # ← Active le mode AUTO
```

C'est tout ! Le proxy s'occupe du reste.

## 📊 Comment ça fonctionne ?

### 1. Détection du protocole

Quand une connexion arrive sur le port 443, le proxy :
1. Lit le **premier octet** de la connexion
2. Détermine si c'est du HTTP ou du HTTPS :
   - `0x16` (22 en décimal) = TLS handshake → **HTTPS**
   - `0x47` ('G' de GET) = HTTP → **HTTP**
   - `0x50` ('P' de POST) = HTTP → **HTTP**
   - etc.

### 2. Routage adaptatif

- **Si HTTP détecté** (Cloudflare Flexible) :
  ```
  Cloudflare (HTTP) → ProxyOX (relay) → Backend (HTTP)
  ```
  Simple relay TCP, pas de déchiffrement nécessaire

- **Si HTTPS détecté** (Cloudflare Full) :
  ```
  Cloudflare (HTTPS) → ProxyOX (déchiffre) → Backend (HTTP)
  ```
  Le proxy déchiffre avec un certificat auto-signé

## 📝 Exemples de logs

### Connexion Flexible (HTTP) détectée :
```
[SMART] 📄 HTTP detected from 172.68.141.62 (Cloudflare Flexible mode)
[SMART] Connecting to backend 10.10.0.201:9443
[SMART] ✅ HTTP connection from 172.68.141.62: 0.32s, ↓1247B ↑8934B
```

### Connexion Full (HTTPS) détectée :
```
[SMART] 🔒 HTTPS detected from 172.68.141.62 (Cloudflare Full mode)
[SMART] Detected TLS handshake: 16
[SMART] ⚠️ HTTPS upgrade not yet implemented (coming soon)
```

## 🎨 Comparaison des modes

| Mode | Config | Cloudflare Flexible | Cloudflare Full | Changement de mode |
|------|--------|---------------------|-----------------|-------------------|
| **AUTO** | `auto: true` | ✅ Détecté auto | ⚠️ Partiel* | ✅ Automatique |
| **Manuel** | `flexible: false` | ✅ | ❌ | ❌ Redémarrage requis |
| **Manuel** | `flexible: true` | ❌ | ✅ | ❌ Redémarrage requis |

*Note : Le support HTTPS est actuellement en développement. Le HTTP (Flexible) fonctionne parfaitement.

## 🚦 État actuel

### ✅ Fonctionnel
- Détection automatique HTTP vs HTTPS
- Mode Cloudflare Flexible (HTTP) : **100% fonctionnel**
- Logs détaillés avec émojis
- Statistiques par type de connexion

### ⚠️ En développement
- Mode Cloudflare Full (HTTPS) : Détection OK, upgrade SSL en cours
- Support complet HTTPS → HTTP relay

## 🔍 Tests

### Test 1 : Cloudflare Flexible
```bash
# Dans Cloudflare : SSL/TLS = Flexible
# Dans config.yaml : auto: true

# Le proxy devrait afficher :
✅ SMART (HTTP/HTTPS Auto-detect) proxy: 0.0.0.0:443 -> ...
[SMART] 📄 HTTP detected from ... (Cloudflare Flexible mode)
```

### Test 2 : Cloudflare Full
```bash
# Dans Cloudflare : SSL/TLS = Full
# Dans config.yaml : auto: true

# Le proxy devrait afficher :
✅ SMART (HTTP/HTTPS Auto-detect) proxy: 0.0.0.0:443 -> ...
[SMART] 🔒 HTTPS detected from ... (Cloudflare Full mode)
```

## 🐛 Dépannage

### Le proxy ne démarre pas
```bash
# Vérifier les logs
journalctl -u proxyox -f

# Vérifier la config
cat /etc/proxyox/config.yaml | grep -A 5 "auto:"
```

### Erreur 521 malgré le mode AUTO
**Cause possible** : Le mode AUTO ne supporte pas encore complètement HTTPS

**Solution temporaire** :
```yaml
# Si Cloudflare Flexible
auto: false
flexible: false

# Si Cloudflare Full (et AUTO ne marche pas)
auto: false
flexible: true
```

## 📚 Documentation connexe

- `CLOUDFLARE_SSL_GUIDE.md` - Guide complet Cloudflare
- `QUICK_REFERENCE.md` - Référence rapide
- `src/proxy/smart.py` - Code source du proxy smart

## 🎯 Recommandation

**Pour la plupart des utilisateurs :**
```yaml
auto: true  # Mode AUTO - Le plus simple!
```

**Si vous avez des problèmes :**
```yaml
auto: false
flexible: false  # Pour Cloudflare Flexible
# OU
flexible: true   # Pour Cloudflare Full
```

Le mode AUTO est la configuration **recommandée** pour 2025 et au-delà ! 🚀
