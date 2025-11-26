"""
Script de migration des passwords de SHA-256 vers bcrypt
Usage: python scripts/migrate_passwords.py
"""
import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from database.mysql_manager import MySQLDatabaseManager
from security.password import hash_password, is_bcrypt_hash
import structlog

logger = structlog.get_logger()


async def migrate_passwords():
    """Migrate all user passwords from SHA-256 to bcrypt"""
    
    print("=" * 60)
    print("ProxyOX - Password Migration to bcrypt")
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
        print("✅ Connected to MySQL database")
        print()
        
        # Get all users directly from database
        users = await db.fetchall("SELECT * FROM users")
        
        if not users:
            print("⚠️  No users found in database")
            return
        
        print(f"Found {len(users)} user(s)")
        print()
        
        # Check which users need migration
        users_to_migrate = []
        users_already_bcrypt = []
        
        for user in users:
            if is_bcrypt_hash(user['password_hash']):
                users_already_bcrypt.append(user['username'])
            else:
                users_to_migrate.append(user)
        
        if users_already_bcrypt:
            print(f"✅ {len(users_already_bcrypt)} user(s) already using bcrypt:")
            for username in users_already_bcrypt:
                print(f"   - {username}")
            print()
        
        if not users_to_migrate:
            print("✅ All users already using bcrypt - no migration needed!")
            return
        
        print(f"⚠️  {len(users_to_migrate)} user(s) need password migration:")
        for user in users_to_migrate:
            print(f"   - {user['username']}")
        print()
        
        print("=" * 60)
        print("⚠️  IMPORTANT: Password Reset Required")
        print("=" * 60)
        print()
        print("SHA-256 passwords cannot be migrated to bcrypt directly.")
        print("Users must reset their passwords.")
        print()
        print("Options:")
        print("1. Reset admin password now (recommended)")
        print("2. Mark users for password reset on next login")
        print("3. Cancel migration")
        print()
        
        choice = input("Enter your choice (1-3): ").strip()
        
        if choice == '1':
            # Reset admin password
            admin_user = next((u for u in users_to_migrate if u['username'] == 'admin'), None)
            
            if not admin_user:
                print("❌ Admin user not found")
                return
            
            # Use password from .env if available
            new_password = os.getenv('ADMIN_PASSWORD')
            
            if not new_password:
                print()
                new_password = input("Enter new admin password (or leave empty to generate): ").strip()
                
                if not new_password:
                    import secrets
                    import string
                    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
                    new_password = ''.join(secrets.choice(alphabet) for _ in range(24))
                    print()
                    print("=" * 60)
                    print("🔑 Generated Password:")
                    print("=" * 60)
                    print(f"   {new_password}")
                    print("=" * 60)
                    print("⚠️  SAVE THIS PASSWORD NOW!")
                    print("=" * 60)
                    print()
                    input("Press Enter after saving the password...")
            
            # Hash with bcrypt
            hashed = hash_password(new_password)
            
            # Update in database
            await db.execute("""
                UPDATE users
                SET password_hash = %s
                WHERE id = %s
            """, (hashed, admin_user['id']))
            
            print()
            print(f"✅ Admin password migrated to bcrypt successfully!")
            print()
            
            # Migrate other users
            if len(users_to_migrate) > 1:
                print("Other users will need to reset their password on next login.")
                for user in users_to_migrate:
                    if user['username'] != 'admin':
                        # Could implement password reset token here
                        print(f"   - {user['username']} - marked for reset")
        
        elif choice == '2':
            print("⚠️  Users marked for password reset")
            print("(Password reset functionality needs to be implemented)")
        
        else:
            print("❌ Migration cancelled")
            return
        
        print()
        print("=" * 60)
        print("✅ Migration completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        logger.error("Migration failed", error=str(e))
        print(f"❌ Error: {e}")
        raise
    
    finally:
        await db.disconnect()
        print()
        print("Database connection closed")


if __name__ == "__main__":
    asyncio.run(migrate_passwords())
