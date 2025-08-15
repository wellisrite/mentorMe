from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as aioredis
import asyncio
import logging
import json
import hashlib
import os

# Configure logging
logger = logging.getLogger(__name__)

# Explicitly export these for use in other modules
__all__ = ['FastAPICache', 'cache_key_builder', 'init_cache']

REDIS_URL = os.getenv(
    "REDIS_URL", 
    "redis://redis:6379"
)

async def init_cache():
    """Initialize Redis cache connection with retries"""
    max_retries = 5
    retry_delay = 1  # seconds
    
    for attempt in range(max_retries):
        try:
            redis = aioredis.from_url(
                REDIS_URL,
                encoding="utf8",
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            # Test connection with timeout
            await asyncio.wait_for(redis.ping(), timeout=5.0)
            
            FastAPICache.init(
                RedisBackend(redis), 
                prefix="mentorme_cache:",
                key_builder=cache_key_builder
            )
            logger.info("Redis cache initialized successfully")
            return
            
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Redis connection attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"Failed to initialize Redis cache after {max_retries} attempts: {e}")

def cache_key_builder(func, *args, **kwargs):
    """Build cache key from function name and arguments"""
    try:
        # Include positional args (like job_id)
        safe_args = []
        for v in args:
            try:
                json.dumps(v)
                safe_args.append(v)
            except (TypeError, ValueError):
                continue

        # Remove non-serializable kwargs
        safe_kwargs = {}
        for k, v in kwargs.items():
            if k == 'db':  # Skip database connection
                continue
            try:
                json.dumps(v)
                safe_kwargs[k] = v
            except (TypeError, ValueError):
                continue

        prefix = f"{func.__module__}:{func.__name__}"

        key_parts = [str(a) for a in safe_args]
        for k in sorted(safe_kwargs.keys()):
            key_parts.append(f"{k}:{json.dumps(safe_kwargs[k], sort_keys=True)}")

        key_string = f"{prefix}:{':'.join(key_parts)}"

        if len(key_string) > 100:
            return f"{prefix}:{hashlib.sha256(key_string.encode()).hexdigest()}"

        return key_string
    except Exception as e:
        logger.error(f"Error building cache key: {e}")
        return f"{func.__module__}:{func.__name__}"
