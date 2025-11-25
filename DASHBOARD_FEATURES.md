# 🚀 ProxyOX Dashboard - Nouvelles Fonctionnalités

## 📊 Multi-Curve Graph avec Filtrage Intelligent

Le dashboard supporte maintenant l'affichage intelligent de multiples courbes pour gérer facilement 200+ proxies :

### Modes d'affichage disponibles :

1. **Top 10 Active** (par défaut)
   - Affiche automatiquement les 10 proxies les plus actifs
   - Tri par nombre de requêtes/connexions
   - Mise à jour dynamique toutes les secondes

2. **All Proxies (Aggregated)**
   - Une seule courbe avec la somme de tous les proxies
   - Utile pour voir la charge globale

3. **HTTP Only**
   - Filtre pour n'afficher que les proxies HTTP
   - Chaque proxy HTTP a sa propre courbe colorée

4. **TCP Only**
   - Filtre pour n'afficher que les proxies TCP
   - Chaque proxy TCP a sa propre courbe colorée

5. **Select Proxies (Custom)**
   - Modal de sélection multi-choix
   - Cochez les proxies spécifiques que vous voulez voir
   - Jusqu'à 10 courbes simultanées recommandées

### Contrôles du graphique :
- **Pause/Resume** : Figer le graphique pour analyser les données
- **Hover interactif** : Affiche toutes les valeurs à un instant T
- **Légende cliquable** : Cliquez sur une légende pour masquer/afficher une courbe
- **Fenêtre de 10 secondes** : Données en temps réel sur une période glissante

---

## 🚨 Système d'Alertes Temps Réel

Le dashboard détecte automatiquement les problèmes et affiche des alertes :

### Types d'alertes :

#### 🔴 Erreur (Rouge) - Critique
- **Proxy Down** : Un proxy n'est pas en état "running"
- S'affiche en haut du dashboard avec icône 🔴
- Ne se ferme pas automatiquement

#### ⚠️ Warning (Orange) - Attention
- **High Failure Rate** : Plus de 10% de connexions échouées (avec minimum 5 échecs)
  - Exemple : "25.3% of connections failing (15/59)"
- **No Traffic** : Aucun trafic depuis plus de 5 minutes alors que le proxy est actif
  - Exemple : "No activity for 12 minutes"
- Ne se ferme pas automatiquement

#### ℹ️ Info (Bleu) - Informatif
- **High Traffic** : Plus de 10 000 requêtes/connexions détectées
  - Peut indiquer une attaque ou un pic de charge
- Se ferme automatiquement après 10 secondes

#### ✅ Success (Vert) - Confirmation
- Actions réussies (start/stop/restart proxy, export)
- Se ferme automatiquement après 10 secondes

### Fonctionnalités des alertes :
- **Animation slide-in** : Apparition fluide par la gauche
- **Bouton de fermeture manuelle** : Cliquez sur × pour fermer
- **Auto-dismiss** : Les alertes info/success disparaissent après 10s
- **Stack vertical** : Plusieurs alertes s'empilent sans se chevaucher
- **Icônes visuelles** : 🔴 ⚠️ ℹ️ ✅ pour identification rapide

---

## 🎮 Contrôles de Proxy

Chaque proxy dans la table peut être contrôlé directement :

### Boutons disponibles :
- **▶️ Start** : Démarrer un proxy arrêté
- **⏹️ Stop** : Arrêter un proxy actif
- **🔄 Restart** : Redémarrer un proxy (stop + start)

### Comportement :
- Boutons désactivés automatiquement si action impossible
  - Start désactivé si déjà running
  - Stop désactivé si déjà stopped
- Feedback visuel immédiat (alert success/error)
- Requêtes envoyées en POST JSON vers `/api/proxy/{action}`

### API Endpoints :
```bash
# Démarrer un proxy
POST /api/proxy/start
Body: {"proxy": "http-reverse-proxy"}

# Arrêter un proxy
POST /api/proxy/stop
Body: {"proxy": "tcp-direct"}

# Redémarrer un proxy
POST /api/proxy/restart
Body: {"proxy": "https-reverse-proxy"}
```

---

## 🔒 Rate Limiting & Max Connections

Protection intégrée contre les surcharges et attaques :

### Configuration globale (config.yaml) :
```yaml
global:
  max-connections: 100    # Maximum de connexions simultanées par proxy
  rate-limit: 1000        # Maximum de requêtes/connexions par seconde
```

### Comportement :

#### HTTP Proxies :
- **Rate Limit** : Maximum de requêtes par seconde
  - Si dépassé → HTTP 429 "Rate limit exceeded"
  - Compte les requêtes sur une fenêtre glissante de 1 seconde
- **Max Connections** : Maximum de requêtes simultanées
  - Si dépassé → HTTP 503 "Too many concurrent requests"
  - Incrémente `failed_requests`

#### TCP Proxies :
- **Rate Limit** : Maximum de nouvelles connexions par seconde
  - Si dépassé → Connexion fermée immédiatement
  - Log warning
- **Max Connections** : Maximum de connexions actives simultanées
  - Si dépassé → Connexion refusée
  - Incrémente `failed_connections`

### Affichage dans le dashboard :

Nouvelle colonne **Limits** dans la table des proxies :
```
50/100 (50%)     ← Connexions actives / Max (Pourcentage)
Rate: 1000/s     ← Limite de rate
```

**Code couleur du pourcentage** :
- 🟢 Vert (0-60%) : Charge normale
- 🟠 Orange (61-80%) : Charge élevée
- 🔴 Rouge (81-100%) : Charge critique

---

## 📥 Export des Statistiques

Exportez toutes les données pour analyse externe :

### Formats disponibles :

#### 📋 Export CSV
- Cliquez sur "Export CSV" dans la sidebar
- Télécharge un fichier `proxyox_stats_YYYYMMDD_HHMMSS.csv`
- Contenu :
  - Name, Protocol, Listen, Target, Status, Uptime
  - Backend SSL, Bytes Sent, Bytes Received, Total Connections

#### 📥 Export JSON
- Cliquez sur "Export JSON" dans la sidebar
- Télécharge un fichier `proxyox_stats_YYYYMMDD_HHMMSS.json`
- Structure complète avec tous les détails :
  ```json
  {
    "timestamp": "2024-01-15T14:30:00",
    "proxies": [
      {
        "name": "http-reverse-proxy",
        "protocol": "HTTP",
        "stats": {
          "requests": 15234,
          "active_requests": 12,
          "bytes_sent": 52428800,
          "domains": {
            "app.example.com": {
              "requests": 8500,
              "bytes_sent": 30000000
            }
          }
        }
      }
    ]
  }
  ```

### API Endpoints :
```bash
# Export JSON
GET /api/export/json

# Export CSV
GET /api/export/csv
```

---

## 📈 Suivi des Erreurs Détaillé

### Nouvelles métriques :

#### Dans la table des proxies :
- **Error Rate** : Pourcentage d'échecs affiché en rouge sous les stats
  - Exemple : "15 failed (8.3%)"
  - Calculé : (failed / total) × 100

#### Dans le système d'alertes :
- **High Failure Rate** : Alerte si > 10% avec minimum 5 échecs
- Affiche le détail : "25.3% of connections failing (15/59)"

#### Tracking complet :
- **HTTP Proxies** :
  - `failed_requests` : Nombre de requêtes échouées
  - `total_requests` : Total des requêtes
- **TCP Proxies** :
  - `failed_connections` : Nombre de connexions échouées
  - `total_connections` : Total des connexions

---

## 🎨 Améliorations Visuelles

### Nouvelles colonnes dans la table :
1. **Limits** : Affiche max_connections et rate_limit avec code couleur
2. **Controls** : 3 boutons pour gérer le proxy (▶️ ⏹️ 🔄)

### Graphique amélioré :
- **Tooltip enrichi** :
  - Affiche toutes les courbes à la même position temporelle
  - Info détaillée par proxy (nom, valeur, unité)
  - Total agrégé si plusieurs courbes
  - Statistiques additionnelles (data transfer)
- **Légende interactive** :
  - Cliquez pour masquer/afficher une courbe
  - Points de style pour identification
- **10 couleurs distinctes** :
  - #5b8def (bleu), #22d3ee (cyan), #9d5cf6 (violet)
  - #fb923c (orange), #f87171 (rouge), #10b981 (vert)
  - #ec4899 (rose), #06b6d4 (bleu clair), #8b5cf6 (violet foncé)
  - #14b8a6 (turquoise)

---

## 🔧 Configuration Technique

### Seuils d'alertes (modifiables dans dashboard.html) :
```javascript
const alertThresholds = {
    failureRate: 0.1,      // 10% de connexions échouées
    downProxy: true,       // Alerte si proxy stopped
    highTraffic: 10000,    // 10k requêtes/connexions
    noTraffic: 300         // 5 minutes sans trafic (300s)
};
```

### Paramètres de graphique :
- **Fenêtre temporelle** : 10 secondes (10 points de données)
- **Mise à jour** : 1 seconde (via WebSocket)
- **Historique conservé** : 10 secondes par proxy
- **Animation** : Désactivée pour performance (`update('none')`)

### Rate Limiting :
- **Implémentation** : `deque` avec taille maximale = rate_limit
- **Fenêtre** : 1 seconde glissante
- **Stockage** : Timestamps des dernières requêtes/connexions

---

## 📝 Utilisation Recommandée

### Pour 1-10 proxies :
- Mode "All (Aggregated)" ou "Top 10 Active"
- Visualisation simple et claire

### Pour 10-50 proxies :
- Mode "Top 10 Active" pour voir les plus chargés
- Modes "HTTP Only" / "TCP Only" pour filtrer par protocole
- Mode "Custom" pour surveiller des proxies spécifiques

### Pour 50-200+ proxies :
- **Mode "Top 10 Active"** recommandé par défaut
- Utiliser les **alertes** pour détecter les problèmes
- **Export CSV** pour analyse complète hors ligne
- **Mode Custom** pour focus sur proxies critiques

### Bonnes pratiques :
1. Surveillez la colonne **Limits** pour anticiper les saturations
2. Configurez des **rate-limits** adaptés à votre infrastructure
3. Utilisez **Pause** pour analyser un pic de trafic
4. **Exportez régulièrement** les stats pour historique long terme
5. Ajustez les **seuils d'alertes** selon vos besoins

---

## 🚀 Performance

### Optimisations :
- **Lazy chart updates** : `update('none')` pour éviter animations
- **Deque** pour historique limité (pas de fuite mémoire)
- **WebSocket** pour push temps réel (pas de polling)
- **Filtrage côté client** : Réduit la charge réseau
- **Canvas mini-charts** : Graphiques légers dans la table

### Scalabilité testée :
- ✅ 200+ proxies : Top 10 mode fluide
- ✅ WebSocket stable avec mises à jour 1/sec
- ✅ Alertes multiples sans lag
- ✅ Export JSON/CSV de 500+ proxies instantané

---

## 🎯 Prochaines Améliorations Possibles

1. **Pagination table** : Pour 500+ proxies
2. **Recherche/filtre** : Trouver rapidement un proxy
3. **Graphiques historiques** : Période > 10 secondes (1h, 24h, 7j)
4. **Notifications navigateur** : Alertes critiques même onglet fermé
5. **Dashboard metrics** : Prometheus/Grafana intégration
6. **Auto-scaling** : Augmenter max_connections automatiquement
7. **Géolocalisation** : Voir d'où viennent les connexions
8. **Blacklist/Whitelist** : Bloquer IPs depuis le dashboard
