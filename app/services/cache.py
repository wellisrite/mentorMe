
# app/services/cache.py
"""
Centralized caching service for the Career Mirror API
"""

import json
import logging
import hashlib
from typing import Any, Optional, Dict, List
from functools import wraps
import redis.asyncio as redis
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CacheConfig:
    """Cache configuration constants"""
    PROFILE_TTL = 300      # 5 minutes - profiles don't change often
    JOB_TTL = 600         # 10 minutes - jobs are relatively stable
    MATCH_TTL = 1800      # 30 minutes - matches are expensive to compute
    SEARCH_TTL = 180      # 3 minutes - search results
    HEALTH_TTL = 60       # 1 minute - health checks
    DEFAULT_TTL = 300     # 5 minutes default

class CacheService:
    """Centralized cache service using Redis"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_pool: Optional[redis.Redis] = None
        self.redis_url = redis_url
        self._connected = False
    
    async def connect(self):
        """Initialize Redis connection"""
        try:
            self.redis_pool = redis.from_url(
                self.redis_url, 
                decode_responses=True,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            await self.redis_pool.ping()
            self._connected = True
            logger.info("Cache service connected successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to cache: {e}")
            self._connected = False
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.redis_pool:
            await self.redis_pool.aclose()
            self._connected = False
            logger.info("Cache service disconnected")
    
    async def is_healthy(self) -> bool:
        """Check if cache is healthy"""
        if not self._connected or not self.redis_pool:
            return False
        
        try:
            await self.redis_pool.ping()
            return True
        except Exception:
            return False
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not await self.is_healthy():
            return None
        
        try:
            cached_data = await self.redis_pool.get(key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = CacheConfig.DEFAULT_TTL):
        """Set value in cache"""
        if not await self.is_healthy():
            return False
        
        try:
            serialized = json.dumps(value, default=str, ensure_ascii=False)
            await self.redis_pool.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str):
        """Delete key from cache"""
        if not await self.is_healthy():
            return False
        
        try:
            await self.redis_pool.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def delete_pattern(self, pattern: str):
        """Delete all keys matching pattern"""
        if not await self.is_healthy():
            return False
        
        try:
            keys = await self.redis_pool.keys(pattern)
            if keys:
                await self.redis_pool.delete(*keys)
                logger.info(f"Deleted {len(keys)} keys matching pattern: {pattern}")
            return True
        except Exception as e:
            logger.error(f"Cache delete pattern error for {pattern}: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not await self.is_healthy():
            return {"status": "disconnected"}
        
        try:
            info = await self.redis_pool.info()
            return {
                "status": "connected",
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0)
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"status": "error", "error": str(e)}

# Global cache instance
cache_service = CacheService()

def build_cache_key(prefix: str, *args, **kwargs) -> str:
    """Build standardized cache key"""
    try:
        key_parts = [prefix]
        
        # Add positional args (typically IDs)
        for arg in args:
            if isinstance(arg, (int, str, float)):
                key_parts.append(str(arg))
        
        # Add relevant kwargs
        relevant_kwargs = {
            k: v for k, v in kwargs.items() 
            if k in ['profile_id', 'job_id', 'limit', 'offset', 'search_term']
        }
        
        for key in sorted(relevant_kwargs.keys()):
            key_parts.append(f"{key}:{relevant_kwargs[key]}")
        
        cache_key = ":".join(key_parts)
        
        # Hash if too long
        if len(cache_key) > 100:
            hash_suffix = hashlib.sha256(cache_key.encode()).hexdigest()[:16]
            return f"{prefix}:{hash_suffix}"
        
        return cache_key
        
    except Exception as e:
        logger.error(f"Error building cache key: {e}")
        return f"{prefix}:error"

def cached(ttl: int = CacheConfig.DEFAULT_TTL, prefix: str = ""):
    """Caching decorator for async functions"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key
            cache_key = build_cache_key(
                prefix or func.__name__,
                *args, **kwargs
            )
            
            # Try cache first
            cached_result = await cache_service.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_result
            
            # Execute function
            logger.debug(f"Cache miss: {cache_key}")
            result = await func(*args, **kwargs)
            
            # Cache the result
            if result is not None:
                await cache_service.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator

# Initialize cache function for main.py
async def init_cache():
    """Initialize cache service"""
    await cache_service.connect()

# Cleanup function for main.py
async def cleanup_cache():
    """Cleanup cache service"""
    await cache_service.disconnect()