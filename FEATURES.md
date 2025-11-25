# 🚀 ProxyOX - Nouvelles Fonctionnalités

## 📦 Installation et Configuration

### Installation des dépendances

```bash
pip3 install -r requirements.txt
```

Nouvelles dépendances ajoutées :
- `psutil` - Pour les informations système (CPU, mémoire, disque)

### Rendre les scripts exécutables (Linux)

```bash
chmod +x check-config.py
chmod +x check-config.sh
chmod +x proxyox.sh
```

## ✅ Vérification de Configuration

### Méthode 1 : Script Python (recommandé)

```bash
# Vérifier le fichier par défaut (config.yaml)
python3 check-config.py

# Vérifier un fichier spécifique
python3 check-config.py /path/to/config.yaml
```

**Fonctionnalités du checker :**
- ✅ Validation de la syntaxe YAML
- ✅ Vérification de la structure (frontends, backends, global)
- ✅ Validation des références backend
- ✅ Détection des conflits de ports
- ✅ Vérification des fichiers SSL/TLS
- ✅ Validation des formats d'adresses (host:port)
- ⚠️ Warnings pour configurations non-optimales

### Méthode 2 : Script Bash (Linux)

```bash
./check-config.sh
./check-config.sh /path/to/config.yaml
```

### Méthode 3 : Via l'API Web

```bash
curl -u proxyox:changeme http://localhost:8080/api/config/validate | jq
```

## 🎮 Gestion du Service (Linux)

### Script de gestion complet

```bash
# Démarrer le service
./proxyox.sh start

# Arrêter le service
./proxyox.sh stop

# Redémarrer le service
./proxyox.sh restart

# Vérifier le statut
./proxyox.sh status

# Valider la configuration
./proxyox.sh validate

# Voir les logs en temps réel
./proxyox.sh logs

# Aide
./proxyox.sh help
```

## 🌐 Nouvelles API REST

Toutes les API nécessitent l'authentification HTTP Basic (définie dans `.env`).

### 1. **Statistiques en temps réel**

```bash
curl -u proxyox:changeme http://localhost:8080/api/stats | jq
```

Retourne :
- Liste de tous les proxies
- Statistiques par proxy (bytes, connexions, requêtes)
- Uptime de chaque proxy
- Mode maintenance actuel

### 2. **Redémarrer le service** 🔥

```bash
curl -X POST -u proxyox:changeme http://localhost:8080/api/restart
```

**Fonctionnalité principale demandée !** Permet de redémarrer ProxyOX depuis le dashboard web.

### 3. **Recharger la configuration**

```bash
curl -X POST -u proxyox:changeme http://localhost:8080/api/reload-config
```

Valide la configuration sans redémarrer. Pour appliquer, utilisez `/api/restart`.

### 4. **Valider la configuration**

```bash
curl -u proxyox:changeme http://localhost:8080/api/config/validate | jq
```

Retourne :
```json
{
  "status": "success",
  "valid": true,
  "errors": [],
  "warnings": [],
  "message": "Configuration is valid ✅"
}
```

### 5. **Exporter les statistiques en JSON**

```bash
curl -u proxyox:changeme \
  http://localhost:8080/api/export/json \
  -o stats_$(date +%Y%m%d).json
```

Télécharge un fichier JSON avec toutes les statistiques + timestamp.

### 6. **Exporter les statistiques en CSV**

```bash
curl -u proxyox:changeme \
  http://localhost:8080/api/export/csv \
  -o stats_$(date +%Y%m%d).csv
```

Format CSV pour Excel, Google Sheets, etc.

### 7. **Historique des connexions**

```bash
# Dernières 100 connexions
curl -u proxyox:changeme \
  'http://localhost:8080/api/history?limit=100' | jq

# Dernières 500 connexions
curl -u proxyox:changeme \
  'http://localhost:8080/api/history?limit=500' | jq
```

### 8. **Mode Maintenance** 🔧

```bash
# Activer le mode maintenance
curl -X POST -u proxyox:changeme \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}' \
  http://localhost:8080/api/maintenance

# Désactiver le mode maintenance
curl -X POST -u proxyox:changeme \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}' \
  http://localhost:8080/api/maintenance

# Toggle (inverser)
curl -X POST -u proxyox:changeme \
  -H "Content-Type: application/json" \
  -d '{}' \
  http://localhost:8080/api/maintenance
```

### 9. **Informations système** 💻

```bash
curl -u proxyox:changeme http://localhost:8080/api/system/info | jq
```

Retourne :
```json
{
  "system": {
    "platform": "Linux",
    "platform_release": "5.15.0",
    "architecture": "x86_64",
    "hostname": "server01",
    "python_version": "3.10.0"
  },
  "resources": {
    "cpu_percent": 15.3,
    "cpu_count": 8,
    "memory_total": 16777216000,
    "memory_available": 8388608000,
    "memory_percent": 50.0,
    "disk_usage": {
      "total": 500000000000,
      "used": 250000000000,
      "free": 250000000000,
      "percent": 50.0
    }
  }
}
```

### 10. **Contrôle individuel des proxies** 🎛️

```bash
# Arrêter un proxy spécifique
curl -X POST -u proxyox:changeme \
  http://localhost:8080/api/proxy/http-reverse-proxy/stop

# Démarrer un proxy spécifique
curl -X POST -u proxyox:changeme \
  http://localhost:8080/api/proxy/http-reverse-proxy/start
```

## 🎨 Fonctionnalités Sympas et Originales

### 1. **Validation de configuration multi-niveaux**

Le système de validation vérifie :
- ✅ Syntaxe YAML
- ✅ Structure des sections (frontends, backends, global)
- ✅ Références entre frontends et backends
- ✅ Conflits de ports
- ✅ Existence des fichiers SSL/TLS
- ✅ Formats d'adresses
- ✅ Valeurs des paramètres globaux

### 2. **Export multi-format**

- **JSON** : Pour intégration avec d'autres outils, backup, analyse
- **CSV** : Pour Excel, Google Sheets, analyse de données

### 3. **Mode Maintenance**

Marquez votre service en maintenance sans l'arrêter :
- Visible dans le dashboard
- Inclus dans toutes les stats API
- Permet de signaler aux utilisateurs

### 4. **Monitoring système intégré**

Grâce à `psutil`, vous obtenez :
- Usage CPU en temps réel
- Usage mémoire
- Usage disque
- Informations plateforme

### 5. **Contrôle granulaire des proxies**

Start/Stop des proxies individuellement sans redémarrer tout le service !

### 6. **WebSocket temps réel**

Le dashboard se connecte via WebSocket pour :
- Mise à jour automatique chaque seconde
- Pas besoin de rafraîchir la page
- Stats en direct

### 7. **Script de gestion tout-en-un**

`proxyox.sh` offre :
- ✅ Start/Stop/Restart avec validation automatique
- ✅ Affichage du statut détaillé (PID, uptime, CPU, RAM)
- ✅ Logs en temps réel
- ✅ Validation avant démarrage
- ✅ Interface colorée et claire

## 📊 Exemples d'Utilisation

### Automatiser la vérification quotidienne

```bash
# Ajouter à crontab
0 9 * * * /path/to/ProxyOX/check-config.py && echo "Config OK" || echo "Config ERROR!"
```

### Monitoring avec un script

```bash
#!/bin/bash
# monitor.sh - Vérifier le service toutes les 5 minutes

while true; do
    if ! ./proxyox.sh status > /dev/null 2>&1; then
        echo "ProxyOX est down! Redémarrage..."
        ./proxyox.sh start
        
        # Envoyer une alerte
        curl -X POST https://hooks.slack.com/... \
          -d '{"text":"ProxyOX a redémarré automatiquement"}'
    fi
    sleep 300
done
```

### Export automatique des stats

```bash
#!/bin/bash
# backup-stats.sh - Export quotidien des statistiques

DATE=$(date +%Y%m%d)
curl -u proxyox:changeme http://localhost:8080/api/export/json \
  -o "/backups/proxyox_stats_$DATE.json"
  
curl -u proxyox:changeme http://localhost:8080/api/export/csv \
  -o "/backups/proxyox_stats_$DATE.csv"
```

### Intégration avec Prometheus

```bash
# Créer un exporter personnalisé
while true; do
    curl -s -u proxyox:changeme http://localhost:8080/api/stats | \
    jq -r '.proxies[] | "proxyox_bytes_in{proxy=\"\(.name)\"} \(.stats.bytes_received)"' \
    > /var/lib/prometheus/node_exporter/proxyox.prom
    
    sleep 10
done
```

## 🔒 Sécurité

### Changer les identifiants par défaut

Créez ou éditez `.env` :

```bash
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=VotreMo7DeP@sseSecurise
DASHBOARD_HOST=127.0.0.1  # N'écouter que sur localhost
DASHBOARD_PORT=8080
```

### Utiliser HTTPS pour le dashboard

Configurez un reverse proxy (nginx, Apache) devant ProxyOX :

```nginx
server {
    listen 443 ssl;
    server_name dashboard.example.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## 🚀 Démarrage Automatique avec systemd

Créez `/etc/systemd/system/proxyox.service` :

```ini
[Unit]
Description=ProxyOX Reverse Proxy
After=network.target

[Service]
Type=simple
User=proxyox
Group=proxyox
WorkingDirectory=/opt/ProxyOX
ExecStartPre=/usr/bin/python3 /opt/ProxyOX/check-config.py
ExecStart=/usr/bin/python3 /opt/ProxyOX/src/main.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/proxyox/proxyox.log
StandardError=append:/var/log/proxyox/proxyox.log

[Install]
WantedBy=multi-user.target
```

Puis :

```bash
sudo systemctl daemon-reload
sudo systemctl enable proxyox
sudo systemctl start proxyox
sudo systemctl status proxyox
```

## 📚 Résumé des Fonctionnalités

| Fonctionnalité | Description | Commande/API |
|---------------|-------------|--------------|
| 🔍 **Validation Config** | Vérification complète de config.yaml | `python3 check-config.py` |
| 🔄 **Redémarrage Web** | Restart depuis le dashboard | `POST /api/restart` |
| 📊 **Export JSON/CSV** | Export des statistiques | `GET /api/export/{json\|csv}` |
| 🔧 **Mode Maintenance** | Marquer le service en maintenance | `POST /api/maintenance` |
| 💻 **Info Système** | CPU, RAM, Disque en temps réel | `GET /api/system/info` |
| 🎛️ **Contrôle Proxies** | Start/Stop individuel des proxies | `POST /api/proxy/{name}/{start\|stop}` |
| 📜 **Historique** | Historique des connexions | `GET /api/history?limit=N` |
| 🎮 **Script Manager** | Gestion complète du service | `./proxyox.sh {start\|stop\|restart\|status}` |
| 🌊 **WebSocket** | Stats en temps réel | `WS /ws` |
| ✅ **Validation API** | Valider config via API | `GET /api/config/validate` |

## 🐛 Dépannage

### Problème : psutil n'est pas installé

```bash
pip3 install psutil
```

### Problème : Permission denied sur les scripts

```bash
chmod +x check-config.py check-config.sh proxyox.sh
```

### Problème : Le service ne redémarre pas

Vérifiez les logs :
```bash
./proxyox.sh logs
# ou
tail -f proxyox.log
```

### Problème : API retourne 401

Vérifiez vos identifiants dans `.env` :
```bash
cat .env | grep DASHBOARD
```

---

**ProxyOX** - Proxy moderne avec fonctionnalités avancées ! 🚀
