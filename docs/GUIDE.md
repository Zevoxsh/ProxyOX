# ProxyOX - Migration vers MySQL

## 🎯 Objectif

Ce guide vous permet de migrer ProxyOX de SQLite vers MySQL pour une utilisation en production.

## 📋 Prérequis

- Windows 10/11
- Python 3.8+ installé
- PowerShell
- Droits administrateur (pour installer MySQL)

## 🚀 Installation Rapide

### Méthode 1 : Installation Automatique (Recommandée)

```powershell
# 1. Ouvrir PowerShell en tant qu'administrateur
# Clic droit sur PowerShell > "Exécuter en tant qu'administrateur"

# 2. Naviguer vers le dossier ProxyOX
cd C:\Users\antoi\Documents\ProxyOX-1

# 3. Installer MySQL automatiquement
python install_mysql.py

# 4. Configurer la base de données ProxyOX
python setup_mysql.py

# 5. Migrer les données de SQLite vers MySQL
python migrate_to_mysql.py

# 6. Démarrer ProxyOX
python src/main.py
```

### Méthode 2 : Installation Manuelle

Si l'installation automatique échoue, suivez le guide détaillé : **[MYSQL_SETUP.md](MYSQL_SETUP.md)**

## 📁 Structure des Fichiers

```
ProxyOX-1/
├── src/
│   ├── database/
│   │   ├── db_manager.py          # SQLite (ancien)
│   │   ├── mysql_manager.py       # MySQL (nouveau) ✨
│   │   └── models.py
│   ├── dashboard/
│   │   └── app.py                 # Mis à jour pour MySQL ✨
│   └── main.py                    # Mis à jour pour MySQL ✨
├── .env                           # Configuration MySQL ✨
├── install_mysql.py               # Installateur automatique ✨
├── setup_mysql.py                 # Configuration DB ✨
├── migrate_to_mysql.py            # Migration SQLite → MySQL ✨
├── MYSQL_SETUP.md                 # Guide d'installation détaillé ✨
└── README_MYSQL.md                # Ce fichier ✨
```

## ⚙️ Configuration

### Fichier `.env`

Les paramètres de connexion MySQL sont dans le fichier `.env` :

```env
# MySQL Configuration
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=proxyox
MYSQL_PASSWORD=proxyox
MYSQL_DATABASE=proxyox
```

Pour modifier ces paramètres :
1. Éditez `.env`
2. Recréez l'utilisateur MySQL si nécessaire
3. Redémarrez ProxyOX

## 🔧 Scripts Disponibles

### 1. `install_mysql.py` - Installation Automatique

Installe MySQL via Chocolatey (gestionnaire de paquets Windows).

**Usage :**
```powershell
# PowerShell en tant qu'administrateur
python install_mysql.py
```

**Ce script :**
- ✅ Vérifie les droits administrateur
- ✅ Installe Chocolatey si nécessaire
- ✅ Installe MySQL Server 8.0
- ✅ Démarre le service MySQL

### 2. `setup_mysql.py` - Configuration de la Base

Crée la base de données et l'utilisateur ProxyOX.

**Usage :**
```powershell
python setup_mysql.py
```

**Vous devrez fournir :**
- Nom d'utilisateur root MySQL (par défaut : `root`)
- Mot de passe root MySQL

**Ce script :**
- ✅ Crée la base `proxyox`
- ✅ Crée l'utilisateur `proxyox` avec mot de passe `proxyox`
- ✅ Accorde les privilèges nécessaires

### 3. `migrate_to_mysql.py` - Migration des Données

Migre toutes les données de SQLite vers MySQL.

**Usage :**
```powershell
python migrate_to_mysql.py
```

**Ce script migre :**
- ✅ Utilisateurs (admin)
- ✅ Proxies (HTTP, HTTPS, TCP)
- ✅ Backends (serveurs cibles)
- ✅ Routes de domaine
- ✅ Filtres IP
- ✅ Paramètres globaux

## 🎮 Utilisation

### Démarrer ProxyOX

```powershell
python src/main.py
```

### Accéder au Dashboard

1. Ouvrir navigateur : **http://localhost:9090**
2. Se connecter :
   - **Nom d'utilisateur :** `admin`
   - **Mot de passe :** `changeme`

### Arrêter ProxyOX

Appuyer sur `Ctrl+C` dans le terminal.

## 📊 Différences SQLite vs MySQL

| Caractéristique | SQLite | MySQL |
|----------------|--------|-------|
| **Type** | Fichier local | Serveur client-serveur |
| **Performance** | Bon pour <100k req/jour | Excellent pour millions de req/jour |
| **Concurrence** | Limitée | Excellente |
| **Production** | ⚠️ Non recommandé | ✅ Recommandé |
| **Backup** | Copier le fichier `.db` | `mysqldump` |
| **Scalabilité** | Limitée | Haute |

## 🔍 Vérifications

### Vérifier que MySQL fonctionne

```powershell
# Vérifier le service
Get-Service MySQL*

# Se connecter à MySQL
mysql -u proxyox -p
# Mot de passe : proxyox

# Dans MySQL
SHOW DATABASES;
USE proxyox;
SHOW TABLES;
EXIT;
```

### Vérifier les données migrées

```sql
-- Compter les enregistrements
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM proxies;
SELECT COUNT(*) FROM backends;
SELECT COUNT(*) FROM domain_routes;
```

### Logs de ProxyOX

```powershell
# Les logs s'affichent dans le terminal
python src/main.py

# Rechercher "MySQL connected" dans la sortie
```

## ❓ Dépannage

### MySQL ne démarre pas

```powershell
# Vérifier le statut
Get-Service MySQL

# Démarrer manuellement
Start-Service MySQL

# Voir les logs
Get-Content "C:\ProgramData\MySQL\MySQL Server 8.0\Data\*.err" -Tail 50
```

### Erreur de connexion Python → MySQL

```powershell
# Vérifier l'installation des paquets
pip list | findstr mysql

# Réinstaller si nécessaire
pip install --upgrade aiomysql pymysql

# Tester la connexion
python -c "import pymysql; pymysql.connect(host='localhost', user='proxyox', password='proxyox', database='proxyox')"
```

### Migration échoue

```powershell
# Vérifier que SQLite DB existe
dir proxyox.db

# Vérifier que MySQL est accessible
python setup_mysql.py

# Relancer la migration avec plus de logs
python migrate_to_mysql.py
```

### ProxyOX ne démarre pas après migration

```powershell
# Vérifier le fichier .env
type .env

# Vérifier que MySQL est accessible
mysql -u proxyox -pproxyox -e "SHOW TABLES" proxyox

# Lancer avec mode debug
python src/main.py
```

## 🔐 Sécurité

### Changer le mot de passe par défaut

```sql
-- Se connecter à MySQL
mysql -u root -p

-- Changer le mot de passe de l'utilisateur proxyox
ALTER USER 'proxyox'@'localhost' IDENTIFIED BY 'nouveau_mot_de_passe_fort';
FLUSH PRIVILEGES;
```

Puis mettre à jour `.env` :
```env
MYSQL_PASSWORD=nouveau_mot_de_passe_fort
```

### Changer le mot de passe admin du dashboard

1. Se connecter au dashboard : http://localhost:9090
2. Aller dans "Settings"
3. Changer le mot de passe de l'utilisateur `admin`

Ou via MySQL :
```sql
-- Générer un hash SHA-256 du nouveau mot de passe
-- (utiliser un outil en ligne ou Python)

UPDATE users 
SET password_hash = SHA2('nouveau_mot_de_passe', 256) 
WHERE username = 'admin';
```

## 💾 Sauvegarde et Restauration

### Sauvegarder la base de données

```powershell
# Sauvegarde complète
mysqldump -u proxyox -p proxyox > backup_$(Get-Date -Format "yyyyMMdd").sql

# Sauvegarde automatique quotidienne (Task Scheduler)
# Créer un fichier backup.ps1 :
$date = Get-Date -Format "yyyyMMdd"
mysqldump -u proxyox -pproxyox proxyox > "C:\Backups\proxyox_$date.sql"

# Ajouter une tâche planifiée
# Panneau de configuration > Outils d'administration > Planificateur de tâches
```

### Restaurer la base de données

```powershell
# Supprimer et recréer la base
mysql -u root -p -e "DROP DATABASE IF EXISTS proxyox; CREATE DATABASE proxyox;"

# Restaurer
mysql -u proxyox -p proxyox < backup_20250126.sql

# Vérifier
mysql -u proxyox -p -e "SELECT COUNT(*) FROM users" proxyox
```

## 📈 Optimisation des Performances

### Augmenter le pool de connexions

Éditer `src/database/mysql_manager.py` :

```python
self.pool = await aiomysql.create_pool(
    ...,
    minsize=10,      # Au lieu de 1
    maxsize=50,      # Au lieu de 10
    ...
)
```

### Configurer MySQL pour les performances

Éditer `my.ini` (Windows) :

```ini
[mysqld]
# Buffer pool (1GB pour serveur avec 4GB RAM)
innodb_buffer_pool_size=1G

# Logs
innodb_log_file_size=256M
innodb_flush_log_at_trx_commit=2

# Connexions
max_connections=200

# Cache des requêtes (MySQL 5.7 seulement)
query_cache_type=1
query_cache_size=64M
```

Redémarrer MySQL après modification :
```powershell
Restart-Service MySQL
```

### Maintenance régulière

```sql
-- Optimiser les tables (1x par semaine)
OPTIMIZE TABLE proxies, backends, domain_routes, audit_logs;

-- Nettoyer les vieux logs d'audit (1x par mois)
DELETE FROM audit_logs WHERE created_at < DATE_SUB(NOW(), INTERVAL 90 DAY);

-- Nettoyer les sessions expirées
DELETE FROM sessions WHERE expires_at < NOW();
```

## 📚 Ressources

- **MySQL Official Docs :** https://dev.mysql.com/doc/
- **aiomysql Documentation :** https://aiomysql.readthedocs.io/
- **ProxyOX Issues :** (GitHub repo si disponible)

## 🆘 Support

Pour obtenir de l'aide :

1. Vérifier les logs de ProxyOX et MySQL
2. Consulter [MYSQL_SETUP.md](MYSQL_SETUP.md) pour le dépannage
3. Vérifier que tous les prérequis sont installés
4. S'assurer que le service MySQL est démarré

## ✅ Checklist de Migration

- [ ] MySQL installé et fonctionnel
- [ ] Service MySQL démarré
- [ ] Base `proxyox` créée
- [ ] Utilisateur `proxyox` créé avec privilèges
- [ ] Fichier `.env` configuré
- [ ] Paquets Python installés (`aiomysql`, `pymysql`)
- [ ] Migration exécutée avec succès
- [ ] ProxyOX démarre sans erreur
- [ ] Dashboard accessible (http://localhost:9090)
- [ ] Connexion possible avec admin/changeme
- [ ] Proxies fonctionnels
- [ ] Ancien fichier `proxyox.db` sauvegardé

## 🎉 Conclusion

Félicitations ! Vous avez migré ProxyOX vers MySQL avec succès.

**Avantages obtenus :**
- ✅ Base de données professionnelle
- ✅ Meilleures performances
- ✅ Support de la concurrence
- ✅ Prêt pour la production
- ✅ Scalabilité améliorée
- ✅ Outils de backup avancés

Profitez de ProxyOX ! 🚀
