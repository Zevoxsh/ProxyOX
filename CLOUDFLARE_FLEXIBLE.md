# Mode Flexible Cloudflare

## Description

Le mode flexible de Cloudflare permet d'avoir :
- **TLS/HTTPS** entre le client et Cloudflare
- **TLS** entre Cloudflare et ProxyOX
- **TCP non chiffré** entre ProxyOX et votre backend

Ce mode est utile quand votre backend ne supporte pas TLS nativement.

## Configuration

Dans `config.yaml`, ajoutez `flexible: true` à votre frontend TCP :

```yaml
frontends:
  - name: tcp-fe
    bind: 0.0.0.0:9000
    mode: tcp
    default_backend: tcp-server
    flexible: true  # Active le mode flexible
    # Optionnel : vos certificats
    certfile: /path/to/cert.pem
    keyfile: /path/to/key.pem
```

### Options

- `flexible: true` - Active le mode flexible (TLS côté client, TCP vers backend)
- `tls: true` - Alternative à `flexible`
- `certfile` - Chemin vers votre certificat TLS (optionnel)
- `keyfile` - Chemin vers votre clé privée (optionnel)

Si `certfile` et `keyfile` ne sont pas spécifiés, un certificat auto-signé sera généré automatiquement.

## Utilisation avec Cloudflare

1. **Configurez votre DNS Cloudflare** pour pointer vers votre serveur ProxyOX
2. **Dans Cloudflare Dashboard** :
   - Allez dans SSL/TLS
   - Sélectionnez le mode **"Flexible"** ou **"Full"**
3. **Dans ProxyOX** :
   - Activez `flexible: true` dans votre frontend
   - ProxyOX acceptera les connexions TLS de Cloudflare
   - ProxyOX transmettra en TCP non chiffré vers votre backend

## Architecture

```
Client (HTTPS)
    ↓
Cloudflare (HTTPS)
    ↓
ProxyOX:9000 (TLS) ← Mode flexible activé
    ↓
Backend:9443 (TCP non chiffré)
```

## Certificats

### Auto-signé (développement)
Si aucun certificat n'est fourni, ProxyOX génère automatiquement un certificat auto-signé.

### Certificats personnalisés (production)
Pour la production, utilisez vos propres certificats :

```yaml
frontends:
  - name: tcp-fe
    bind: 0.0.0.0:9000
    mode: tcp
    default_backend: tcp-server
    flexible: true
    certfile: /etc/ssl/certs/my-cert.pem
    keyfile: /etc/ssl/private/my-key.pem
```

### Certificats Cloudflare Origin
Vous pouvez utiliser les certificats Origin de Cloudflare :

1. Dans Cloudflare Dashboard → SSL/TLS → Origin Server
2. Créez un nouveau certificat Origin
3. Téléchargez le certificat et la clé
4. Configurez les chemins dans `config.yaml`

## Vérification

Pour vérifier que le mode flexible fonctionne :

```bash
# Connexion TLS au proxy
openssl s_client -connect votre-serveur:9000

# Le proxy devrait accepter la connexion TLS
# et transmettre en TCP non chiffré au backend
```

## Dépannage

### Erreur "cryptography module not available"
Installez la dépendance :
```bash
pip install cryptography
```

### Certificat auto-signé rejeté
Pour le développement, vous pouvez désactiver la vérification SSL :
```bash
curl -k https://votre-serveur:9000
```

Pour la production, utilisez des certificats valides (Let's Encrypt ou Cloudflare Origin).
