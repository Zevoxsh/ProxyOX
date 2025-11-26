"""Database module for ProxyOX"""
from .mysql_manager import MySQLDatabaseManager
from .models import User, Proxy, Backend, DomainRoute, IPFilter, Setting, AuditLog

# Maintain backward compatibility (deprecated)
DatabaseManager = MySQLDatabaseManager

__all__ = [
    'MySQLDatabaseManager',
    'DatabaseManager',  # Deprecated, use MySQLDatabaseManager
    'User',
    'Proxy',
    'Backend',
    'DomainRoute',
    'IPFilter',
    'Setting',
    'AuditLog'
]

