"""
Cost-based limiting system for tracking and limiting spending on LLM API calls.

This module provides per-user and global cost tracking with configurable time periods,
separate from request-based rate limiting.
"""
import redis
import hashlib
import logging
from fastapi import WebSocket
from app.config import settings

logger = logging.getLogger(__name__)


def get_ip_identifier(websocket: WebSocket) -> str:
    """Get IP identifier for cost tracking (reuses IP logic from rate limiter)."""
    # Get real IP, handling proxies and load balancers
    real_ip = (
        (websocket.client.host if websocket.client else "unknown") or
        websocket.headers.get("x-forwarded-for", "").split(",")[0].strip() or
        websocket.headers.get("x-real-ip", "") or
        websocket.headers.get("cf-connecting-ip", "") or  # Cloudflare
        websocket.headers.get("x-original-forwarded-for", "")  # Additional proxy header
    )
    
    # Normalize IP address (handle IPv4 and IPv6)
    normalized_ip = real_ip[:45] if real_ip else "unknown"
    
    # Create secure IP-only hash
    return hashlib.sha256(normalized_ip.encode()).hexdigest()[:32]


class IPCostLimiter:
    """Per-IP cost tracking with configurable time periods."""
    
    def __init__(self, redis_client: redis.Redis, max_cost: float = 1.0, period_seconds: int = 168):
        self.redis = redis_client
        self.max_cost = max_cost
        self.period_seconds = period_seconds
    
    def _get_ip_key(self, ip_identifier: str) -> str:
        """Generate Redis key for IP cost tracking."""
        return f"cost_limit:ip:{ip_identifier}"
    
    def is_within_limits(self, ip_identifier: str) -> bool:
        """Check if IP is within their cost limit for current period."""
        key = self._get_ip_key(ip_identifier)
        
        try:
            current_cost = float(self.redis.get(key) or 0)
            return current_cost < self.max_cost
        except Exception as e:
            logger.error(f"Redis error checking user cost limit: {e}")
            # Fail open for cost limits - allow request if Redis fails
            return True
    
    def record_cost(self, ip_identifier: str, actual_cost: float):
        """Record actual cost for IP with TTL management."""
        if actual_cost <= 0:
            return
            
        key = self._get_ip_key(ip_identifier)
        
        try:
            # Check if key exists to determine if we need to set TTL
            current_cost = self.redis.get(key)
            
            if current_cost is None:
                # First cost record - set both value and TTL
                self.redis.set(key, actual_cost, ex=self.period_seconds)
                logger.debug(f"First cost record for IP {ip_identifier[:8]}...: ${actual_cost:.6f} (TTL: {self.period_seconds}s)")
            else:
                # Key exists - just increment (preserves existing TTL)
                self.redis.incrbyfloat(key, actual_cost)
                logger.debug(f"Added cost for IP {ip_identifier[:8]}...: ${actual_cost:.6f}")
                
        except Exception as e:
            logger.error(f"Error recording IP cost: {e}")
    
    def get_current_usage(self, ip_identifier: str) -> float:
        """Get current cost usage for IP in current period."""
        key = self._get_ip_key(ip_identifier)
        try:
            return float(self.redis.get(key) or 0)
        except Exception as e:
            logger.error(f"Error getting IP cost usage: {e}")
            return 0.0


class GlobalCostLimiter:
    """Global cost tracking across all users with configurable time periods."""
    
    def __init__(self, redis_client: redis.Redis, max_cost: float = 10.0, period_seconds: int = 8760):
        self.redis = redis_client
        self.max_cost = max_cost
        self.period_seconds = period_seconds
    
    def _get_global_key(self) -> str:
        """Generate Redis key for global cost tracking."""
        return "cost_limit:global"
    
    def is_within_limits(self) -> bool:
        """Check if global system is within cost limit for current period."""
        key = self._get_global_key()
        
        try:
            current_cost = float(self.redis.get(key) or 0)
            return current_cost < self.max_cost
        except Exception as e:
            logger.error(f"Redis error checking global cost limit: {e}")
            # Fail open for cost limits - allow request if Redis fails
            return True
    
    def record_cost(self, actual_cost: float):
        """Record actual cost globally with TTL management."""
        if actual_cost <= 0:
            return
            
        key = self._get_global_key()
        
        try:
            # Check if key exists to determine if we need to set TTL
            current_cost = self.redis.get(key)
            
            if current_cost is None:
                # First global cost record - set both value and TTL
                self.redis.set(key, actual_cost, ex=self.period_seconds)
                logger.debug(f"First global cost record: ${actual_cost:.6f} (TTL: {self.period_seconds}s)")
            else:
                # Key exists - just increment (preserves existing TTL)
                self.redis.incrbyfloat(key, actual_cost)
                logger.debug(f"Added global cost: ${actual_cost:.6f}")
                
        except Exception as e:
            logger.error(f"Error recording global cost: {e}")
    
    def get_current_usage(self) -> float:
        """Get current global cost usage in current period."""
        key = self._get_global_key()
        try:
            return float(self.redis.get(key) or 0)
        except Exception as e:
            logger.error(f"Error getting global cost usage: {e}")
            return 0.0


class CostLimiter:
    """Main cost limiter combining IP and global cost tracking."""
    
    def __init__(self, redis_client: redis.Redis):
        """Initialize with settings from config."""
        self.ip_limiter = IPCostLimiter(
            redis_client,
            max_cost=settings.per_user_cost_limit,
            period_seconds=settings.per_user_cost_period_seconds
        )
        self.global_limiter = GlobalCostLimiter(
            redis_client,
            max_cost=settings.global_cost_limit,
            period_seconds=settings.global_cost_period_seconds
        )
    
    def is_allowed(self, websocket: WebSocket) -> bool:
        """Check if request is allowed based on both IP and global cost limits."""
        ip_identifier = get_ip_identifier(websocket)
        
        # Check global limit first (most restrictive)
        if not self.global_limiter.is_within_limits():
            logger.warning(f"Global cost limit exceeded: {self.global_limiter.get_current_usage():.6f} >= {self.global_limiter.max_cost}")
            return False
        
        # Check IP limit
        if not self.ip_limiter.is_within_limits(ip_identifier):
            logger.warning(f"IP cost limit exceeded for {ip_identifier[:8]}...: {self.ip_limiter.get_current_usage(ip_identifier):.6f} >= {self.ip_limiter.max_cost}")
            return False
        
        return True
    
    def record_cost(self, websocket: WebSocket, actual_cost: float):
        """Record actual cost for both IP and global tracking."""
        if actual_cost <= 0:
            return
            
        ip_identifier = get_ip_identifier(websocket)
        
        self.ip_limiter.record_cost(ip_identifier, actual_cost)
        self.global_limiter.record_cost(actual_cost)
        
        logger.info(f"Recorded cost ${actual_cost:.6f} for IP {ip_identifier[:8]}...")