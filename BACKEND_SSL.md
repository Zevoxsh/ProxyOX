# Backend HTTPS Support

## ✅ Solution : Conversion HTTP → HTTPS automatique

ProxyOX convertit maintenant automatiquement les requêtes HTTP en HTTPS vers votre backend !

## Configuration

### Dans `config.yaml` :

```yaml
frontends:
  # Port 80 - Reçoit HTTP, envoie HTTPS
  - name: http-redirect
    bind: 0.0.0.0:80
    mode: http  # ← Mode HTTP
    default_backend: https-server

  # Port 443 - Reçoit HTTP, envoie HTTPS
  - name: tcp-fe
    bind: 0.0.0.0:443
    mode: http  # ← Mode HTTP
    default_backend: https-server

backends:
  - name: https-server
    server: 82.64.136.176:443
    https: true  # ← Le backend utilise HTTPS
```

## Comment ça marche ?

### Flux de données :

```
Cloudflare → ProxyOX (port 80/443) → Backend nginx
   HTTP         HTTP                    HTTPS
             (convertit en HTTPS)    (port 443)
```

### Le proxy HTTP :
1. **Reçoit** une requête HTTP de Cloudflare
2. **Convertit** automatiquement en HTTPS
3. **Envoie** vers le backend avec SSL
4. **Accepte** les certificats auto-signés

## Paramètres

| Paramètre | Emplacement | Description |
|-----------|-------------|-------------|
| `mode: http` | Frontend | Utilise le proxy HTTP (intelligent) |
| `https: true` | Backend | Le backend utilise HTTPS |

## Exemple complet

```yaml
global:
  log-level: info
  timeout: 300
  max-connections: 100

frontends:
  - name: http-80
    bind: 0.0.0.0:80
    mode: http
    default_backend: my-backend

  - name: http-443  
    bind: 0.0.0.0:443
    mode: http
    default_backend: my-backend

backends:
  - name: my-backend
    server: 82.64.136.176:443
    https: true  # Backend en HTTPS
```

## Test

```bash
# Sur le serveur
cd /etc/proxyox
systemctl restart proxyox
journalctl -u proxyox -f
```

**Logs attendus :**
```
✅ HTTP proxy: 0.0.0.0:80 -> 82.64.136.176:443 (HTTPS)
✅ HTTP proxy: 0.0.0.0:443 -> 82.64.136.176:443 (HTTPS)
HTTP proxy started: 0.0.0.0:80 -> 82.64.136.176:443
```

## Avantages

- ✅ Conversion automatique HTTP → HTTPS
- ✅ Accepte les certificats auto-signés
- ✅ Parse correctement les requêtes HTTP
- ✅ Plus d'erreur "plain HTTP request was sent to HTTPS port"
- ✅ Compatible avec Cloudflare Flexible et Full
