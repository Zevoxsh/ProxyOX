# 🚀 ProxyOX - Migration MySQL - Démarrage Rapide

## Option 1 : Script Automatique (Recommandé)

### Windows PowerShell :
```powershell
# Ouvrir PowerShell en tant qu'administrateur
cd C:\Users\antoi\Documents\ProxyOX-1
.\migrate_mysql.ps1
```

### Ou via Python :
```powershell
python migrate_assistant.py
```

---

## Option 2 : Étape par Étape (Manuel)

### 1. Installer MySQL (si pas déjà fait)

**Option A - Automatique :**
```powershell
python install_mysql.py
```

**Option B - Manuel :**
- Télécharger : https://dev.mysql.com/downloads/installer/
- Installer MySQL Server 8.0
- Définir un mot de passe root

### 2. Installer les dépendances Python
```powershell
pip install aiomysql pymysql
```

### 3. Configurer la base de données
```powershell
python setup_mysql.py
```
> Entrer le mot de passe root MySQL quand demandé

### 4. Migrer les données
```powershell
python migrate_to_mysql.py
```

### 5. Démarrer ProxyOX
```powershell
python src/main.py
```

### 6. Accéder au Dashboard
- URL : http://localhost:9090
- Username : `admin`
- Password : `changeme`

---

## Configuration

Fichier `.env` :
```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=proxyox
MYSQL_PASSWORD=proxyox
MYSQL_DATABASE=proxyox
```

---

## Vérification

### Vérifier MySQL :
```powershell
Get-Service MySQL*
mysql -u proxyox -p
# Password: proxyox
```

### Vérifier les données :
```sql
USE proxyox;
SHOW TABLES;
SELECT COUNT(*) FROM proxies;
SELECT COUNT(*) FROM backends;
```

---

## Troubleshooting Rapide

### MySQL ne démarre pas :
```powershell
Start-Service MySQL
```

### Erreur de connexion :
```powershell
# Vérifier que MySQL écoute sur 3306
netstat -an | findstr 3306

# Tester la connexion
mysql -h localhost -u proxyox -p
```

### ProxyOX ne démarre pas :
```powershell
# Vérifier .env
type .env

# Vérifier les logs
python src/main.py
```

---

## Fichiers Importants

| Fichier | Description |
|---------|-------------|
| `migrate_assistant.py` | Assistant de migration interactif |
| `install_mysql.py` | Installation automatique MySQL |
| `setup_mysql.py` | Configuration DB |
| `migrate_to_mysql.py` | Migration des données |
| `README_MYSQL.md` | Guide complet |
| `MYSQL_SETUP.md` | Installation détaillée |

---

## Commandes Utiles

```powershell
# Démarrer ProxyOX
python src/main.py

# Backup MySQL
mysqldump -u proxyox -p proxyox > backup.sql

# Restaurer MySQL
mysql -u proxyox -p proxyox < backup.sql

# Logs MySQL
Get-Content "C:\ProgramData\MySQL\MySQL Server 8.0\Data\*.err" -Tail 50
```

---

## Aide

Pour plus d'informations :
- Guide complet : `README_MYSQL.md`
- Installation : `MYSQL_SETUP.md`
- Changelog : `MYSQL_CHANGELOG.md`

Bon déploiement ! 🎉
