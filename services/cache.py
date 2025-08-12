"""
Efficient caching service with TTL support and memory management.
"""

import time
import threading
from typing import Any, Optional, Dict
from collections import OrderedDict
from dataclasses import dataclass

from utils.logger import get_logger


@dataclass
class CacheEntry:
    """Cache entry with TTL support."""
    value: Any
    created_at: float
    ttl: Optional[float] = None
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        if self.ttl is None:
            return False
        return time.time() > (self.created_at + self.ttl)


class CacheService:
    """
    Thread-safe in-memory cache with TTL support and LRU eviction.
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self.logger = get_logger("cache.service")
        
        # Statistics
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'evictions': 0,
            'expired_cleanups': 0
        }
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self._lock:
            if key not in self._cache:
                self._stats['misses'] += 1
                return None
            
            entry = self._cache[key]
            
            # Check if expired
            if entry.is_expired:
                del self._cache[key]
                self._stats['misses'] += 1
                self._stats['expired_cleanups'] += 1
                return None
            
            # Move to end (LRU)
            self._cache.move_to_end(key)
            self._stats['hits'] += 1
            
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with optional TTL."""
        with self._lock:
            # Use default TTL if not specified
            if ttl is None:
                ttl = self.default_ttl
            
            # Create cache entry
            entry = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl=ttl
            )
            
            # Remove old entry if exists
            if key in self._cache:
                del self._cache[key]
            
            # Add new entry
            self._cache[key] = entry
            
            # Evict if necessary
            self._evict_if_needed()
            
            self._stats['sets'] += 1
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._stats['deletes'] += 1
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            cleared_count = len(self._cache)
            self._cache.clear()
            self.logger.info(f"Cleared {cleared_count} cache entries")
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count of removed entries."""
        with self._lock:
            current_time = time.time()
            expired_keys = []
            
            for key, entry in self._cache.items():
                if entry.is_expired:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                self._stats['expired_cleanups'] += len(expired_keys)
                self.logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
            
            return len(expired_keys)
    
    def _evict_if_needed(self) -> None:
        """Evict oldest entries if cache is full."""
        while len(self._cache) > self.max_size:
            # Remove least recently used item
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            self._stats['evictions'] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = (self._stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hit_rate': round(hit_rate, 2),
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'sets': self._stats['sets'],
                'deletes': self._stats['deletes'],
                'evictions': self._stats['evictions'],
                'expired_cleanups': self._stats['expired_cleanups']
            }
    
    def get_memory_usage(self) -> Dict[str, int]:
        """Estimate memory usage of cache."""
        import sys
        
        with self._lock:
            total_size = 0
            entry_count = len(self._cache)
            
            # Rough estimation of memory usage
            for key, entry in self._cache.items():
                total_size += sys.getsizeof(key)
                total_size += sys.getsizeof(entry)
                total_size += sys.getsizeof(entry.value)
            
            return {
                'total_bytes': total_size,
                'total_mb': round(total_size / (1024 * 1024), 2),
                'entry_count': entry_count,
                'avg_entry_size': round(total_size / entry_count) if entry_count > 0 else 0
            }
    
    def keys(self) -> list:
        """Get all cache keys."""
        with self._lock:
            return list(self._cache.keys())
    
    def has_key(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        with self._lock:
            if key not in self._cache:
                return False
            
            entry = self._cache[key]
            if entry.is_expired:
                del self._cache[key]
                self._stats['expired_cleanups'] += 1
                return False
            
            return True
    
    def refresh(self, key: str, ttl: Optional[int] = None) -> bool:
        """Refresh TTL for existing key."""
        with self._lock:
            if key not in self._cache:
                return False
            
            entry = self._cache[key]
            if entry.is_expired:
                del self._cache[key]
                self._stats['expired_cleanups'] += 1
                return False
            
            # Update TTL
            if ttl is None:
                ttl = self.default_ttl
            
            entry.created_at = time.time()
            entry.ttl = ttl
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            
            return True
