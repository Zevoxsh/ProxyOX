"""
ProxyOX - Professional Proxy Server with Database Backend
"""
import asyncio
import structlog
import logging
import sys
from pathlib import Path
from aiohttp import web

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.proxy.manager import ProxyManager
from src.dashboard.app import Dashboard
from src.database.mysql_manager import MySQLDatabaseManager
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.KeyValueRenderer(key_order=['timestamp', 'level', 'event'])
    ]
)

logger = structlog.get_logger()

async def load_config_from_db(manager: ProxyManager, db: MySQLDatabaseManager):
    """Load proxy configuration from database"""
    logger.info("Loading configuration from database")
    
    # Get global settings
    settings = await db.list_settings(include_secrets=False)
    
    # Get all proxies
    proxies = await db.list_proxies(enabled_only=True)
    backends_list = await db.list_backends(enabled_only=True)
    
    # Create backend map
    backend_map = {b['id']: b for b in backends_list}
    
    logger.info("Configuration loaded", 
               proxies_count=len(proxies),
               backends_count=len(backends_list))
    
    # Start each proxy
    for proxy in proxies:
        try:
            mode = proxy['mode'].lower()
            bind_address = proxy['bind_address']
            bind_port = proxy['bind_port']
            
            # Get default backend if configured
            default_backend = None
            if proxy.get('default_backend_id'):
                backend = backend_map.get(proxy['default_backend_id'])
                if backend:
                    default_backend = f"{backend['server_address']}:{backend['server_port']}"
            
            # Get domain routes for this proxy
            domain_routes = await db.list_domain_routes(proxy['id'])
            
            # Build domain_routes dict for HTTP mode
            routes_dict = {}
            if mode == 'http' and domain_routes:
                for route in domain_routes:
                    backend = backend_map.get(route['backend_id'])
                    if backend:
                        routes_dict[route['domain']] = {
                            'host': backend['server_address'],
                            'port': backend['server_port'],
                            'https': backend.get('use_https', False)
                        }
            
            # Get IP filters for this proxy
            blacklist_filters = await db.list_ip_filters('blacklist', proxy['id'])
            whitelist_filters = await db.list_ip_filters('whitelist', proxy['id'])
            
            blacklist_ips = [f['ip_address'] for f in blacklist_filters]
            whitelist_ips = [f['ip_address'] for f in whitelist_filters]
            
            # Start the proxy
            logger.info("Starting proxy",
                       name=proxy['name'],
                       mode=mode,
                       bind=f"{bind_address}:{bind_port}",
                       default_backend=default_backend,
                       domain_routes_count=len(routes_dict),
                       blacklist_count=len(blacklist_ips),
                       whitelist_count=len(whitelist_ips))
            
            await manager.start_proxy(
                name=proxy['name'],
                mode=mode,
                bind_address=bind_address,
                bind_port=bind_port,
                backend_address=default_backend,
                domain_routes=routes_dict if routes_dict else None,
                max_connections=proxy.get('max_connections', 100),
                rate_limit=proxy.get('rate_limit', 1000),
                timeout=proxy.get('timeout', 300),
                backend_ssl=proxy.get('use_ssl', False),
                use_https=proxy.get('use_ssl', False),  # SSL côté client
                blacklist=blacklist_ips if blacklist_ips else None,
                whitelist=whitelist_ips if whitelist_ips else None
            )
            
        except Exception as e:
            logger.error("Failed to start proxy",
                        proxy=proxy['name'],
                        error=str(e))

async def main():
    """Main entrypoint for ProxyOX"""
    logger.info("="*60)
    logger.info("Starting ProxyOX - Professional Proxy Server")
    logger.info("="*60)
    
    # Get MySQL connection parameters from environment
    mysql_host = os.getenv("MYSQL_HOST", "localhost")
    mysql_port = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_user = os.getenv("MYSQL_USER", "proxyox")
    mysql_password = os.getenv("MYSQL_PASSWORD", "proxyox")
    mysql_database = os.getenv("MYSQL_DATABASE", "proxyox")
    
    # Initialize MySQL database
    db = MySQLDatabaseManager(
        host=mysql_host,
        port=mysql_port,
        user=mysql_user,
        password=mysql_password,
        database=mysql_database
    )
    await db.initialize()
    
    # Initialize proxy manager
    manager = ProxyManager()
    manager.db = db  # Attach database to manager for runtime operations
    
    # Load and start proxies from database
    await load_config_from_db(manager, db)
    
    # Initialize dashboard
    dashboard = Dashboard(manager, mysql_host, mysql_port, mysql_user, mysql_password, mysql_database)
    await dashboard.initialize()
    
    # Get dashboard settings
    dashboard_host = await db.get_setting('DASHBOARD_HOST') or '0.0.0.0'
    dashboard_port = await db.get_setting('DASHBOARD_PORT') or 9090
    
    logger.info("Starting dashboard",
               host=dashboard_host,
               port=dashboard_port)
    
    # Start dashboard server
    runner = web.AppRunner(dashboard.app)
    await runner.setup()
    site = web.TCPSite(runner, dashboard_host, dashboard_port)
    
    try:
        await site.start()
        
        logger.info("="*60)
        logger.info("ProxyOX is running!")
        logger.info(f"Dashboard: http://{dashboard_host}:{dashboard_port}")
        logger.info("Login credentials:")
        logger.info("  Username: admin")
        logger.info("  Password: changeme")
        logger.info("="*60)
        logger.info("Press Ctrl+C to stop")
        logger.info("="*60)
        
        # Keep running
        await asyncio.Event().wait()
        
    except KeyboardInterrupt:
        logger.info("Shutting down ProxyOX...")
    finally:
        # Stop all proxies
        await manager.stop_all()
        
        # Cleanup
        await runner.cleanup()
        await db.disconnect()
        
        logger.info("ProxyOX stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
