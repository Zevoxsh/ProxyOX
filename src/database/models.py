"""Database models for ProxyOX"""
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any
import json

class BaseModel:
    """Base model with common methods"""
    
    @staticmethod
    def dict_factory(cursor, row):
        """Convert sqlite3.Row to dict"""
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

class User:
    """User model for authentication"""
    
    TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'admin',
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """
    
    @staticmethod
    def create_indexes(conn):
        """Create indexes for users table"""
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")

class Proxy:
    """Proxy (Frontend) configuration model"""
    
    TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS proxies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            bind_address TEXT NOT NULL,
            bind_port INTEGER NOT NULL,
            mode TEXT NOT NULL CHECK(mode IN ('http', 'tcp', 'udp')),
            default_backend_id INTEGER,
            is_enabled BOOLEAN DEFAULT 1,
            max_connections INTEGER DEFAULT 100,
            rate_limit INTEGER DEFAULT 1000,
            timeout INTEGER DEFAULT 300,
            use_ssl BOOLEAN DEFAULT 0,
            ssl_cert_path TEXT,
            ssl_key_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (default_backend_id) REFERENCES backends(id) ON DELETE SET NULL
        )
    """
    
    @staticmethod
    def create_indexes(conn):
        """Create indexes for proxies table"""
        conn.execute("CREATE INDEX IF NOT EXISTS idx_proxies_name ON proxies(name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_proxies_enabled ON proxies(is_enabled)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_proxies_mode ON proxies(mode)")

class Backend:
    """Backend server configuration model"""
    
    TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS backends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            server_address TEXT NOT NULL,
            server_port INTEGER NOT NULL,
            use_https BOOLEAN DEFAULT 0,
            is_enabled BOOLEAN DEFAULT 1,
            health_check_enabled BOOLEAN DEFAULT 0,
            health_check_interval INTEGER DEFAULT 30,
            health_check_path TEXT DEFAULT '/',
            weight INTEGER DEFAULT 1,
            max_connections INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    
    @staticmethod
    def create_indexes(conn):
        """Create indexes for backends table"""
        conn.execute("CREATE INDEX IF NOT EXISTS idx_backends_name ON backends(name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_backends_enabled ON backends(is_enabled)")

class DomainRoute:
    """Domain routing configuration model"""
    
    TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS domain_routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proxy_id INTEGER NOT NULL,
            domain TEXT NOT NULL,
            backend_id INTEGER NOT NULL,
            priority INTEGER DEFAULT 0,
            is_enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (proxy_id) REFERENCES proxies(id) ON DELETE CASCADE,
            FOREIGN KEY (backend_id) REFERENCES backends(id) ON DELETE CASCADE,
            UNIQUE(proxy_id, domain)
        )
    """
    
    @staticmethod
    def create_indexes(conn):
        """Create indexes for domain_routes table"""
        conn.execute("CREATE INDEX IF NOT EXISTS idx_domain_routes_proxy ON domain_routes(proxy_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_domain_routes_domain ON domain_routes(domain)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_domain_routes_backend ON domain_routes(backend_id)")

class IPFilter:
    """IP filtering configuration model"""
    
    TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS ip_filters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            filter_type TEXT NOT NULL CHECK(filter_type IN ('blacklist', 'whitelist')),
            proxy_id INTEGER,
            reason TEXT,
            is_enabled BOOLEAN DEFAULT 1,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (proxy_id) REFERENCES proxies(id) ON DELETE CASCADE,
            UNIQUE(ip_address, filter_type, proxy_id)
        )
    """
    
    @staticmethod
    def create_indexes(conn):
        """Create indexes for ip_filters table"""
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ip_filters_ip ON ip_filters(ip_address)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ip_filters_type ON ip_filters(filter_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ip_filters_proxy ON ip_filters(proxy_id)")

class Setting:
    """Global settings model"""
    
    TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL,
            value_type TEXT DEFAULT 'string' CHECK(value_type IN ('string', 'int', 'float', 'bool', 'json')),
            description TEXT,
            is_secret BOOLEAN DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by INTEGER,
            FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
        )
    """
    
    @staticmethod
    def create_indexes(conn):
        """Create indexes for settings table"""
        conn.execute("CREATE INDEX IF NOT EXISTS idx_settings_key ON settings(key)")

class AuditLog:
    """Audit log for tracking admin actions"""
    
    TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id INTEGER,
            details TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """
    
    @staticmethod
    def create_indexes(conn):
        """Create indexes for audit_logs table"""
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource_type, resource_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at)")

class ProxyStats:
    """Real-time proxy statistics model"""
    
    TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS proxy_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proxy_id INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            connections_total INTEGER DEFAULT 0,
            connections_active INTEGER DEFAULT 0,
            bytes_sent INTEGER DEFAULT 0,
            bytes_received INTEGER DEFAULT 0,
            requests_total INTEGER DEFAULT 0,
            requests_failed INTEGER DEFAULT 0,
            response_time_avg REAL DEFAULT 0,
            FOREIGN KEY (proxy_id) REFERENCES proxies(id) ON DELETE CASCADE
        )
    """
    
    @staticmethod
    def create_indexes(conn):
        """Create indexes for proxy_stats table"""
        conn.execute("CREATE INDEX IF NOT EXISTS idx_proxy_stats_proxy ON proxy_stats(proxy_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_proxy_stats_timestamp ON proxy_stats(timestamp)")

class TrafficHistory:
    """Traffic history model for 24-hour graphs (5-minute intervals)"""
    
    TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS traffic_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proxy_name TEXT NOT NULL,
            date DATE NOT NULL,
            interval_index INTEGER NOT NULL,
            request_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(proxy_name, date, interval_index)
        )
    """
    
    @staticmethod
    def create_indexes(conn):
        """Create indexes for traffic_history table"""
        conn.execute("CREATE INDEX IF NOT EXISTS idx_traffic_proxy ON traffic_history(proxy_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_traffic_date ON traffic_history(date)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_traffic_unique ON traffic_history(proxy_name, date, interval_index)")

class Session:
    """User session model for JWT token management"""
    
    TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT UNIQUE NOT NULL,
            refresh_token_hash TEXT UNIQUE,
            ip_address TEXT,
            user_agent TEXT,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """
    
    @staticmethod
    def create_indexes(conn):
        """Create indexes for sessions table"""
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(is_active)")
