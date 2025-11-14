# Backend SSL Support

## Problème résolu

Votre backend nginx écoute en **HTTPS** (port 9443), mais ProxyOX lui envoyait du **HTTP**.

**Erreur avant :**
```
400 Bad Request
The plain HTTP request was sent to HTTPS port
```

## Solution

Ajoutez `backend_ssl: true` dans votre configuration pour que ProxyOX se connecte en HTTPS au backend.

## Configuration

```yaml
frontends:
  - name: tcp-fe
    bind: 0.0.0.0:443
    mode: tcp
    default_backend: tcp-server
    backend_ssl: true  # ← Active la connexion HTTPS vers le backend

backends:
  - name: tcp-server
    server: 10.10.0.201:9443  # Backend en HTTPS
```

## Flux complet

### Cloudflare Flexible + Backend HTTPS
```
Visiteur → Cloudflare → ProxyOX → Backend
HTTPS     HTTP         HTTPS     HTTPS
        (port 80/443) (SSL!)   (port 9443)
```

**Configuration:**
```yaml
frontends:
  - bind: 0.0.0.0:443
    mode: tcp
    backend_ssl: true  # ← ProxyOX → Backend en HTTPS
```

### Cloudflare Full + Backend HTTPS
```
Visiteur → Cloudflare → ProxyOX → Backend
HTTPS     HTTPS        HTTPS     HTTPS
                    (décrypte et re-crypte)
```

**Pas encore supporté** - utilisez Cloudflare Flexible pour l'instant.

## Test

```bash
# Sur votre serveur
cd /etc/proxyox
systemctl restart proxyox
journalctl -u proxyox -f
```

**Logs attendus :**
```
✅ TCP proxy: 0.0.0.0:80 -> 10.10.0.201:9443 (HTTPS)
✅ TCP proxy: 0.0.0.0:443 -> 10.10.0.201:9443 (HTTPS)
[TCP] Connecting with SSL to backend
[TCP] Connected to upstream 10.10.0.201:9443 (SSL)
```

## Paramètres

| Paramètre | Description | Valeur |
|-----------|-------------|--------|
| `backend_ssl` | Connexion SSL vers le backend | `true` / `false` |
| `tls` | Écoute en SSL côté client (pas utilisé avec Cloudflare) | `true` / `false` |

**Note :** Les certificats auto-signés du backend sont acceptés automatiquement.
