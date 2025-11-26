"""
Script pour vérifier et initialiser la base de données ProxyOX
"""
import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from database.mysql_manager import MySQLDatabaseManager
import structlog

logger = structlog.get_logger()


async def check_and_init_database():
    """Vérifier et initialiser la base de données si nécessaire"""
    
    print("=" * 60)
    print("ProxyOX - Vérification Base de Données")
    print("=" * 60)
    print()
    
    # Load environment
    load_dotenv()
    
    # Initialize database
    db = MySQLDatabaseManager(
        host=os.getenv('MYSQL_HOST', 'localhost'),
        port=int(os.getenv('MYSQL_PORT', '3306')),
        user=os.getenv('MYSQL_USER', 'proxyox'),
        password=os.getenv('MYSQL_PASSWORD'),
        database=os.getenv('MYSQL_DATABASE', 'proxyox')
    )
    
    try:
        await db.connect()
        print("✅ Connecté à MySQL")
        print()
        
        # Check if tables exist
        tables = await db.fetchall("SHOW TABLES")
        
        if not tables:
            print("⚠️  Aucune table trouvée - Initialisation nécessaire")
            print()
            print("Initialisation de la base de données...")
            
            # Initialize database schema
            await db.initialize()
            
            print("✅ Base de données initialisée avec succès!")
            print()
            
            # Show created tables
            tables = await db.fetchall("SHOW TABLES")
            print(f"Tables créées ({len(tables)}):")
            for table in tables:
                table_name = list(table.values())[0]
                print(f"  ✓ {table_name}")
            print()
            
            # Create default admin user
            admin_password = os.getenv('ADMIN_PASSWORD', 'changeme')
            
            # Import hash_password
            from security.password import hash_password
            
            hashed_password = hash_password(admin_password)
            
            # Create admin user
            await db.execute("""
                INSERT INTO users (username, password_hash, email, role, is_active)
                VALUES (%s, %s, %s, %s, %s)
            """, ('admin', hashed_password, 'admin@proxyox.local', 'admin', True))
            
            print("✅ Utilisateur admin créé avec bcrypt")
            print(f"   Username: admin")
            print(f"   Password: {admin_password}")
            print()
            print("⚠️  IMPORTANT: Changez ce mot de passe après le premier login!")
            
        else:
            print(f"✅ Base de données déjà initialisée ({len(tables)} tables)")
            print()
            
            # List tables
            print("Tables existantes:")
            for table in tables:
                table_name = list(table.values())[0]
                
                # Count rows
                count_result = await db.fetchone(f"SELECT COUNT(*) as count FROM {table_name}")
                count = count_result['count'] if count_result else 0
                
                print(f"  ✓ {table_name} ({count} enregistrements)")
            print()
            
            # Check users
            users = await db.fetchall("SELECT username, email, role FROM users")
            
            if users:
                print(f"Utilisateurs ({len(users)}):")
                for user in users:
                    print(f"  - {user['username']} ({user['role']}) - {user['email']}")
            else:
                print("⚠️  Aucun utilisateur trouvé")
                print("Création de l'utilisateur admin...")
                
                from security.password import hash_password
                admin_password = os.getenv('ADMIN_PASSWORD', 'changeme')
                hashed_password = hash_password(admin_password)
                
                await db.execute("""
                    INSERT INTO users (username, password_hash, email, role, is_active)
                    VALUES (%s, %s, %s, %s, %s)
                """, ('admin', hashed_password, 'admin@proxyox.local', 'admin', True))
                
                print(f"✅ Utilisateur admin créé")
                print(f"   Username: admin")
                print(f"   Password: {admin_password}")
        
        print()
        print("=" * 60)
        print("✅ Vérification terminée")
        print("=" * 60)
        
    except Exception as e:
        logger.error("Erreur lors de la vérification", error=str(e))
        print(f"❌ Erreur: {e}")
        raise
    
    finally:
        await db.disconnect()
        print()
        print("Connexion fermée")


if __name__ == "__main__":
    asyncio.run(check_and_init_database())
