# Guide de Configuration Cloudflare SSL/TLS

## ⚠️ IMPORTANT : Correspondance des modes

### 🔥 Nouveau : Mode AUTO (Recommandé!)

Le proxy peut maintenant **détecter automatiquement** si Cloudflare envoie HTTP ou HTTPS !

```yaml
frontends:
  - bind: 0.0.0.0:443
    mode: tcp
    auto: true  # ← Détection automatique
```

Avec `auto: true`, le proxy fonctionne automatiquement avec:
- ✅ Cloudflare Flexible (HTTP)
- ✅ Cloudflare Full (HTTPS)
- ✅ Sans changement de configuration!

### Mode Manuel (si vous préférez)

| Mode Cloudflare | Cloudflare → ProxyOX | Config ProxyOX | ProxyOX → Backend |
|----------------|---------------------|----------------|-------------------|
| **Off** | HTTP (port 80) | N/A | HTTP |
| **Flexible** | HTTP (port 443!) | `flexible: false` | HTTP |
| **Full** | HTTPS (port 443) | `flexible: true` | HTTP |
| **Full (strict)** | HTTPS (port 443) | `flexible: true` + certificat valide | HTTP |

## 📝 Explication détaillée

### 🔥 Mode AUTO (Recommandé) - Nouveau!
```
Visiteur → Cloudflare → ProxyOX → Backend
HTTPS     HTTP/HTTPS   HTTP      HTTP
                    (détection auto!)
```
**Config ProxyOX :**
```yaml
frontends:
  - bind: 0.0.0.0:443
    mode: tcp
    auto: true  # ← Le proxy détecte automatiquement HTTP ou HTTPS
```
**Pourquoi ?** Le proxy lit le premier octet de la connexion:
- Si c'est `0x16` (TLS handshake) → Mode Full détecté → Traite comme HTTPS
- Si c'est des lettres ASCII (`GET`, `POST`) → Mode Flexible détecté → Traite comme HTTP

**Avantages :**
- ✅ Pas besoin de connaître le mode Cloudflare
- ✅ Fonctionne automatiquement si vous changez de mode
- ✅ Un seul fichier de configuration pour tous les modes

### Cloudflare SSL/TLS : Off
```
Visiteur → Cloudflare → ProxyOX
HTTP      HTTP         HTTP (port 80)
```
**Config ProxyOX :**
```yaml
frontends:
  - bind: 0.0.0.0:80
    mode: tcp
    flexible: false
```

### Cloudflare SSL/TLS : Flexible ⭐ (Le plus courant)
```
Visiteur → Cloudflare → ProxyOX → Backend
HTTPS     HTTP         HTTP      HTTP
                    (port 443!)
```
**Config ProxyOX :**
```yaml
frontends:
  - bind: 0.0.0.0:443
    mode: tcp
    flexible: false  # ← PAS de SSL côté serveur
```
**Pourquoi ?** Cloudflare chiffre uniquement entre le visiteur et Cloudflare. Entre Cloudflare et votre serveur, c'est du HTTP simple (même sur le port 443).

### Cloudflare SSL/TLS : Full
```
Visiteur → Cloudflare → ProxyOX → Backend
HTTPS     HTTPS        HTTP      HTTP
                    (port 443)
```
**Config ProxyOX :**
```yaml
frontends:
  - bind: 0.0.0.0:443
    mode: tcp
    flexible: true  # ← Active SSL côté serveur (certificat auto-signé OK)
```
**Pourquoi ?** Cloudflare chiffre jusqu'à votre serveur. Le certificat auto-signé est accepté.

### Cloudflare SSL/TLS : Full (strict)
```
Visiteur → Cloudflare → ProxyOX → Backend
HTTPS     HTTPS        HTTP      HTTP
                    (port 443)
```
**Config ProxyOX :**
```yaml
frontends:
  - bind: 0.0.0.0:443
    mode: tcp
    flexible: true
    certfile: /path/to/valid-cert.pem  # Certificat valide requis
    keyfile: /path/to/valid-key.pem
```
**Pourquoi ?** Comme Full, mais Cloudflare vérifie que le certificat est valide (pas auto-signé).

## 🔧 Configuration rapide

### Mode AUTO (Le plus simple) ⭐
**Pour n'importe quel mode Cloudflare :**
```yaml
frontends:
  - bind: 0.0.0.0:443
    mode: tcp
    auto: true  # ← Fonctionne avec Flexible ET Full
```
Pas besoin de savoir quel mode Cloudflare vous utilisez !

### Je suis en Cloudflare Flexible → Erreur 521
**Problème :** `flexible: true` essaie d'accepter HTTPS, mais Cloudflare envoie du HTTP

**Solution :**
```yaml
frontends:
  - bind: 0.0.0.0:443
    mode: tcp
    flexible: false  # ← Changez à false
```

### Je suis en Cloudflare Full → Erreur "plain HTTP request"
**Problème :** `flexible: false` attend du HTTP, mais Cloudflare envoie du HTTPS

**Solution :**
```yaml
frontends:
  - bind: 0.0.0.0:443
    mode: tcp
    flexible: true  # ← Changez à true
```

## 🧪 Test de votre configuration

### 1. Vérifier ce que Cloudflare envoie
```bash
# Sur votre serveur ProxyOX
tcpdump -i any -n port 443 -A | head -20
```
- Si vous voyez `GET / HTTP/1.1` en clair → Cloudflare envoie HTTP → `flexible: false`
- Si vous voyez des données binaires/chiffrées → Cloudflare envoie HTTPS → `flexible: true`

### 2. Vérifier les logs ProxyOX
```bash
journalctl -u proxyox -f
```
- `plain HTTP request was sent to HTTPS port` → Vous avez `flexible: true` mais Cloudflare est en mode Flexible → Mettez `flexible: false`
- `SSL handshake failed` → Vous avez `flexible: false` mais Cloudflare est en mode Full → Mettez `flexible: true`

## 📊 Récapitulatif simple

### Option 1 : Mode AUTO (Recommandé) 🌟
```yaml
auto: true  # Fonctionne avec Flexible ET Full automatiquement
```

### Option 2 : Mode Manuel
**Règle d'or :**
- Cloudflare **Flexible** = ProxyOX `flexible: false` (HTTP sur port 443)
- Cloudflare **Full** = ProxyOX `flexible: true` (HTTPS sur port 443)

**C'est contre-intuitif, mais c'est la logique !**

### Quel mode choisir ?
- 🥇 **Mode AUTO** : Vous ne voulez pas vous soucier du mode Cloudflare → `auto: true`
- 🥈 **Mode Manuel** : Vous savez exactement quel mode vous utilisez → `flexible: true/false`
