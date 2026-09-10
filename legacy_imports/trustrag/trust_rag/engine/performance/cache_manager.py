"""
Cache Manager for GraphRAG.

This module provides multi-level caching to optimize response times and reduce
computational overhead across different system components.
"""

import logging
from typing import Dict, List, Any, Optional, Callable, Union
import time
import threading
import hashlib
import pickle
from collections import OrderedDict
import redis
import psutil
from pathlib import Path

logger = logging.getLogger(__name__)


class LRUCache:
    """Simple LRU cache implementation."""

    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self.cache = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        with self.lock:
            if key in self.cache:
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                return self.cache[key]
            return None

    def put(self, key: str, value: Any):
        """Put item in cache."""
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            else:
                if len(self.cache) >= self.capacity:
                    # Remove least recently used
                    self.cache.popitem(last=False)

            self.cache[key] = value

    def remove(self, key: str) -> bool:
        """Remove item from cache."""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False

    def clear(self):
        """Clear all cache entries."""
        with self.lock:
            self.cache.clear()

    def size(self) -> int:
        """Get cache size."""
        with self.lock:
            return len(self.cache)


class CacheManager:
    """
    Multi-level cache manager with memory, Redis, and disk caching.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize cache manager.

        Args:
            config: Cache configuration
        """
        self.config = config or {}

        # Cache levels
        self.enable_memory_cache = self.config.get('enable_memory_cache', True)
        self.enable_redis_cache = self.config.get('enable_redis_cache', True)
        self.enable_disk_cache = self.config.get('enable_disk_cache', True)

        # Cache configurations
        self.memory_cache_size = self.config.get('memory_cache_size', 10000)
        self.redis_host = self.config.get('redis_host', 'localhost')
        self.redis_port = self.config.get('redis_port', 6379)
        self.redis_db = self.config.get('redis_db', 0)
        self.disk_cache_dir = Path(self.config.get('disk_cache_dir', './cache'))

        # TTL settings (in seconds)
        self.default_ttl = self.config.get('default_ttl', 3600)  # 1 hour
        self.ttl_configs = {
            'query_results': self.config.get('query_ttl', 1800),  # 30 minutes
            'embeddings': self.config.get('embedding_ttl', 7200),  # 2 hours
            'model_outputs': self.config.get('model_ttl', 3600),  # 1 hour
            'metadata': self.config.get('metadata_ttl', 86400),  # 24 hours
        }

        # Cache instances
        self.memory_cache = LRUCache(self.memory_cache_size) if self.enable_memory_cache else None
        self.redis_client = None
        self.disk_cache_enabled = False

        # Statistics
        self.stats = {
            'memory_hits': 0,
            'memory_misses': 0,
            'redis_hits': 0,
            'redis_misses': 0,
            'disk_hits': 0,
            'disk_misses': 0,
            'total_requests': 0
        }

        # Initialize caches
        self._init_caches()

        logger.info("Cache manager initialized")

    def _init_caches(self):
        """Initialize cache backends."""
        # Redis cache
        if self.enable_redis_cache:
            try:
                self.redis_client = redis.Redis(
                    host=self.redis_host,
                    port=self.redis_port,
                    db=self.redis_db,
                    decode_responses=False,  # Keep as bytes for pickle
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True
                )
                # Test connection
                self.redis_client.ping()
                logger.info("Redis cache connected")
            except Exception as e:
                logger.warning(f"Redis cache unavailable: {e}")
                self.redis_client = None

        # Disk cache
        if self.enable_disk_cache:
            try:
                self.disk_cache_dir.mkdir(parents=True, exist_ok=True)
                self.disk_cache_enabled = True
                logger.info(f"Disk cache enabled at {self.disk_cache_dir}")
            except Exception as e:
                logger.warning(f"Disk cache initialization failed: {e}")
                self.disk_cache_enabled = False

    def get(self, key: str, cache_type: str = 'auto') -> Optional[Any]:
        """
        Get item from cache using multi-level lookup.

        Args:
            key: Cache key
            cache_type: Cache type ('memory', 'redis', 'disk', 'auto')

        Returns:
            Cached value or None
        """
        self.stats['total_requests'] += 1

        # Generate cache key
        cache_key = self._generate_key(key)

        # Try memory cache first (L1)
        if self.memory_cache and (cache_type in ['auto', 'memory']):
            value = self.memory_cache.get(cache_key)
            if value is not None:
                self.stats['memory_hits'] += 1
                return self._deserialize_value(value)

        # Try Redis cache (L2)
        if self.redis_client and (cache_type in ['auto', 'redis']):
            try:
                value = self.redis_client.get(cache_key)
                if value is not None:
                    self.stats['redis_hits'] += 1
                    # Also store in memory cache for faster future access
                    if self.memory_cache:
                        self.memory_cache.put(cache_key, value)
                    return self._deserialize_value(value)
            except Exception as e:
                logger.debug(f"Redis get failed: {e}")

        # Try disk cache (L3)
        if self.disk_cache_enabled and (cache_type in ['auto', 'disk']):
            value = self._get_from_disk(cache_key)
            if value is not None:
                self.stats['disk_hits'] += 1
                # Promote to higher cache levels
                if self.redis_client:
                    try:
                        self.redis_client.setex(cache_key, self.default_ttl, self._serialize_value(value))
                    except Exception:
                        pass
                if self.memory_cache:
                    self.memory_cache.put(cache_key, self._serialize_value(value))
                return value

        # Cache miss
        if cache_type == 'memory':
            self.stats['memory_misses'] += 1
        elif cache_type == 'redis':
            self.stats['redis_misses'] += 1
        elif cache_type == 'disk':
            self.stats['disk_misses'] += 1

        return None

    def put(self, key: str, value: Any, ttl: Optional[int] = None, cache_type: str = 'auto'):
        """
        Put item in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            cache_type: Cache type ('memory', 'redis', 'disk', 'auto')
        """
        if value is None:
            return

        cache_key = self._generate_key(key)
        ttl = ttl or self.default_ttl
        serialized_value = self._serialize_value(value)

        # Memory cache (L1)
        if self.memory_cache and (cache_type in ['auto', 'memory']):
            self.memory_cache.put(cache_key, serialized_value)

        # Redis cache (L2)
        if self.redis_client and (cache_type in ['auto', 'redis']):
            try:
                self.redis_client.setex(cache_key, ttl, serialized_value)
            except Exception as e:
                logger.debug(f"Redis set failed: {e}")

        # Disk cache (L3) - only for larger or persistent data
        if self.disk_cache_enabled and (cache_type in ['auto', 'disk']):
            self._put_to_disk(cache_key, value, ttl)

    def delete(self, key: str, cache_type: str = 'all'):
        """
        Delete item from cache.

        Args:
            key: Cache key
            cache_type: Cache type to delete from ('memory', 'redis', 'disk', 'all')
        """
        cache_key = self._generate_key(key)

        if cache_type in ['all', 'memory'] and self.memory_cache:
            self.memory_cache.remove(cache_key)

        if cache_type in ['all', 'redis'] and self.redis_client:
            try:
                self.redis_client.delete(cache_key)
            except Exception as e:
                logger.debug(f"Redis delete failed: {e}")

        if cache_type in ['all', 'disk'] and self.disk_cache_enabled:
            self._delete_from_disk(cache_key)

    def clear(self, cache_type: str = 'all'):
        """
        Clear cache.

        Args:
            cache_type: Cache type to clear ('memory', 'redis', 'disk', 'all')
        """
        if cache_type in ['all', 'memory'] and self.memory_cache:
            self.memory_cache.clear()

        if cache_type in ['all', 'redis'] and self.redis_client:
            try:
                self.redis_client.flushdb()
            except Exception as e:
                logger.debug(f"Redis flush failed: {e}")

        if cache_type in ['all', 'disk'] and self.disk_cache_enabled:
            self._clear_disk_cache()

    def get_or_set(self, key: str, func: Callable[[], Any], ttl: Optional[int] = None) -> Any:
        """
        Get item from cache or compute and cache it.

        Args:
            key: Cache key
            func: Function to compute value if not cached
            ttl: Time to live

        Returns:
            Cached or computed value
        """
        # Try to get from cache
        value = self.get(key)
        if value is not None:
            return value

        # Compute value
        value = func()

        # Cache the result
        self.put(key, value, ttl)

        return value

    def preheat_caches(self, warmup_data: Dict[str, Any]):
        """
        Preheat caches with common data.

        Args:
            warmup_data: Data to preload into caches
        """
        logger.info("Preheating caches with warmup data")

        for cache_type, data in warmup_data.items():
            if cache_type == 'queries':
                for query_data in data:
                    key = f"query_{query_data.get('id', hash(str(query_data)))}"
                    self.put(key, query_data, ttl=self.ttl_configs['query_results'])

            elif cache_type == 'embeddings':
                for embedding_data in data:
                    key = f"embedding_{embedding_data.get('id', hash(str(embedding_data)))}"
                    self.put(key, embedding_data, ttl=self.ttl_configs['embeddings'])

            elif cache_type == 'metadata':
                for metadata in data:
                    key = f"metadata_{metadata.get('type', 'unknown')}_{metadata.get('id', hash(str(metadata)))}"
                    self.put(key, metadata, ttl=self.ttl_configs['metadata'])

        logger.info("Cache preheating completed")

    def _generate_key(self, key: str) -> str:
        """Generate cache key."""
        if isinstance(key, str):
            # Hash long keys to prevent issues
            if len(key) > 250:
                key = hashlib.md5(key.encode()).hexdigest()
            return key
        else:
            # Convert other types to string and hash
            return hashlib.md5(str(key).encode()).hexdigest()

    def _serialize_value(self, value: Any) -> bytes:
        """Serialize value for storage."""
        return pickle.dumps(value)

    def _deserialize_value(self, value: bytes) -> Any:
        """Deserialize value from storage."""
        return pickle.loads(value)

    def _get_from_disk(self, key: str) -> Optional[Any]:
        """Get item from disk cache."""
        try:
            cache_file = self.disk_cache_dir / f"{key}.pkl"
            if cache_file.exists():
                # Check if expired (simple file timestamp check)
                if time.time() - cache_file.stat().st_mtime > self.default_ttl:
                    cache_file.unlink()  # Remove expired file
                    return None

                with open(cache_file, 'rb') as f:
                    return pickle.load(f)

        except Exception as e:
            logger.debug(f"Disk cache get failed: {e}")

        return None

    def _put_to_disk(self, key: str, value: Any, ttl: int):
        """Put item in disk cache."""
        try:
            cache_file = self.disk_cache_dir / f"{key}.pkl"
            with open(cache_file, 'wb') as f:
                pickle.dump(value, f)

            # Set file modification time for TTL tracking
            current_time = time.time()
            os.utime(cache_file, (current_time, current_time))

        except Exception as e:
            logger.debug(f"Disk cache put failed: {e}")

    def _delete_from_disk(self, key: str):
        """Delete item from disk cache."""
        try:
            cache_file = self.disk_cache_dir / f"{key}.pkl"
            if cache_file.exists():
                cache_file.unlink()
        except Exception as e:
            logger.debug(f"Disk cache delete failed: {e}")

    def _clear_disk_cache(self):
        """Clear all disk cache files."""
        try:
            for cache_file in self.disk_cache_dir.glob("*.pkl"):
                cache_file.unlink()
        except Exception as e:
            logger.debug(f"Disk cache clear failed: {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total_hits = self.stats['memory_hits'] + self.stats['redis_hits'] + self.stats['disk_hits']
        total_misses = self.stats['memory_misses'] + self.stats['redis_misses'] + self.stats['disk_misses']

        hit_rate = total_hits / (total_hits + total_misses) if (total_hits + total_misses) > 0 else 0

        return {
            'total_requests': self.stats['total_requests'],
            'total_hits': total_hits,
            'total_misses': total_misses,
            'hit_rate': hit_rate,
            'memory_cache': {
                'enabled': self.memory_cache is not None,
                'size': self.memory_cache.size() if self.memory_cache else 0,
                'capacity': self.memory_cache.capacity if self.memory_cache else 0,
                'hits': self.stats['memory_hits'],
                'misses': self.stats['memory_misses']
            },
            'redis_cache': {
                'enabled': self.redis_client is not None,
                'connected': self.redis_client is not None,
                'hits': self.stats['redis_hits'],
                'misses': self.stats['redis_misses']
            },
            'disk_cache': {
                'enabled': self.disk_cache_enabled,
                'directory': str(self.disk_cache_dir),
                'hits': self.stats['disk_hits'],
                'misses': self.stats['disk_misses']
            }
        }

    def get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage statistics."""
        process = psutil.Process()
        memory_info = process.memory_info()

        return {
            'rss': memory_info.rss,  # Resident Set Size
            'vms': memory_info.vms,  # Virtual Memory Size
            'memory_percent': process.memory_percent(),
            'cache_memory_mb': (self.memory_cache.size() * 1024 * 1024) if self.memory_cache else 0
        }

    def optimize_cache_sizes(self):
        """Optimize cache sizes based on usage patterns."""
        stats = self.get_cache_stats()

        # Adjust memory cache size based on hit rate
        if self.memory_cache:
            hit_rate = stats['memory_cache']['hits'] / (stats['memory_cache']['hits'] + stats['memory_cache']['misses']) if stats['memory_cache']['hits'] + stats['memory_cache']['misses'] > 0 else 0

            if hit_rate > 0.8:
                # High hit rate, can increase cache size
                new_size = min(self.memory_cache.capacity * 2, 50000)
                if new_size != self.memory_cache.capacity:
                    self.memory_cache.capacity = new_size
                    logger.info(f"Increased memory cache size to {new_size}")
            elif hit_rate < 0.5:
                # Low hit rate, can decrease cache size
                new_size = max(self.memory_cache.capacity // 2, 1000)
                if new_size != self.memory_cache.capacity:
                    self.memory_cache.capacity = new_size
                    logger.info(f"Decreased memory cache size to {new_size}")

    def enable_compression(self, enable: bool = True):
        """
        Enable/disable cache compression.

        Args:
            enable: Whether to enable compression
        """
        self.compression_enabled = enable
        logger.info(f"Cache compression {'enabled' if enable else 'disabled'}")

    def set_cache_policy(self, policy: str):
        """
        Set cache eviction policy.

        Args:
            policy: Cache policy ('lru', 'lfu', 'fifo')
        """
        # For now, only LRU is implemented
        supported_policies = ['lru']
        if policy not in supported_policies:
            logger.warning(f"Unsupported cache policy: {policy}")
            return

        logger.info(f"Cache policy set to: {policy}")

    def get_cache_recommendations(self) -> List[str]:
        """Get cache optimization recommendations."""
        recommendations = []
        stats = self.get_cache_stats()

        if stats['hit_rate'] < 0.7:
            recommendations.append("Low cache hit rate - consider increasing cache sizes or TTL values")

        if stats['memory_cache']['enabled'] and stats['memory_cache']['size'] > stats['memory_cache']['capacity'] * 0.9:
            recommendations.append("Memory cache near capacity - consider increasing memory cache size")

        if not stats['redis_cache']['connected']:
            recommendations.append("Redis cache not connected - consider enabling Redis for better performance")

        memory_usage = self.get_memory_usage()
        if memory_usage['memory_percent'] > 80:
            recommendations.append("High memory usage - consider reducing cache sizes")

        return recommendations

    def export_cache_metrics(self, filepath: str):
        """
        Export cache metrics to file.

        Args:
            filepath: Export file path
        """
        metrics = {
            'timestamp': time.time(),
            'stats': self.get_cache_stats(),
            'memory_usage': self.get_memory_usage(),
            'recommendations': self.get_cache_recommendations()
        }

        with open(filepath, 'w') as f:
            json.dump(metrics, f, indent=2, default=str)

        logger.info(f"Cache metrics exported to {filepath}")

    def __del__(self):
        """Cleanup on destruction."""
        if hasattr(self, 'redis_client') and self.redis_client:
            try:
                self.redis_client.close()
            except Exception:
                pass
