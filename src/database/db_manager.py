"""Database manager for ProxyOX"""
import sqlite3
import asyncio
import structlog
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import hashlib
import secrets

from .models import (
    User, Proxy, Backend, DomainRoute, IPFilter, 
    Setting, AuditLog, ProxyStats, Session, TrafficHistory, BaseModel
)

logger = structlog.get_logger()

class DatabaseManager:
    """Async database manager using aiosqlite-like interface"""
    
    def __init__(self, db_path: str = "proxyox.db"):
        """Initialize database manager"""
        self.db_path = Path(db_path)
        self.conn: Optional[sqlite3.Connection] = None
        self._initialized = False
        
    def connect(self):
        """Connect to database"""
        if self.conn is None:
            self.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                isolation_level=None  # Autocommit mode
            )
            self.conn.row_factory = BaseModel.dict_factory
            logger.info("Database connected", path=str(self.db_path))
            
    def disconnect(self):
        """Disconnect from database"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Database disconnected")
            
    async def initialize(self):
        """Initialize database schema"""
        if self._initialized:
            return
            
        self.connect()
        
        try:
            # Create all tables
            tables = [
                User, Proxy, Backend, DomainRoute, 
                IPFilter, Setting, AuditLog, ProxyStats, Session, TrafficHistory
            ]
            
            for table in tables:
                self.conn.execute(table.TABLE_SCHEMA)
                table.create_indexes(self.conn)
                
            # Create default admin user if not exists
            await self._create_default_admin()
            
            # Create default settings
            await self._create_default_settings()
            
            self._initialized = True
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize database", error=str(e))
            raise
            
    async def _create_default_admin(self):
        """Create default admin user"""
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM users")
        result = cursor.fetchone()
        
        if result['count'] == 0:
            # Hash default password
            password_hash = hashlib.sha256("changeme".encode()).hexdigest()
            
            self.conn.execute("""
                INSERT INTO users (username, password_hash, email, role)
                VALUES (?, ?, ?, ?)
            """, ("admin", password_hash, "admin@proxyox.local", "admin"))
            
            logger.info("Default admin user created", username="admin")
            
    async def _create_default_settings(self):
        """Create default global settings"""
        default_settings = [
            ("log_level", "info", "string", "Global log level"),
            ("use_uvloop", "false", "bool", "Use uvloop for better performance"),
            ("timeout", "300", "int", "Default connection timeout in seconds"),
            ("max_connections", "100", "int", "Default max connections per proxy"),
            ("rate_limit", "1000", "int", "Default rate limit per second"),
            ("jwt_secret", secrets.token_hex(32), "string", "JWT secret key", True),
            ("jwt_expiry", "3600", "int", "JWT token expiry in seconds"),
            ("refresh_token_expiry", "604800", "int", "Refresh token expiry (7 days)"),
        ]
        
        for key, value, value_type, description, *is_secret in default_settings:
            secret = is_secret[0] if is_secret else False
            
            cursor = self.conn.execute("SELECT COUNT(*) as count FROM settings WHERE key = ?", (key,))
            if cursor.fetchone()['count'] == 0:
                self.conn.execute("""
                    INSERT INTO settings (key, value, value_type, description, is_secret)
                    VALUES (?, ?, ?, ?, ?)
                """, (key, value, value_type, description, secret))
                
        logger.info("Default settings created")
        
    # ========== USER OPERATIONS ==========
    
    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        cursor = self.conn.execute(
            "SELECT * FROM users WHERE username = ? AND is_active = 1",
            (username,)
        )
        return cursor.fetchone()
        
    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        cursor = self.conn.execute(
            "SELECT * FROM users WHERE id = ? AND is_active = 1",
            (user_id,)
        )
        return cursor.fetchone()
        
    async def update_user_last_login(self, user_id: int):
        """Update user's last login timestamp"""
        self.conn.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
            (user_id,)
        )
        
    async def list_users(self) -> List[Dict[str, Any]]:
        """List all users"""
        cursor = self.conn.execute(
            "SELECT id, username, email, role, is_active, created_at, last_login FROM users"
        )
        return cursor.fetchall()
        
    # ========== PROXY OPERATIONS ==========
    
    async def list_proxies(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """List all proxies"""
        query = "SELECT * FROM proxies"
        if enabled_only:
            query += " WHERE is_enabled = 1"
        query += " ORDER BY name"
        
        cursor = self.conn.execute(query)
        return cursor.fetchall()
        
    async def get_proxy(self, proxy_id: int) -> Optional[Dict[str, Any]]:
        """Get proxy by ID"""
        cursor = self.conn.execute("SELECT * FROM proxies WHERE id = ?", (proxy_id,))
        return cursor.fetchone()
        
    async def get_proxy_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get proxy by name"""
        cursor = self.conn.execute("SELECT * FROM proxies WHERE name = ?", (name,))
        return cursor.fetchone()
        
    async def create_proxy(self, data: Dict[str, Any], user_id: int) -> int:
        """Create new proxy"""
        cursor = self.conn.execute("""
            INSERT INTO proxies (
                name, bind_address, bind_port, mode, default_backend_id,
                is_enabled, max_connections, rate_limit, timeout,
                use_ssl, ssl_cert_path, ssl_key_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['name'], data['bind_address'], data['bind_port'], data['mode'],
            data.get('default_backend_id'), data.get('is_enabled', True),
            data.get('max_connections', 100), data.get('rate_limit', 1000),
            data.get('timeout', 300), data.get('use_ssl', False),
            data.get('ssl_cert_path'), data.get('ssl_key_path')
        ))
        
        proxy_id = cursor.lastrowid
        
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
                set_clause.append(f"{key} = ?")
                values.append(data[key])
                
        if not set_clause:
            return
            
        set_clause.append("updated_at = CURRENT_TIMESTAMP")
        values.append(proxy_id)
        
        query = f"UPDATE proxies SET {', '.join(set_clause)} WHERE id = ?"
        self.conn.execute(query, values)
        
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
        self.conn.execute("DELETE FROM proxies WHERE id = ?", (proxy_id,))
        
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
        
        cursor = self.conn.execute(query)
        return cursor.fetchall()
        
    async def get_backend(self, backend_id: int) -> Optional[Dict[str, Any]]:
        """Get backend by ID"""
        cursor = self.conn.execute("SELECT * FROM backends WHERE id = ?", (backend_id,))
        return cursor.fetchone()
        
    async def get_backend_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get backend by name"""
        cursor = self.conn.execute("SELECT * FROM backends WHERE name = ?", (name,))
        return cursor.fetchone()
        
    async def create_backend(self, data: Dict[str, Any], user_id: int) -> int:
        """Create new backend"""
        cursor = self.conn.execute("""
            INSERT INTO backends (
                name, server_address, server_port, use_https, is_enabled,
                health_check_enabled, health_check_interval, health_check_path,
                weight, max_connections
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['name'], data['server_address'], data['server_port'],
            data.get('use_https', False), data.get('is_enabled', True),
            data.get('health_check_enabled', False),
            data.get('health_check_interval', 30),
            data.get('health_check_path', '/'),
            data.get('weight', 1), data.get('max_connections')
        ))
        
        backend_id = cursor.lastrowid
        
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
                set_clause.append(f"{key} = ?")
                values.append(data[key])
                
        if not set_clause:
            return
            
        set_clause.append("updated_at = CURRENT_TIMESTAMP")
        values.append(backend_id)
        
        query = f"UPDATE backends SET {', '.join(set_clause)} WHERE id = ?"
        self.conn.execute(query, values)
        
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
        self.conn.execute("DELETE FROM backends WHERE id = ?", (backend_id,))
        
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
            cursor = self.conn.execute(
                """SELECT dr.*, b.name as backend_name 
                   FROM domain_routes dr 
                   LEFT JOIN backends b ON dr.backend_id = b.id
                   WHERE dr.proxy_id = ? AND dr.is_enabled = 1
                   ORDER BY dr.priority DESC, dr.domain""",
                (proxy_id,)
            )
        else:
            cursor = self.conn.execute(
                """SELECT dr.*, b.name as backend_name, p.name as proxy_name
                   FROM domain_routes dr 
                   LEFT JOIN backends b ON dr.backend_id = b.id
                   LEFT JOIN proxies p ON dr.proxy_id = p.id
                   WHERE dr.is_enabled = 1
                   ORDER BY dr.proxy_id, dr.priority DESC, dr.domain"""
            )
        return cursor.fetchall()
        
    async def create_domain_route(self, data: Dict[str, Any], user_id: int) -> int:
        """Create domain route"""
        cursor = self.conn.execute("""
            INSERT INTO domain_routes (proxy_id, domain, backend_id, priority, is_enabled)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data['proxy_id'], data['domain'], data['backend_id'],
            data.get('priority', 0), data.get('is_enabled', True)
        ))
        
        route_id = cursor.lastrowid
        
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
        self.conn.execute("DELETE FROM domain_routes WHERE id = ?", (route_id,))
        
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
            query += " AND filter_type = ?"
            params.append(filter_type)
            
        if proxy_id:
            query += " AND (proxy_id = ? OR proxy_id IS NULL)"
            params.append(proxy_id)
            
        query += " ORDER BY created_at DESC"
        
        cursor = self.conn.execute(query, params)
        return cursor.fetchall()
        
    async def add_ip_filter(self, ip_address: str, filter_type: str,
                          proxy_id: Optional[int], reason: Optional[str],
                          user_id: int) -> int:
        """Add IP filter"""
        cursor = self.conn.execute("""
            INSERT OR REPLACE INTO ip_filters 
            (ip_address, filter_type, proxy_id, reason, is_enabled)
            VALUES (?, ?, ?, ?, 1)
        """, (ip_address, filter_type, proxy_id, reason))
        
        filter_id = cursor.lastrowid
        
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
        self.conn.execute("DELETE FROM ip_filters WHERE id = ?", (filter_id,))
        
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
        cursor = self.conn.execute("SELECT value, value_type FROM settings WHERE key = ?", (key,))
        result = cursor.fetchone()
        
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
            
        self.conn.execute("""
            INSERT OR REPLACE INTO settings (key, value, value_type, updated_at, updated_by)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
        """, (key, value_str, value_type, user_id))
        
        logger.info("Setting updated", key=key)
        
    async def list_settings(self, include_secrets: bool = False) -> Dict[str, Any]:
        """List all settings"""
        query = "SELECT key, value, value_type FROM settings"
        if not include_secrets:
            query += " WHERE is_secret = 0"
            
        cursor = self.conn.execute(query)
        settings = {}
        
        for row in cursor.fetchall():
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
        self.conn.execute("""
            INSERT INTO audit_logs 
            (user_id, action, resource_type, resource_id, details, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?)
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
            query += " WHERE al.user_id = ?"
            params.append(user_id)
            
        query += " ORDER BY al.created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor = self.conn.execute(query, params)
        return cursor.fetchall()
        
    # ========== SESSION OPERATIONS ==========
    
    async def create_session(self, user_id: int, token_hash: str,
                           refresh_token_hash: str, expires_at: datetime,
                           ip_address: Optional[str] = None,
                           user_agent: Optional[str] = None) -> int:
        """Create user session"""
        cursor = self.conn.execute("""
            INSERT INTO sessions 
            (user_id, token_hash, refresh_token_hash, expires_at, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, token_hash, refresh_token_hash, expires_at, ip_address, user_agent))
        
        return cursor.lastrowid
        
    async def get_session_by_token(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """Get session by token hash"""
        cursor = self.conn.execute("""
            SELECT * FROM sessions 
            WHERE token_hash = ? AND is_active = 1 AND expires_at > CURRENT_TIMESTAMP
        """, (token_hash,))
        return cursor.fetchone()
        
    async def invalidate_session(self, session_id: int):
        """Invalidate session"""
        self.conn.execute(
            "UPDATE sessions SET is_active = 0 WHERE id = ?",
            (session_id,)
        )
        
    async def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        self.conn.execute(
            "DELETE FROM sessions WHERE expires_at < CURRENT_TIMESTAMP"
        )
    
    # Traffic History Methods
    
    async def save_traffic_history(self, proxy_name: str, date: str, interval_index: int, request_count: int):
        """Save or update traffic history for a specific interval"""
        self.conn.execute("""
            INSERT INTO traffic_history (proxy_name, date, interval_index, request_count, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(proxy_name, date, interval_index) 
            DO UPDATE SET 
                request_count = request_count + excluded.request_count,
                updated_at = CURRENT_TIMESTAMP
        """, (proxy_name, date, interval_index, request_count))
    
    async def get_traffic_history(self, proxy_name: str, date: str) -> List[int]:
        """Get traffic history for a proxy on a specific date (returns array of 288 intervals)"""
        cursor = self.conn.execute("""
            SELECT interval_index, request_count 
            FROM traffic_history 
            WHERE proxy_name = ? AND date = ?
            ORDER BY interval_index
        """, (proxy_name, date))
        
        results = cursor.fetchall()
        
        # Initialize 1440 intervals with 0 (1 minute each)
        history = [0] * 1440
        
        # Fill with actual data
        for row in results:
            if row['interval_index'] < 1440:
                history[row['interval_index']] = row['request_count']
        
        return history
    
    async def get_all_proxies_traffic_history(self, date: str) -> Dict[str, List[int]]:
        """Get traffic history for all proxies on a specific date"""
        cursor = self.conn.execute("""
            SELECT proxy_name, interval_index, request_count 
            FROM traffic_history 
            WHERE date = ?
            ORDER BY proxy_name, interval_index
        """, (date,))
        
        results = cursor.fetchall()
        
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
        self.conn.execute("""
            DELETE FROM traffic_history 
            WHERE date < DATE('now', '-' || ? || ' days')
        """, (days_to_keep,))

