"""Authentication module for ProxyOX"""
import jwt
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
import structlog
from security.password import verify_password as bcrypt_verify_password, is_bcrypt_hash

logger = structlog.get_logger()

class AuthManager:
    """JWT-based authentication manager"""
    
    def __init__(self, db_manager, jwt_secret: str, jwt_expiry: int = 3600, refresh_expiry: int = 604800):
        """
        Initialize authentication manager
        
        Args:
            db_manager: Database manager instance
            jwt_secret: Secret key for JWT signing
            jwt_expiry: JWT token expiry in seconds (default 1 hour)
            refresh_expiry: Refresh token expiry in seconds (default 7 days)
        """
        self.db = db_manager
        self.jwt_secret = jwt_secret
        self.jwt_expiry = jwt_expiry
        self.refresh_expiry = refresh_expiry
        
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash password using SHA-256 (DEPRECATED - for backward compatibility only)
        Use security.password.hash_password() for new passwords
        """
        return hashlib.sha256(password.encode()).hexdigest()
        
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """
        Verify password against hash.
        Supports both bcrypt (new) and SHA-256 (legacy) hashes.
        """
        # Check if it's a bcrypt hash
        if is_bcrypt_hash(password_hash):
            return bcrypt_verify_password(password, password_hash)
        else:
            # Legacy SHA-256 support (will be removed after migration)
            return AuthManager.hash_password(password) == password_hash
        
    def generate_token(self, user_id: int, username: str) -> str:
        """Generate JWT access token"""
        payload = {
            'user_id': user_id,
            'username': username,
            'exp': datetime.utcnow() + timedelta(seconds=self.jwt_expiry),
            'iat': datetime.utcnow()
        }
        
        token = jwt.encode(payload, self.jwt_secret, algorithm='HS256')
        return token
        
    def generate_refresh_token(self) -> str:
        """Generate refresh token"""
        return secrets.token_urlsafe(32)
        
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token"""
        try:
            logger.info("Verifying token", token_preview=token[:30] if token else None, secret_preview=self.jwt_secret[:20] if self.jwt_secret else None)
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            logger.info("Token verified successfully", user_id=payload.get('user_id'), username=payload.get('username'))
            return payload
        except jwt.ExpiredSignatureError as e:
            logger.warning("Token expired", error=str(e))
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid token", error=str(e), token_preview=token[:30] if token else None)
            return None
        except Exception as e:
            logger.error("Token verification error", error=str(e), exc_info=True)
            return None
            
    async def authenticate(self, username: str, password: str, 
                          ip_address: Optional[str] = None,
                          user_agent: Optional[str] = None) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """
        Authenticate user and generate tokens
        
        Returns:
            Tuple of (access_token, refresh_token, user_data) or None
        """
        # Get user from database
        user = await self.db.get_user_by_username(username)
        
        if not user:
            logger.warning("User not found", username=username)
            return None
            
        # Verify password
        if not self.verify_password(password, user['password_hash']):
            logger.warning("Invalid password", username=username)
            return None
            
        # Generate tokens
        access_token = self.generate_token(user['id'], user['username'])
        refresh_token = self.generate_refresh_token()
        
        # Hash tokens for storage
        token_hash = hashlib.sha256(access_token.encode()).hexdigest()
        refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        
        # Create session
        expires_at = datetime.utcnow() + timedelta(seconds=self.refresh_expiry)
        await self.db.create_session(
            user_id=user['id'],
            token_hash=token_hash,
            refresh_token_hash=refresh_token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Update last login
        await self.db.update_user_last_login(user['id'])
        
        logger.info("User authenticated", username=username, user_id=user['id'])
        
        # Return tokens and safe user data
        user_data = {
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'role': user['role']
        }
        
        return (access_token, refresh_token, user_data)
        
    async def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """Refresh access token using refresh token"""
        refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        
        # Get session by refresh token (not access token)
        session = await self.db.get_session_by_refresh_token(refresh_token_hash)
        
        if not session:
            logger.warning("Invalid refresh token")
            return None
            
        # Get user
        user = await self.db.get_user_by_id(session['user_id'])
        
        if not user:
            logger.warning("User not found for session")
            return None
            
        # Generate new access token
        access_token = self.generate_token(user['id'], user['username'])
        
        logger.info("Access token refreshed", user_id=user['id'])
        
        return access_token
        
    async def logout(self, token: str):
        """Logout user by invalidating session"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        session = await self.db.get_session_by_token(token_hash)
        
        if session:
            await self.db.invalidate_session(session['id'])
            logger.info("User logged out", session_id=session['id'])
            
    async def verify_request(self, authorization_header: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Verify request authorization header
        
        Returns:
            User data if valid, None otherwise
        """
        if not authorization_header:
            logger.warning("No authorization header provided")
            return None
            
        try:
            parts = authorization_header.split(' ', 1)
            
            if len(parts) != 2:
                logger.warning("Invalid authorization header format", header=authorization_header[:50])
                return None
                
            scheme, token = parts
            
            if scheme.lower() != 'bearer':
                logger.warning("Invalid authorization scheme", scheme=scheme)
                return None
                
            # Verify token
            payload = self.verify_token(token)
            
            if not payload:
                logger.warning("Token verification failed")
                return None
                
            # Get user
            user = await self.db.get_user_by_id(payload['user_id'])
            
            if not user:
                logger.warning("User not found for token", user_id=payload.get('user_id'))
                return None
            
            logger.info("Request verified successfully", user_id=user['id'], username=user['username'])
            
            return {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'role': user['role']
            }
            
        except Exception as e:
            logger.error("Error verifying request", error=str(e), exc_info=True)
            return None
            
    async def require_auth(self, request) -> Optional[Dict[str, Any]]:
        """Middleware helper to require authentication"""
        auth_header = request.headers.get('Authorization')
        return await self.verify_request(auth_header)
