"""Rate limiter for preventing brute force attacks."""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import asyncio


class RateLimiter:
    """
    Rate limiter for preventing brute force attacks.
    
    Tracks attempts per identifier (e.g., IP address) and blocks
    after max_attempts within the time window.
    """
    
    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        """
        Initialize rate limiter.
        
        Args:
            max_attempts: Maximum allowed attempts in window
            window_seconds: Time window in seconds (default: 5 minutes)
        """
        self.max_attempts = max_attempts
        self.window = timedelta(seconds=window_seconds)
        self.window_seconds = window_seconds
        
        # Track attempts: identifier -> list of attempt timestamps
        self.attempts: Dict[str, List[datetime]] = defaultdict(list)
        
        # Track blocked identifiers: identifier -> blocked until timestamp
        self.blocked: Dict[str, datetime] = {}
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, identifier: str) -> bool:
        """
        Check if identifier is allowed to make request.
        
        Args:
            identifier: Unique identifier (e.g., IP address, username)
            
        Returns:
            True if allowed, False if blocked
        """
        async with self._lock:
            now = datetime.now()
            
            # Check if currently blocked
            if identifier in self.blocked:
                if now < self.blocked[identifier]:
                    # Still blocked
                    return False
                else:
                    # Block expired, remove
                    del self.blocked[identifier]
            
            # Clean old attempts outside window
            self.attempts[identifier] = [
                timestamp for timestamp in self.attempts[identifier]
                if now - timestamp < self.window
            ]
            
            # Check if limit reached
            if len(self.attempts[identifier]) >= self.max_attempts:
                # Block identifier
                self.blocked[identifier] = now + self.window
                return False
            
            # Record this attempt
            self.attempts[identifier].append(now)
            return True
    
    async def remaining_attempts(self, identifier: str) -> int:
        """
        Get remaining attempts for identifier.
        
        Args:
            identifier: Unique identifier
            
        Returns:
            Number of remaining attempts (0 if blocked)
        """
        async with self._lock:
            now = datetime.now()
            
            # Clean old attempts
            self.attempts[identifier] = [
                timestamp for timestamp in self.attempts[identifier]
                if now - timestamp < self.window
            ]
            
            return max(0, self.max_attempts - len(self.attempts[identifier]))
    
    async def get_block_info(self, identifier: str) -> Optional[Tuple[int, datetime]]:
        """
        Get blocking information for identifier.
        
        Args:
            identifier: Unique identifier
            
        Returns:
            Tuple of (attempts_count, blocked_until) if blocked, None otherwise
        """
        async with self._lock:
            now = datetime.now()
            
            if identifier in self.blocked and now < self.blocked[identifier]:
                return (
                    len(self.attempts[identifier]),
                    self.blocked[identifier]
                )
            
            return None
    
    async def reset(self, identifier: str) -> None:
        """
        Reset attempts and block for identifier.
        
        Args:
            identifier: Unique identifier
        """
        async with self._lock:
            if identifier in self.attempts:
                del self.attempts[identifier]
            if identifier in self.blocked:
                del self.blocked[identifier]
    
    async def clear_all(self) -> None:
        """Clear all attempts and blocks."""
        async with self._lock:
            self.attempts.clear()
            self.blocked.clear()
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics.
        
        Returns:
            Dictionary with 'total_tracked', 'blocked_count'
        """
        return {
            'total_tracked': len(self.attempts),
            'blocked_count': len(self.blocked),
        }
