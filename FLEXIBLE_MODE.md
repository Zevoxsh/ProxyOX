# Configuration SSL/TLS avec Cloudflare

## ⚠️ ATTENTION : Confusion courante !

Le paramètre `flexible` dans ProxyOX ne correspond PAS directement au mode Cloudflare !

### Correspondance correcte :

| Mode Cloudflare | ProxyOX Config | Pourquoi ? |
|----------------|----------------|------------|
| **Flexible** | `flexible: false` | Cloudflare envoie HTTP simple |
| **Full** | `flexible: true` | Cloudflare envoie HTTPS |

## Cloudflare Flexible SSL (Le plus courant)

### Ce que Cloudflare fait :
```
Internet (HTTPS) → Cloudflare (HTTPS) → Votre serveur (HTTP sur port 443)
```

Cloudflare envoie du **HTTP simple** vers votre port 443 !

### Configuration ProxyOX :
```yaml
frontends:
  - name: tcp-fe
    bind: 0.0.0.0:443
    mode: tcp
    default_backend: tcp-server
    flexible: false  # ← HTTP simple accepté sur port 443
```

## Cloudflare Full SSL

### Ce que Cloudflare fait :
```
Internet (HTTPS) → Cloudflare (HTTPS) → Votre serveur (HTTPS sur port 443)
```

Cloudflare envoie du **HTTPS** vers votre port 443 (certificat auto-signé accepté)

### Configuration ProxyOX :
```yaml
frontends:
  - name: tcp-fe
    bind: 0.0.0.0:443
    mode: tcp
    default_backend: tcp-server
    flexible: true  # ← HTTPS accepté avec certificat auto-signé
    # Certificat auto-signé généré automatiquement
```

### Vérification

Pour vérifier que votre configuration fonctionne :

1. **Pour Cloudflare Flexible** (`flexible: false`) :
```bash
# Vous devriez voir
✅ TCP proxy: 0.0.0.0:443 -> 10.10.0.201:8080
```

2. **Pour Cloudflare Full** (`flexible: true`) :
```bash
# Vous devriez voir
✅ FLEXIBLE (HTTP/HTTPS Auto) proxy: 0.0.0.0:443 -> 10.10.0.201:8080
✅ FLEXIBLE PROXY STARTED on 0.0.0.0:443
   - Target: 10.10.0.201:8080
   - Mode: HTTPS (client) -> HTTP (backend)
```

### Dépannage

#### Erreur 521 (Cloudflare)
**Cause :** Mauvaise correspondance entre mode Cloudflare et config ProxyOX

**Solution :**
- Cloudflare en **Flexible** → ProxyOX `flexible: false`
- Cloudflare en **Full** → ProxyOX `flexible: true`

#### "The plain HTTP request was sent to HTTPS port"
**Cause :** Vous avez `flexible: true` mais Cloudflare envoie du HTTP (mode Flexible)

**Solution :**
```yaml
flexible: false  # Cloudflare Flexible envoie HTTP
```

#### "SSL handshake failed"
**Cause :** Vous avez `flexible: false` mais Cloudflare envoie du HTTPS (mode Full)

**Solution :**
```yaml
flexible: true  # Cloudflare Full envoie HTTPS
```

## Résumé

### Pour Cloudflare Flexible SSL :
```yaml
flexible: false  # Accepte HTTP sur port 443
```
Cloudflare envoie du HTTP simple vers votre port 443.

### Pour Cloudflare Full SSL :
```yaml
flexible: true  # Accepte HTTPS sur port 443
```
Cloudflare envoie du HTTPS vers votre port 443 (certificat auto-signé généré automatiquement).

**📖 Voir aussi :** `CLOUDFLARE_SSL_GUIDE.md` pour un guide complet avec tests et dépannage.
