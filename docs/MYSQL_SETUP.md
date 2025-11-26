# MySQL Installation Guide for ProxyOX on Windows

## Option 1: MySQL Installer (Recommended)

### Download and Install MySQL

1. **Download MySQL Installer**
   - Visit: https://dev.mysql.com/downloads/installer/
   - Download `mysql-installer-community-8.0.XX.msi` (larger file with MySQL Server)

2. **Run the Installer**
   - Choose "Developer Default" or "Server only"
   - Click "Next" and "Execute" to download components

3. **Configuration**
   - Type and Networking: Keep defaults (Port 3306)
   - Authentication Method: Use strong password encryption (recommended)
   - Accounts and Roles: Set a root password (remember it!)
   - Windows Service: Check "Start MySQL Server at System Startup"

4. **Complete Installation**
   - Click "Execute" to apply configuration
   - Click "Finish"

### Verify Installation

```powershell
# Check if MySQL service is running
Get-Service -Name MySQL*

# Try to connect (enter your root password when prompted)
mysql -u root -p
```

If successful, you should see the MySQL prompt: `mysql>`

Type `exit` to leave MySQL.

---

## Option 2: MySQL ZIP Archive (No Installer)

1. **Download MySQL ZIP**
   - Visit: https://dev.mysql.com/downloads/mysql/
   - Choose "Windows (x86, 64-bit), ZIP Archive"

2. **Extract to C:\mysql**
   ```powershell
   # Extract the downloaded ZIP to C:\mysql
   Expand-Archive -Path "mysql-8.0.XX-winx64.zip" -DestinationPath "C:\"
   Rename-Item -Path "C:\mysql-8.0.XX-winx64" -NewName "mysql"
   ```

3. **Create Configuration File**
   Create `C:\mysql\my.ini`:
   ```ini
   [mysqld]
   basedir=C:/mysql
   datadir=C:/mysql/data
   port=3306
   ```

4. **Initialize MySQL**
   ```powershell
   cd C:\mysql\bin
   .\mysqld --initialize-insecure --console
   ```

5. **Install as Windows Service**
   ```powershell
   # Run PowerShell as Administrator
   cd C:\mysql\bin
   .\mysqld --install MySQL --defaults-file="C:\mysql\my.ini"
   ```

6. **Start MySQL Service**
   ```powershell
   Start-Service MySQL
   ```

7. **Set Root Password**
   ```powershell
   cd C:\mysql\bin
   .\mysql -u root
   ```
   
   In MySQL prompt:
   ```sql
   ALTER USER 'root'@'localhost' IDENTIFIED BY 'your_password';
   FLUSH PRIVILEGES;
   EXIT;
   ```

---

## Setup ProxyOX Database

Once MySQL is installed and running:

### 1. Run the Setup Script

```powershell
cd C:\Users\antoi\Documents\ProxyOX-1
python setup_mysql.py
```

This will:
- Create the `proxyox` database
- Create the `proxyox` user with password `proxyox`
- Grant all privileges on the database

**Enter your MySQL root credentials when prompted.**

### 2. Migrate Data from SQLite

```powershell
python migrate_to_mysql.py
```

This will copy all data from `proxyox.db` (SQLite) to MySQL:
- Users
- Proxies
- Backends
- Domain routes
- IP filters
- Settings

### 3. Start ProxyOX

```powershell
python src/main.py
```

---

## Configuration

ProxyOX MySQL settings are in `.env`:

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=proxyox
MYSQL_PASSWORD=proxyox
MYSQL_DATABASE=proxyox
```

To change these:
1. Edit `.env` file
2. Update the database/user in MySQL accordingly
3. Restart ProxyOX

---

## Troubleshooting

### MySQL Service Won't Start

```powershell
# Check service status
Get-Service MySQL

# View logs
Get-Content "C:\ProgramData\MySQL\MySQL Server 8.0\Data\*.err" -Tail 50

# Restart service
Restart-Service MySQL
```

### Can't Connect to MySQL

```powershell
# Test connection
mysql -h localhost -P 3306 -u root -p

# Check if port 3306 is listening
netstat -an | findstr 3306

# Check firewall
New-NetFirewallRule -DisplayName "MySQL" -Direction Inbound -Protocol TCP -LocalPort 3306 -Action Allow
```

### Access Denied Error

```sql
-- Connect as root and check user
mysql -u root -p

-- In MySQL:
SELECT user, host FROM mysql.user;
SHOW GRANTS FOR 'proxyox'@'localhost';

-- Recreate user if needed
DROP USER IF EXISTS 'proxyox'@'localhost';
CREATE USER 'proxyox'@'localhost' IDENTIFIED BY 'proxyox';
GRANT ALL PRIVILEGES ON proxyox.* TO 'proxyox'@'localhost';
FLUSH PRIVILEGES;
```

### Python Can't Connect

```powershell
# Verify aiomysql and pymysql are installed
pip list | findstr mysql

# Reinstall if needed
pip install --upgrade aiomysql pymysql

# Test connection
python -c "import pymysql; print(pymysql.connect(host='localhost', user='proxyox', password='proxyox', database='proxyox'))"
```

---

## Performance Tips

### For Production

1. **Increase Connection Pool Size**
   
   Edit `src/database/mysql_manager.py`:
   ```python
   self.pool = await aiomysql.create_pool(
       ...,
       minsize=5,
       maxsize=20,
       ...
   )
   ```

2. **Enable Query Cache** (if using MySQL 5.7)
   
   Add to `my.ini`:
   ```ini
   [mysqld]
   query_cache_type=1
   query_cache_size=64M
   ```

3. **Optimize InnoDB Settings**
   
   Add to `my.ini`:
   ```ini
   [mysqld]
   innodb_buffer_pool_size=1G
   innodb_log_file_size=256M
   innodb_flush_log_at_trx_commit=2
   ```

4. **Regular Maintenance**
   ```sql
   -- Optimize tables weekly
   OPTIMIZE TABLE proxies, backends, domain_routes, audit_logs;
   
   -- Clean old audit logs
   DELETE FROM audit_logs WHERE created_at < DATE_SUB(NOW(), INTERVAL 90 DAY);
   ```

---

## Backup and Restore

### Backup Database

```powershell
# Full backup
mysqldump -u proxyox -p proxyox > backup_$(Get-Date -Format "yyyyMMdd").sql

# Backup schema only
mysqldump -u proxyox -p --no-data proxyox > schema_backup.sql

# Backup data only
mysqldump -u proxyox -p --no-create-info proxyox > data_backup.sql
```

### Restore Database

```powershell
# Drop and recreate database
mysql -u root -p -e "DROP DATABASE IF EXISTS proxyox; CREATE DATABASE proxyox;"

# Restore
mysql -u proxyox -p proxyox < backup_20250126.sql
```

---

## Uninstall MySQL

### If installed with MySQL Installer:

1. Open "Add or Remove Programs"
2. Find "MySQL Server 8.0"
3. Click "Uninstall"
4. Choose "Remove" (not "Reconfigure")

### If installed manually:

```powershell
# Stop service
Stop-Service MySQL

# Remove service
sc.exe delete MySQL

# Delete files
Remove-Item -Path "C:\mysql" -Recurse -Force
Remove-Item -Path "C:\ProgramData\MySQL" -Recurse -Force
```

---

## Alternative: Use XAMPP

If you prefer an all-in-one solution:

1. **Download XAMPP**: https://www.apachefriends.org/
2. **Install** and start MySQL via XAMPP Control Panel
3. **Update .env**:
   ```env
   MYSQL_HOST=localhost
   MYSQL_PORT=3306
   MYSQL_USER=root
   MYSQL_PASSWORD=
   MYSQL_DATABASE=proxyox
   ```
4. **Run setup script** (use empty password for root)

---

## Next Steps

After MySQL is running:

1. ✅ Run `python setup_mysql.py` to create database and user
2. ✅ Run `python migrate_to_mysql.py` to migrate data
3. ✅ Start ProxyOX: `python src/main.py`
4. ✅ Access dashboard: http://localhost:9090
5. ✅ Login with: admin / changeme

Enjoy ProxyOX with MySQL! 🚀
