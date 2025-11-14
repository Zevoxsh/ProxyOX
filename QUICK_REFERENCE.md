# Quick Reference - Cloudflare + ProxyOX

## 🚀 Configuration rapide

### 🔥 Mode AUTO (Recommandé!)
```yaml
frontends:
  - bind: 0.0.0.0:443
    mode: tcp
    auto: true  # ← Fonctionne avec TOUS les modes Cloudflare!
```
**Fonctionne automatiquement avec:**
- ✅ Cloudflare Flexible
- ✅ Cloudflare Full
- ✅ Cloudflare Full (strict)

Aucune configuration manuelle nécessaire!

### Vous préférez le mode manuel ?

#### Vous utilisez Cloudflare Flexible ?
```yaml
frontends:
  - bind: 0.0.0.0:443
    mode: tcp
    auto: false
    flexible: false  # ← HTTP accepté
```

#### Vous utilisez Cloudflare Full ?
```yaml
frontends:
  - bind: 0.0.0.0:443
    mode: tcp
    auto: false
    flexible: true   # ← HTTPS accepté
```

## 🔍 Comment savoir quel mode utiliser ?

### Vérifier dans Cloudflare Dashboard :
1. Allez dans **SSL/TLS** → **Overview**
2. Regardez le mode actif :
   - **Flexible** → ProxyOX `flexible: false`
   - **Full** → ProxyOX `flexible: true`
   - **Full (strict)** → ProxyOX `flexible: true` + certificat valide

## 🐛 Erreurs communes

| Erreur | Cause | Solution |
|--------|-------|----------|
| **Error 521** | Mauvaise config | Vérifier mode Cloudflare vs ProxyOX |
| **plain HTTP to HTTPS port** | `flexible: true` + Cloudflare Flexible | Mettre `flexible: false` |
| **SSL handshake failed** | `flexible: false` + Cloudflare Full | Mettre `flexible: true` |

## 📝 Après changement de config

```bash
# Sur le serveur
cd /etc/proxyox
nano config.yaml  # Modifier flexible: true/false
systemctl restart proxyox
journalctl -u proxyox -f  # Vérifier les logs
```

## 📚 Documentation complète

- `CLOUDFLARE_SSL_GUIDE.md` - Guide complet avec tests
- `FLEXIBLE_MODE.md` - Détails techniques
