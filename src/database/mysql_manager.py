"""MySQL Database manager for ProxyOX"""
import aiomysql
import structlog
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import hashlib
import secrets

logger = structlog.get_logger()

class MySQLDatabaseManager:
    """Async MySQL database manager"""
    
    def __init__(self, host: str = "localhost", port: int = 3306, 
                 user: str = "proxyox", password: str = "proxyox",
                 database: str = "proxyox"):
        """Initialize MySQL database manager"""
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.pool: Optional[aiomysql.Pool] = None
        self._initialized = False
        
    async def connect(self):
        """Create connection pool"""
        if self.pool is None:
            self.pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                db=self.database,
                autocommit=True,
                charset='utf8mb4',
                cursorclass=aiomysql.DictCursor
            )
            logger.info("MySQL connected", host=self.host, database=self.database)
            
    async def disconnect(self):
        """Close connection pool"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            self.pool = None
            logger.info("MySQL disconnected")
            
    async def execute(self, query: str, params: tuple = None):
        """Execute a query and return cursor"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params or ())
                return cur
                
    async def fetchone(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """Execute query and fetch one result"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params or ())
                return await cur.fetchone()
                
    async def fetchall(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Execute query and fetch all results"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params or ())
                return await cur.fetchall()
                
    async def initialize(self):
        """Initialize database schema"""
        if self._initialized:
            return
            
        await self.connect()
        
        try:
            # Create tables
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # Users table (first - no dependencies)
                    await cur.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            username VARCHAR(255) UNIQUE NOT NULL,
                            password_hash VARCHAR(255) NOT NULL,
                            email VARCHAR(255),
                            role VARCHAR(50) DEFAULT 'admin',
                            is_active BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            last_login TIMESTAMP NULL,
                            INDEX idx_username (username),
                            INDEX idx_email (email)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """)
                    
                    # Backends table (before proxies - needed by proxies foreign key)
                    await cur.execute("""
                        CREATE TABLE IF NOT EXISTS backends (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            name VARCHAR(255) UNIQUE NOT NULL,
                            server_address VARCHAR(255) NOT NULL,
                            server_port INT NOT NULL,
                            use_https BOOLEAN DEFAULT FALSE,
                            is_enabled BOOLEAN DEFAULT TRUE,
                            health_check_enabled BOOLEAN DEFAULT FALSE,
                            health_check_interval INT DEFAULT 30,
                            health_check_path VARCHAR(255) DEFAULT '/',
                            weight INT DEFAULT 1,
                            max_connections INT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            INDEX idx_name (name),
                            INDEX idx_enabled (is_enabled)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """)
                    
                    # Proxies table (after backends)
                    await cur.execute("""
                        CREATE TABLE IF NOT EXISTS proxies (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            name VARCHAR(255) UNIQUE NOT NULL,
                            bind_address VARCHAR(255) NOT NULL,
                            bind_port INT NOT NULL,
                            mode VARCHAR(20) NOT NULL,
                            default_backend_id INT,
                            is_enabled BOOLEAN DEFAULT TRUE,
                            max_connections INT DEFAULT 100,
                            rate_limit INT DEFAULT 1000,
                            timeout INT DEFAULT 300,
                            use_ssl BOOLEAN DEFAULT FALSE,
                            ssl_cert_path TEXT,
                            ssl_key_path TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            FOREIGN KEY (default_backend_id) REFERENCES backends(id) ON DELETE SET NULL,
                            INDEX idx_name (name),
                            INDEX idx_enabled (is_enabled),
                            INDEX idx_mode (mode),
                            CHECK (mode IN ('http', 'tcp', 'udp'))
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """)
                    
                    # Domain routes table
                    await cur.execute("""
                        CREATE TABLE IF NOT EXISTS domain_routes (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            proxy_id INT NOT NULL,
                            domain VARCHAR(255) NOT NULL,
                            backend_id INT NOT NULL,
                            priority INT DEFAULT 0,
                            is_enabled BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            FOREIGN KEY (proxy_id) REFERENCES proxies(id) ON DELETE CASCADE,
                            FOREIGN KEY (backend_id) REFERENCES backends(id) ON DELETE CASCADE,
                            UNIQUE KEY unique_proxy_domain (proxy_id, domain),
                            INDEX idx_proxy (proxy_id),
                            INDEX idx_domain (domain),
                            INDEX idx_backend (backend_id)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """)
                    
                    # IP filters table
                    await cur.execute("""
                        CREATE TABLE IF NOT EXISTS ip_filters (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            ip_address VARCHAR(255) NOT NULL,
                            filter_type VARCHAR(20) NOT NULL,
                            proxy_id INT,
                            reason TEXT,
                            is_enabled BOOLEAN DEFAULT TRUE,
                            expires_at TIMESTAMP NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            FOREIGN KEY (proxy_id) REFERENCES proxies(id) ON DELETE CASCADE,
                            UNIQUE KEY unique_ip_filter (ip_address, filter_type, proxy_id),
                            INDEX idx_ip (ip_address),
                            INDEX idx_type (filter_type),
                            INDEX idx_proxy (proxy_id),
                            CHECK (filter_type IN ('blacklist', 'whitelist'))
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """)
                    
                    # Settings table
                    await cur.execute("""
                        CREATE TABLE IF NOT EXISTS settings (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            `key` VARCHAR(255) UNIQUE NOT NULL,
                            value TEXT NOT NULL,
                            value_type VARCHAR(20) DEFAULT 'string',
                            description TEXT,
                            is_secret BOOLEAN DEFAULT FALSE,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            updated_by INT,
                            FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL,
                            INDEX idx_key (`key`),
                            CHECK (value_type IN ('string', 'int', 'float', 'bool', 'json'))
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """)
                    
                    # Audit logs table
                    await cur.execute("""
                        CREATE TABLE IF NOT EXISTS audit_logs (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            user_id INT,
                            action VARCHAR(50) NOT NULL,
                            resource_type VARCHAR(50) NOT NULL,
                            resource_id INT,
                            details TEXT,
                            ip_address VARCHAR(255),
                            user_agent TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                            INDEX idx_user (user_id),
                            INDEX idx_action (action),
                            INDEX idx_resource (resource_type, resource_id),
                            INDEX idx_created (created_at)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """)
                    
                    # Sessions table
                    await cur.execute("""
                        CREATE TABLE IF NOT EXISTS sessions (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            user_id INT NOT NULL,
                            token_hash VARCHAR(255) UNIQUE NOT NULL,
                            refresh_token_hash VARCHAR(255) UNIQUE,
                            ip_address VARCHAR(255),
                            user_agent TEXT,
                            expires_at TIMESTAMP NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            is_active BOOLEAN DEFAULT TRUE,
                            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                            INDEX idx_user (user_id),
                            INDEX idx_token (token_hash),
                            INDEX idx_expires (expires_at),
                            INDEX idx_active (is_active)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """)
                    
                    # Traffic history table (1440 intervals per day = 1 minute each)
                    await cur.execute("""
                        CREATE TABLE IF NOT EXISTS traffic_history (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            proxy_name VARCHAR(255) NOT NULL,
                            date DATE NOT NULL,
                            interval_index INT NOT NULL,
                            request_count INT DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            UNIQUE KEY unique_traffic (proxy_name, date, interval_index),
                            INDEX idx_proxy (proxy_name),
                            INDEX idx_date (date)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """)
                    
            # Create default admin user
            await self._create_default_admin()
            
            # Create default settings
            await self._create_default_settings()
            
            self._initialized = True
            logger.info("MySQL database initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize MySQL database", error=str(e))
            raise
            
    async def _create_default_admin(self):
        """Create default admin user"""
        result = await self.fetchone("SELECT COUNT(*) as count FROM users")
        
        if result['count'] == 0:
            password_hash = hashlib.sha256("changeme".encode()).hexdigest()
            
            await self.execute("""
                INSERT INTO users (username, password_hash, email, role)
                VALUES (%s, %s, %s, %s)
            """, ("admin", password_hash, "admin@proxyox.local", "admin"))
            
            logger.info("Default admin user created", username="admin")
            
    async def _create_default_settings(self):
        """Create default global settings"""
        default_settings = [
            ("log_level", "info", "string", "Global log level", False),
            ("use_uvloop", "false", "bool", "Use uvloop for better performance", False),
            ("timeout", "300", "int", "Default connection timeout in seconds", False),
            ("max_connections", "100", "int", "Default max connections per proxy", False),
            ("rate_limit", "1000", "int", "Default rate limit per second", False),
            ("jwt_secret", secrets.token_hex(32), "string", "JWT secret key", True),
            ("jwt_expiry", "3600", "int", "JWT token expiry in seconds", False),
            ("refresh_token_expiry", "604800", "int", "Refresh token expiry (7 days)", False),
            ("DASHBOARD_HOST", "0.0.0.0", "string", "Dashboard bind address", False),
            ("DASHBOARD_PORT", "9090", "int", "Dashboard port", False),
        ]
        
        for key, value, value_type, description, is_secret in default_settings:
            result = await self.fetchone("SELECT COUNT(*) as count FROM settings WHERE `key` = %s", (key,))
            if result['count'] == 0:
                await self.execute("""
                    INSERT INTO settings (`key`, value, value_type, description, is_secret)
                    VALUES (%s, %s, %s, %s, %s)
                """, (key, value, value_type, description, is_secret))
                
        logger.info("Default settings created")

    # ========== USER OPERATIONS ==========
    
    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        return await self.fetchone(
            "SELECT * FROM users WHERE username = %s AND is_active = 1",
            (username,)
        )
        
    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        return await self.fetchone(
            "SELECT * FROM users WHERE id = %s AND is_active = 1",
            (user_id,)
        )
        
    async def update_user_last_login(self, user_id: int):
        """Update user's last login timestamp"""
        await self.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s",
            (user_id,)
        )
        
    async def list_users(self) -> List[Dict[str, Any]]:
        """List all users"""
        return await self.fetchall(
            "SELECT id, username, email, role, is_active, created_at, last_login FROM users"
        )
        
    # ========== PROXY OPERATIONS ==========
    
    async def list_proxies(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """List all proxies"""
        query = "SELECT * FROM proxies"
        if enabled_only:
            query += " WHERE is_enabled = 1"
        query += " ORDER BY name"
        
        return await self.fetchall(query)
        
    async def get_proxy(self, proxy_id: int) -> Optional[Dict[str, Any]]:
        """Get proxy by ID"""
        return await self.fetchone("SELECT * FROM proxies WHERE id = %s", (proxy_id,))
        
    async def get_proxy_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get proxy by name"""
        return await self.fetchone("SELECT * FROM proxies WHERE name = %s", (name,))
        
    async def create_proxy(self, data: Dict[str, Any], user_id: int) -> int:
        """Create new proxy"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO proxies (
                        name, bind_address, bind_port, mode, default_backend_id,
                        is_enabled, max_connections, rate_limit, timeout,
                        use_ssl, ssl_cert_path, ssl_key_path
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    data['name'], data['bind_address'], data['bind_port'], data['mode'],
                    data.get('default_backend_id'), data.get('is_enabled', True),
                    data.get('max_connections', 100), data.get('rate_limit', 1000),
                    data.get('timeout', 300), data.get('use_ssl', False),
                    data.get('ssl_cert_path'), data.get('ssl_key_path')
                ))
                
                proxy_id = cur.lastrowid
                
        # Audit log
        await self.create_audit_log(
            user_id=user_id,
            action="CREATE",
            resource_type="proxy",
            resource_id=proxy_id,
            details=json.dumps({"name": data['name']})
        )
        
        logger.info("Proxy created", proxy_id=proxy_id, name=data['name'])
        return proxy_id
        
    async def update_proxy(self, proxy_id: int, data: Dict[str, Any], user_id: int):
        """Update proxy"""
        set_clause = []
        values = []
        
        for key in ['bind_address', 'bind_port', 'mode', 'default_backend_id',
                    'is_enabled', 'max_connections', 'rate_limit', 'timeout',
                    'use_ssl', 'ssl_cert_path', 'ssl_key_path']:
            if key in data:
                set_clause.append(f"{key} = %s")
                values.append(data[key])
                
        if not set_clause:
            return
            
        values.append(proxy_id)
        
        query = f"UPDATE proxies SET {', '.join(set_clause)} WHERE id = %s"
        await self.execute(query, tuple(values))
        
        # Audit log
        await self.create_audit_log(
            user_id=user_id,
            action="UPDATE",
            resource_type="proxy",
            resource_id=proxy_id,
            details=json.dumps(data)
        )
        
        logger.info("Proxy updated", proxy_id=proxy_id)
        
    async def delete_proxy(self, proxy_id: int, user_id: int):
        """Delete proxy"""
        await self.execute("DELETE FROM proxies WHERE id = %s", (proxy_id,))
        
        # Audit log
        await self.create_audit_log(
            user_id=user_id,
            action="DELETE",
            resource_type="proxy",
            resource_id=proxy_id
        )
        
        logger.info("Proxy deleted", proxy_id=proxy_id)
        
    # ========== BACKEND OPERATIONS ==========
    
    async def list_backends(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """List all backends"""
        query = "SELECT * FROM backends"
        if enabled_only:
            query += " WHERE is_enabled = 1"
        query += " ORDER BY name"
        
        return await self.fetchall(query)
        
    async def get_backend(self, backend_id: int) -> Optional[Dict[str, Any]]:
        """Get backend by ID"""
        return await self.fetchone("SELECT * FROM backends WHERE id = %s", (backend_id,))
        
    async def get_backend_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get backend by name"""
        return await self.fetchone("SELECT * FROM backends WHERE name = %s", (name,))
        
    async def create_backend(self, data: Dict[str, Any], user_id: int) -> int:
        """Create new backend"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO backends (
                        name, server_address, server_port, use_https, is_enabled,
                        health_check_enabled, health_check_interval, health_check_path,
                        weight, max_connections
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    data['name'], data['server_address'], data['server_port'],
                    data.get('use_https', False), data.get('is_enabled', True),
                    data.get('health_check_enabled', False),
                    data.get('health_check_interval', 30),
                    data.get('health_check_path', '/'),
                    data.get('weight', 1), data.get('max_connections')
                ))
                
                backend_id = cur.lastrowid
                
        # Audit log
        await self.create_audit_log(
            user_id=user_id,
            action="CREATE",
            resource_type="backend",
            resource_id=backend_id,
            details=json.dumps({"name": data['name']})
        )
        
        logger.info("Backend created", backend_id=backend_id, name=data['name'])
        return backend_id
        
    async def update_backend(self, backend_id: int, data: Dict[str, Any], user_id: int):
        """Update backend"""
        set_clause = []
        values = []
        
        for key in ['server_address', 'server_port', 'use_https', 'is_enabled',
                    'health_check_enabled', 'health_check_interval',
                    'health_check_path', 'weight', 'max_connections']:
            if key in data:
                set_clause.append(f"{key} = %s")
                values.append(data[key])
                
        if not set_clause:
            return
            
        values.append(backend_id)
        
        query = f"UPDATE backends SET {', '.join(set_clause)} WHERE id = %s"
        await self.execute(query, tuple(values))
        
        # Audit log
        await self.create_audit_log(
            user_id=user_id,
            action="UPDATE",
            resource_type="backend",
            resource_id=backend_id,
            details=json.dumps(data)
        )
        
        logger.info("Backend updated", backend_id=backend_id)
        
    async def delete_backend(self, backend_id: int, user_id: int):
        """Delete backend"""
        await self.execute("DELETE FROM backends WHERE id = %s", (backend_id,))
        
        # Audit log
        await self.create_audit_log(
            user_id=user_id,
            action="DELETE",
            resource_type="backend",
            resource_id=backend_id
        )
        
        logger.info("Backend deleted", backend_id=backend_id)
        
    # ========== DOMAIN ROUTE OPERATIONS ==========
    
    async def list_domain_routes(self, proxy_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """List domain routes"""
        if proxy_id:
            return await self.fetchall(
                """SELECT dr.*, b.name as backend_name 
                   FROM domain_routes dr 
                   LEFT JOIN backends b ON dr.backend_id = b.id
                   WHERE dr.proxy_id = %s AND dr.is_enabled = 1
                   ORDER BY dr.priority DESC, dr.domain""",
                (proxy_id,)
            )
        else:
            return await self.fetchall(
                """SELECT dr.*, b.name as backend_name, p.name as proxy_name
                   FROM domain_routes dr 
                   LEFT JOIN backends b ON dr.backend_id = b.id
                   LEFT JOIN proxies p ON dr.proxy_id = p.id
                   WHERE dr.is_enabled = 1
                   ORDER BY dr.proxy_id, dr.priority DESC, dr.domain"""
            )
        
    async def create_domain_route(self, data: Dict[str, Any], user_id: int) -> int:
        """Create domain route"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO domain_routes (proxy_id, domain, backend_id, priority, is_enabled)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    data['proxy_id'], data['domain'], data['backend_id'],
                    data.get('priority', 0), data.get('is_enabled', True)
                ))
                
                route_id = cur.lastrowid
                
        # Audit log
        await self.create_audit_log(
            user_id=user_id,
            action="CREATE",
            resource_type="domain_route",
            resource_id=route_id,
            details=json.dumps({"domain": data['domain']})
        )
        
        logger.info("Domain route created", route_id=route_id, domain=data['domain'])
        return route_id
        
    async def delete_domain_route(self, route_id: int, user_id: int):
        """Delete domain route"""
        await self.execute("DELETE FROM domain_routes WHERE id = %s", (route_id,))
        
        # Audit log
        await self.create_audit_log(
            user_id=user_id,
            action="DELETE",
            resource_type="domain_route",
            resource_id=route_id
        )
        
        logger.info("Domain route deleted", route_id=route_id)
        
    # ========== IP FILTER OPERATIONS ==========
    
    async def list_ip_filters(self, filter_type: Optional[str] = None,
                            proxy_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """List IP filters"""
        query = "SELECT * FROM ip_filters WHERE is_enabled = 1"
        params = []
        
        if filter_type:
            query += " AND filter_type = %s"
            params.append(filter_type)
            
        if proxy_id:
            query += " AND (proxy_id = %s OR proxy_id IS NULL)"
            params.append(proxy_id)
            
        query += " ORDER BY created_at DESC"
        
        return await self.fetchall(query, tuple(params) if params else None)
        
    async def add_ip_filter(self, ip_address: str, filter_type: str,
                          proxy_id: Optional[int], reason: Optional[str],
                          user_id: int) -> int:
        """Add IP filter"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO ip_filters 
                    (ip_address, filter_type, proxy_id, reason, is_enabled)
                    VALUES (%s, %s, %s, %s, 1)
                    ON DUPLICATE KEY UPDATE 
                    reason = VALUES(reason), is_enabled = 1
                """, (ip_address, filter_type, proxy_id, reason))
                
                filter_id = cur.lastrowid
                
        # Audit log
        await self.create_audit_log(
            user_id=user_id,
            action="CREATE",
            resource_type="ip_filter",
            resource_id=filter_id,
            details=json.dumps({
                "ip": ip_address,
                "type": filter_type,
                "reason": reason
            })
        )
        
        logger.info("IP filter added", ip=ip_address, type=filter_type)
        return filter_id
        
    async def remove_ip_filter(self, filter_id: int, user_id: int):
        """Remove IP filter"""
        await self.execute("DELETE FROM ip_filters WHERE id = %s", (filter_id,))
        
        # Audit log
        await self.create_audit_log(
            user_id=user_id,
            action="DELETE",
            resource_type="ip_filter",
            resource_id=filter_id
        )
        
        logger.info("IP filter removed", filter_id=filter_id)
        
    # ========== SETTINGS OPERATIONS ==========
    
    async def get_setting(self, key: str) -> Optional[Any]:
        """Get setting value"""
        result = await self.fetchone("SELECT value, value_type FROM settings WHERE `key` = %s", (key,))
        
        if not result:
            return None
            
        value = result['value']
        value_type = result['value_type']
        
        # Convert to appropriate type
        if value_type == 'int':
            return int(value)
        elif value_type == 'float':
            return float(value)
        elif value_type == 'bool':
            return value.lower() in ('true', '1', 'yes')
        elif value_type == 'json':
            return json.loads(value)
        else:
            return value
            
    async def set_setting(self, key: str, value: Any, user_id: int):
        """Set setting value"""
        # Determine value type
        if isinstance(value, bool):
            value_type = 'bool'
            value_str = 'true' if value else 'false'
        elif isinstance(value, int):
            value_type = 'int'
            value_str = str(value)
        elif isinstance(value, float):
            value_type = 'float'
            value_str = str(value)
        elif isinstance(value, (dict, list)):
            value_type = 'json'
            value_str = json.dumps(value)
        else:
            value_type = 'string'
            value_str = str(value)
            
        await self.execute("""
            INSERT INTO settings (`key`, value, value_type, updated_by)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            value = VALUES(value), 
            value_type = VALUES(value_type),
            updated_by = VALUES(updated_by)
        """, (key, value_str, value_type, user_id))
        
        logger.info("Setting updated", key=key)
        
    async def list_settings(self, include_secrets: bool = False) -> Dict[str, Any]:
        """List all settings"""
        query = "SELECT `key`, value, value_type FROM settings"
        if not include_secrets:
            query += " WHERE is_secret = 0"
            
        results = await self.fetchall(query)
        settings = {}
        
        for row in results:
            key = row['key']
            value = row['value']
            value_type = row['value_type']
            
            # Convert to appropriate type
            if value_type == 'int':
                settings[key] = int(value)
            elif value_type == 'float':
                settings[key] = float(value)
            elif value_type == 'bool':
                settings[key] = value.lower() in ('true', '1', 'yes')
            elif value_type == 'json':
                settings[key] = json.loads(value)
            else:
                settings[key] = value
                
        return settings
        
    # ========== AUDIT LOG OPERATIONS ==========
    
    async def create_audit_log(self, user_id: int, action: str,
                             resource_type: str, resource_id: Optional[int] = None,
                             details: Optional[str] = None,
                             ip_address: Optional[str] = None,
                             user_agent: Optional[str] = None):
        """Create audit log entry"""
        await self.execute("""
            INSERT INTO audit_logs 
            (user_id, action, resource_type, resource_id, details, ip_address, user_agent)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (user_id, action, resource_type, resource_id, details, ip_address, user_agent))
        
    async def list_audit_logs(self, limit: int = 100, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """List audit logs"""
        query = """
            SELECT al.*, u.username 
            FROM audit_logs al
            LEFT JOIN users u ON al.user_id = u.id
        """
        params = []
        
        if user_id:
            query += " WHERE al.user_id = %s"
            params.append(user_id)
            
        query += " ORDER BY al.created_at DESC LIMIT %s"
        params.append(limit)
        
        return await self.fetchall(query, tuple(params))
        
    # ========== SESSION OPERATIONS ==========
    
    async def create_session(self, user_id: int, token_hash: str,
                           refresh_token_hash: str, expires_at: datetime,
                           ip_address: Optional[str] = None,
                           user_agent: Optional[str] = None) -> int:
        """Create user session"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO sessions 
                    (user_id, token_hash, refresh_token_hash, expires_at, ip_address, user_agent)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (user_id, token_hash, refresh_token_hash, expires_at, ip_address, user_agent))
                
                return cur.lastrowid
        
    async def get_session_by_token(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """Get session by access token hash"""
        return await self.fetchone("""
            SELECT * FROM sessions 
            WHERE token_hash = %s AND is_active = 1 AND expires_at > NOW()
        """, (token_hash,))
    
    async def get_session_by_refresh_token(self, refresh_token_hash: str) -> Optional[Dict[str, Any]]:
        """Get session by refresh token hash"""
        return await self.fetchone("""
            SELECT * FROM sessions 
            WHERE refresh_token_hash = %s AND is_active = 1 AND expires_at > NOW()
        """, (refresh_token_hash,))
        
    async def invalidate_session(self, session_id: int):
        """Invalidate session"""
        await self.execute(
            "UPDATE sessions SET is_active = 0 WHERE id = %s",
            (session_id,)
        )
        
    async def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        await self.execute("DELETE FROM sessions WHERE expires_at < NOW()")
    
    # Traffic History Methods
    
    async def save_traffic_history(self, proxy_name: str, date: str, interval_index: int, request_count: int):
        """Save or update traffic history for a specific interval"""
        await self.execute("""
            INSERT INTO traffic_history (proxy_name, date, interval_index, request_count, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE 
                request_count = request_count + VALUES(request_count),
                updated_at = NOW()
        """, (proxy_name, date, interval_index, request_count))
    
    async def get_traffic_history(self, proxy_name: str, date: str) -> List[int]:
        """Get traffic history for a proxy on a specific date (returns array of 1440 intervals)"""
        results = await self.fetchall("""
            SELECT interval_index, request_count 
            FROM traffic_history 
            WHERE proxy_name = %s AND date = %s
            ORDER BY interval_index
        """, (proxy_name, date))
        
        # Initialize 1440 intervals with 0 (1 minute each)
        history = [0] * 1440
        
        # Fill with actual data
        for row in results:
            if row['interval_index'] < 1440:
                history[row['interval_index']] = row['request_count']
        
        return history
    
    async def get_all_proxies_traffic_history(self, date: str) -> Dict[str, List[int]]:
        """Get traffic history for all proxies on a specific date"""
        results = await self.fetchall("""
            SELECT proxy_name, interval_index, request_count 
            FROM traffic_history 
            WHERE date = %s
            ORDER BY proxy_name, interval_index
        """, (date,))
        
        # Group by proxy
        history = {}
        for row in results:
            proxy_name = row['proxy_name']
            if proxy_name not in history:
                history[proxy_name] = [0] * 1440
            if row['interval_index'] < 1440:
                history[proxy_name][row['interval_index']] = row['request_count']
        
        return history
    
    async def cleanup_old_traffic_history(self, days_to_keep: int = 7):
        """Clean up traffic history older than specified days"""
        await self.execute("""
            DELETE FROM traffic_history 
            WHERE date < DATE_SUB(CURDATE(), INTERVAL %s DAY)
        """, (days_to_keep,))
