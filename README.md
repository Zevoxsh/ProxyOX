# ProxyOX 🚀

**ProxyOX** est un serveur proxy asynchrone haute performance avec support du **reverse proxy** basé sur les noms de domaine, monitoring en temps réel et dashboard web intégré.

## ✨ Fonctionnalités

- **🔄 Reverse Proxy Intelligent** : Routage HTTP/HTTPS par nom de domaine (SNI)
- **🌐 Multi-Protocole** : TCP, UDP, et HTTP/HTTPS
- **⚡ Haute Performance** : Architecture asynchrone avec Python asyncio
- **📊 Dashboard Web** : Interface de monitoring temps réel avec graphiques
- **🔒 Sécurisé** : Authentification HTTP Basic Auth pour le dashboard
- **⚙️ Configuration Flexible** : Format YAML simple avec séparation frontend/backend
- **📈 Statistiques Détaillées** : Connexions, requêtes, bande passante, latence
- **🔐 Support SSL/TLS** : Chiffrement backend pour proxies TCP
- **📝 Logs Détaillés** : Suivi complet des requêtes et des routes

---

## 🚀 Installation Rapide

### Installation en Une Commande

```bash
wget -qO- https://raw.githubusercontent.com/Zevoxsh/ProxyOX/main/install.sh | sudo bash
```

**Ou avec curl :**

```bash
curl -fsSL https://raw.githubusercontent.com/Zevoxsh/ProxyOX/main/install.sh | sudo bash
```

Cette commande va :
- ✅ Cloner le repository
- ✅ Installer les dépendances Python
- ✅ Configurer le service systemd
- ✅ Créer les fichiers de configuration
- ✅ Démarrer ProxyOX automatiquement

### Installation Manuelle

```bash
# 1. Cloner le repository
git clone https://github.com/Zevoxsh/ProxyOX.git /opt/proxyox
cd /opt/proxyox

# 2. Lancer le script d'installation
sudo bash install.sh
```

---

## ⚙️ Configuration

### 📁 Structure de Configuration

ProxyOX utilise un modèle **frontend/backend** :
- **Frontends** : Définissent les interfaces d'écoute (ports, protocoles)
- **Backends** : Définissent les serveurs cibles

Fichier de configuration : `/etc/proxyox/config.yaml`

### 🌐 Reverse Proxy par Nom de Domaine

Configuration d'un reverse proxy HTTP avec routage intelligent :

```yaml
global:
  log-level: info
  use-uvloop: false
  timeout: 300
  max-connections: 100

frontends:
  # Port 80 - Reverse proxy HTTP
  - name: http-reverse-proxy
    bind: 0.0.0.0:80
    mode: http
    domain_routes:
      - domain: app.example.com
        backend: app-server
      - domain: api.example.com
        backend: api-server
      - domain: blog.example.com
        backend: blog-server
    # Backend par défaut si domaine non trouvé
    default_backend: default-web

  # Port 443 - Reverse proxy HTTPS
  - name: https-reverse-proxy
    bind: 0.0.0.0:443
    mode: http
    domain_routes:
      - domain: app.example.com
        backend: app-server-https
      - domain: api.example.com
        backend: api-server-https
    default_backend: default-web-https

backends:
  - name: app-server
    server: 192.168.1.10:80
    https: false

  - name: api-server
    server: 192.168.1.20:8080
    https: false

  - name: blog-server
    server: 192.168.1.30:3000
    https: false

  - name: app-server-https
    server: 192.168.1.10:443
    https: true

  - name: api-server-https
    server: 192.168.1.20:8443
    https: true

  - name: default-web
    server: 192.168.1.100:80
    https: false

  - name: default-web-https
    server: 192.168.1.100:443
    https: true
```

### 🔧 Configuration DNS

Pour utiliser le reverse proxy, configurez vos enregistrements DNS :

```dns
# Zone DNS : example.com
app.example.com     A    IP_DU_PROXY
api.example.com     A    IP_DU_PROXY
blog.example.com    A    IP_DU_PROXY
```

**Exemple avec DNS local** (`/etc/hosts` ou équivalent) :

```
192.168.1.5    app.example.com
192.168.1.5    api.example.com
192.168.1.5    blog.example.com
```

### 🔌 Modes de Protocole

#### 🌐 Mode HTTP (Reverse Proxy)

Idéal pour router le trafic HTTP/HTTPS par nom de domaine :

```yaml
frontends:
  - name: web-proxy
    bind: 0.0.0.0:80
    mode: http
    domain_routes:
      - domain: site1.local
        backend: server1
      - domain: site2.local
        backend: server2
    default_backend: default-server
```

**Fonctionnalités** :
- ✅ Routage par header `Host`
- ✅ Support des domaines et sous-domaines
- ✅ Gestion automatique des headers HTTP
- ✅ Statistiques par requête (latence, méthodes HTTP)

#### 🔌 Mode TCP

Proxy TCP générique pour tout type de trafic :

```yaml
frontends:
  - name: tcp-proxy
    bind: 0.0.0.0:443
    mode: tcp
    default_backend: https-server
    backend_ssl: false  # Passthrough simple
```

**Options** :
- `backend_ssl: true` : Chiffre la connexion vers le backend
- `backend_ssl: false` : Mode passthrough (pas de modification)

#### 📡 Mode UDP

Proxy UDP pour DNS, gaming, VoIP, etc. :

```yaml
frontends:
  - name: udp-proxy
    bind: 0.0.0.0:53
    mode: udp
    default_backend: dns-server

backends:
  - name: dns-server
    server: 8.8.8.8:53
```

---

## 🎯 Exemples de Configuration

### Exemple 1 : Hébergement Multi-Sites

```yaml
frontends:
  - name: multi-site-http
    bind: 0.0.0.0:80
    mode: http
    domain_routes:
      - domain: wordpress.local
        backend: wordpress
      - domain: nextcloud.local
        backend: nextcloud
      - domain: grafana.local
        backend: grafana
    default_backend: wordpress

backends:
  - name: wordpress
    server: 192.168.1.10:80
    https: false
  
  - name: nextcloud
    server: 192.168.1.20:80
    https: false
  
  - name: grafana
    server: 192.168.1.30:3000
    https: false
```

### Exemple 2 : Proxy avec Accès Direct

```yaml
frontends:
  # Reverse proxy sur port 80
  - name: http-reverse
    bind: 0.0.0.0:80
    mode: http
    domain_routes:
      - domain: app.local
        backend: app-server
    default_backend: app-server

  # Accès direct TCP sur port alternatif
  - name: direct-access
    bind: 0.0.0.0:8080
    mode: tcp
    default_backend: app-server

backends:
  - name: app-server
    server: 192.168.1.50:80
```

### Exemple 3 : Load Balancing Simple

Créez plusieurs frontends pointant vers différents backends :

```yaml
frontends:
  - name: lb-web1
    bind: 0.0.0.0:8081
    mode: http
    default_backend: web-server-1

  - name: lb-web2
    bind: 0.0.0.0:8082
    mode: http
    default_backend: web-server-2

backends:
  - name: web-server-1
    server: 192.168.1.10:80
  
  - name: web-server-2
    server: 192.168.1.11:80
```

---

## 📊 Dashboard et Monitoring

### Accès au Dashboard

Par défaut : `http://IP_SERVEUR:8090`

**Identifiants** (définis dans `.env`) :
```env
DASHBOARD_USER=admin
DASHBOARD_PASS=votre_mot_de_passe
```

### Changer le Port du Dashboard

```bash
# Éditer le fichier .env
nano /opt/proxyox/.env

# Modifier
DASHBOARD_PORT=8090  # Changez ce port
```

### Statistiques Disponibles

- **Proxies actifs** : Liste de tous les proxies en cours
- **Connexions** : Totales, actives, pic
- **Bande passante** : Entrée/Sortie en temps réel
- **Latence** : Temps de réponse moyen (mode HTTP)
- **Requêtes** : Total, succès, erreurs
- **Graphiques temps réel** : Trafic, connexions, requêtes

---

## 🛠️ Gestion du Service

### Commandes Systemd

```bash
# Démarrer ProxyOX
sudo systemctl start proxyox

# Arrêter ProxyOX
sudo systemctl stop proxyox

# Redémarrer ProxyOX
sudo systemctl restart proxyox

# Voir le statut
sudo systemctl status proxyox

# Activer au démarrage
sudo systemctl enable proxyox

# Désactiver au démarrage
sudo systemctl disable proxyox
```

### Logs et Débogage

```bash
# Voir les logs en temps réel
sudo journalctl -u proxyox -f

# Voir les 100 dernières lignes
sudo journalctl -u proxyox -n 100

# Logs depuis aujourd'hui
sudo journalctl -u proxyox --since today
```

### Recharger la Configuration

```bash
# Éditer la config
sudo nano /etc/proxyox/config.yaml

# Redémarrer pour appliquer
sudo systemctl restart proxyox
```

---

## 🔧 Dépannage

### Le reverse proxy ne route pas correctement

**Vérifiez les logs** :
```bash
journalctl -u proxyox -f
```

Vous devriez voir :
```
INFO:http_proxy:[HTTP] Request from example.com - Available routes: ['app.example.com', 'api.example.com']
INFO:http_proxy:Routing example.com to 192.168.1.10:80 (HTTPS: False)
```

**Problème de domaine** : Si vous voyez `Available routes: None`, vérifiez que `domain_routes` est bien configuré dans `config.yaml`.

### Erreur "Domaine non approuvé" (NextCloud, etc.)

Certaines applications vérifient le header `Host`. Ajoutez le domaine dans leur configuration :

**NextCloud** :
```bash
nano /var/www/nextcloud/config/config.php
```

```php
'trusted_domains' => array (
  0 => 'localhost',
  1 => 'nextcloud.example.com',  // Ajoutez ici
),
```

### Erreur de décodage (ERR_CONTENT_DECODING_FAILED)

ProxyOX désactive automatiquement la compression. Si l'erreur persiste, vérifiez que vous utilisez la dernière version :

```bash
cd /opt/proxyox
git pull origin main
sudo systemctl restart proxyox
```

---

## 🔄 Mise à Jour

```bash
# Aller dans le répertoire
cd /opt/proxyox

# Sauvegarder la config actuelle
sudo cp /etc/proxyox/config.yaml /etc/proxyox/config.yaml.backup

# Mettre à jour depuis GitHub
sudo git pull origin main

# Redémarrer le service
sudo systemctl restart proxyox
```

---

## 🗑️ Désinstallation

```bash
cd /opt/proxyox
sudo bash uninstall.sh
```

---

## 📚 Documentation Technique

### Architecture

```
Client → Frontend (Port d'écoute) → Reverse Proxy → Backend (Serveur cible)
```

### Flux de Requête HTTP

1. Client fait une requête vers `app.example.com`
2. ProxyOX reçoit la requête sur le port 80
3. Extraction du header `Host: app.example.com`
4. Recherche dans `domain_routes`
5. Route trouvée → Redirige vers le backend configuré
6. Réponse renvoyée au client

### Gestion des Headers

ProxyOX filtre automatiquement les headers problématiques :
- ✅ `Transfer-Encoding` : Géré automatiquement
- ✅ `Content-Length` : Recalculé automatiquement
- ✅ `Connection` : Forcé à `close`
- ✅ `Accept-Encoding` : Forcé à `identity` (désactive compression)

---
