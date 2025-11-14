# Mode Flexible - Auto-détection HTTP/HTTPS

## Comment ça fonctionne

Le proxy ProxyOX supporte maintenant le **mode flexible** qui permet de gérer automatiquement les connexions HTTPS de Cloudflare en mode Flexible SSL.

### Configuration

Dans `config.yaml`, activez le mode flexible :

```yaml
frontends:
  - name: tcp-fe
    bind: 0.0.0.0:443
    mode: tcp
    default_backend: tcp-server
    flexible: true  # ← Active le mode flexible
```

### Comportement

Quand `flexible: true` est activé :

1. **Le proxy démarre avec SSL activé sur le port 443**
   - Un certificat auto-signé est généré automatiquement
   - Ou vous pouvez fournir vos propres certificats avec `certfile` et `keyfile`

2. **Les connexions HTTPS sont acceptées**
   - Le proxy déchiffre automatiquement les connexions HTTPS
   - Parfait pour Cloudflare qui envoie du HTTPS même en mode Flexible

3. **Les données sont transmises en HTTP simple au backend**
   - Le proxy envoie les données déchiffrées en HTTP au backend
   - Pas besoin de SSL sur votre application backend

### Modes Cloudflare supportés

#### ✅ Cloudflare Flexible SSL (Recommandé)
```
Internet (HTTPS) → Cloudflare (HTTPS) → ProxyOX (HTTPS→HTTP) → Backend (HTTP)
```
- Cloudflare gère le certificat SSL pour vos visiteurs
- ProxyOX accepte HTTPS de Cloudflare (avec certificat auto-signé)
- Votre backend reçoit du HTTP simple

#### ✅ Cloudflare Full SSL
```
Internet (HTTPS) → Cloudflare (HTTPS) → ProxyOX (HTTPS→HTTP) → Backend (HTTP)
```
- Identique au mode Flexible côté ProxyOX
- La seule différence est que Cloudflare vérifie le certificat (accepte les auto-signés)

#### ❌ Cloudflare Off (HTTP simple)
```
Internet (HTTP) → Cloudflare (HTTP) → ProxyOX ??? → Backend
```
- Non supporté avec `flexible: true`
- Pour HTTP pur, utilisez `flexible: false` et `tls: false`

### Exemple de configuration complète

```yaml
frontends:
  # Mode Flexible - HTTPS vers HTTP
  - name: https-flexible
    bind: 0.0.0.0:443
    mode: tcp
    default_backend: backend-http
    flexible: true
    # Optionnel : certificats personnalisés
    # certfile: /path/to/cert.pem
    # keyfile: /path/to/key.pem

backends:
  - name: backend-http
    server: 10.10.0.201:8080  # Backend en HTTP simple
```

### Vérification

Pour vérifier que le mode flexible fonctionne :

1. Démarrez ProxyOX :
```bash
python src/main.py
```

2. Vous devriez voir dans les logs :
```
✅ FLEXIBLE (HTTP/HTTPS Auto) proxy: 0.0.0.0:443 -> 10.10.0.201:8080
✅ FLEXIBLE PROXY STARTED on 0.0.0.0:443
   - Target: 10.10.0.201:8080
   - Mode: HTTPS (client) -> HTTP (backend)
   - Perfect for Cloudflare Flexible SSL
```

3. Testez avec curl depuis Cloudflare ou avec SSL :
```bash
# Ceci devrait fonctionner (HTTPS vers le proxy)
curl -k https://votre-domaine.com

# Le proxy transmet en HTTP au backend
```

### Dépannage

#### "The plain HTTP request was sent to HTTPS port"
- ✅ Ce problème est résolu avec le mode flexible !
- Le proxy accepte maintenant HTTPS et transmet en HTTP

#### "SSL handshake failed"
- Vérifiez que le certificat est bien généré
- Cloudflare accepte les certificats auto-signés en mode Flexible/Full

#### "Connection refused"
- Vérifiez que votre backend écoute bien en HTTP
- Vérifiez l'adresse IP et le port du backend dans `config.yaml`

### Statistiques

Le dashboard affiche maintenant :
- **Protocol**: `FLEXIBLE (HTTP/HTTPS Auto-detect)`
- **HTTPS connections**: Nombre de connexions HTTPS reçues
- **HTTP connections**: Nombre de connexions HTTP (si supporté)
- **Mode**: `HTTPS->HTTP` pour chaque connexion

## Résumé

Le mode `flexible: true` résout le problème "plain HTTP request was sent to HTTPS port" en :
1. Acceptant les connexions HTTPS sur le port 443
2. Déchiffrant automatiquement avec SSL
3. Transmettant les données en HTTP simple au backend

C'est la configuration parfaite pour Cloudflare Flexible SSL ! 🎉
