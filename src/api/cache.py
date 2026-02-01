"""
Redis cache utilities for API.
"""
import json
import logging
from typing import Optional, Any

from config.settings import settings

logger = logging.getLogger(__name__)

_redis_client = None
_cache_wrapper = None
_redis_checked = False


def cache_key(*args) -> str:
    """
    Generate a cache key from arguments.

    Args:
        *args: Key components

    Returns:
        Cache key string
    """
    return ":".join(str(a) for a in args)


class CacheWrapper:
    """
    Wrapper for Redis client with JSON serialization.
    """

    def __init__(self, client):
        self.client = client

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None

    def set(self, key: str, value: Any, ex: Optional[int] = None):
        """Set value in cache."""
        try:
            self.client.set(key, json.dumps(value), ex=ex)
        except Exception as e:
            logger.warning(f"Cache set error: {e}")

    def delete(self, key: str):
        """Delete value from cache."""
        try:
            self.client.delete(key)
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")

    def ping(self):
        """Check connection."""
        return self.client.ping()


def get_cache() -> Optional[CacheWrapper]:
    """
    Get wrapped Redis cache client.

    Returns None if Redis is disabled or unavailable.
    Caches the result to avoid repeated connection attempts.
    """
    global _redis_client, _cache_wrapper, _redis_checked

    if not settings.database.redis_enabled:
        return None

    # Return cached wrapper if already initialized
    if _cache_wrapper is not None:
        return _cache_wrapper

    # If we already checked and failed, don't retry
    if _redis_checked:
        return None

    _redis_checked = True

    try:
        import redis
        _redis_client = redis.from_url(
            settings.database.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,  # Fast timeout
            socket_timeout=2,
        )
        # Test connection
        _redis_client.ping()
        logger.info("Redis cache connected")
        _cache_wrapper = CacheWrapper(_redis_client)
        return _cache_wrapper
    except ImportError:
        logger.warning("Redis package not installed, caching disabled")
        return None
    except Exception as e:
        logger.warning(f"Failed to connect to Redis: {e}")
        return None


def is_redis_connected() -> bool:
    """Check if Redis is connected without attempting reconnection."""
    return _cache_wrapper is not None
