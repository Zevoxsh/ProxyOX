"""Password hashing and verification using bcrypt."""

import bcrypt
from typing import Optional


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt with 12 rounds.
    
    Args:
        password: Plain text password to hash
        
    Returns:
        Hashed password string (bcrypt format)
        
    Raises:
        ValueError: If password is empty
    """
    if not password:
        raise ValueError("Password cannot be empty")
    
    # Generate salt with 12 rounds (good balance of security/performance)
    salt = bcrypt.gensalt(rounds=12)
    
    # Hash password
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    
    # Return as string
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a password against a bcrypt hash.
    
    Args:
        password: Plain text password to verify
        hashed: Bcrypt hash to verify against
        
    Returns:
        True if password matches hash, False otherwise
    """
    if not password or not hashed:
        return False
    
    try:
        return bcrypt.checkpw(
            password.encode('utf-8'),
            hashed.encode('utf-8')
        )
    except (ValueError, Exception):
        # Invalid hash format or other error
        return False


def is_bcrypt_hash(hash_string: str) -> bool:
    """
    Check if a string is a valid bcrypt hash.
    
    Args:
        hash_string: String to check
        
    Returns:
        True if string appears to be a bcrypt hash
    """
    if not hash_string:
        return False
    
    # Bcrypt hashes start with $2a$, $2b$, or $2y$
    return hash_string.startswith(('$2a$', '$2b$', '$2y$'))
