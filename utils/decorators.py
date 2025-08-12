"""
Utility decorators for rate limiting, caching, and performance monitoring.
"""

import asyncio
import functools
import time
from typing import Dict, Callable, Any, Optional
from collections import defaultdict, deque

from utils.logger import get_logger


class RateLimiter:
    """
    Token bucket rate limiter implementation.
    """
    
    def __init__(self, max_calls: int, window: int):
        self.max_calls = max_calls
        self.window = window
        self.calls = defaultdict(deque)
        self.logger = get_logger("rate_limiter")
    
    def is_allowed(self, key: str) -> bool:
        """Check if call is allowed for given key."""
        now = time.time()
        calls = self.calls[key]
        
        # Remove old calls outside the window
        while calls and calls[0] <= now - self.window:
            calls.popleft()
        
        # Check if under limit
        if len(calls) < self.max_calls:
            calls.append(now)
            return True
        
        return False
    
    def time_until_reset(self, key: str) -> float:
        """Get time until rate limit resets for key."""
        calls = self.calls[key]
        if not calls:
            return 0
        
        oldest_call = calls[0]
        reset_time = oldest_call + self.window
        return max(0, reset_time - time.time())


# Global rate limiter instance
_global_rate_limiter = {}


def rate_limit(max_calls: int = 10, window: int = 60, key_func: Optional[Callable] = None):
    """
    Rate limiting decorator.
    
    Args:
        max_calls: Maximum calls allowed in window
        window: Time window in seconds
        key_func: Function to generate rate limit key from args
    """
    def decorator(func):
        limiter_key = f"{func.__module__}.{func.__name__}"
        if limiter_key not in _global_rate_limiter:
            _global_rate_limiter[limiter_key] = RateLimiter(max_calls, window)
        
        limiter = _global_rate_limiter[limiter_key]
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate rate limit key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = str(args[0]) if args else "default"
            
            if not limiter.is_allowed(key):
                reset_time = limiter.time_until_reset(key)
                logger = get_logger(func.__module__)
                logger.warning(f"Rate limit exceeded for {func.__name__}, key: {key}, reset in: {reset_time:.1f}s")
                return None
            
            return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Generate rate limit key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = str(args[0]) if args else "default"
            
            if not limiter.is_allowed(key):
                reset_time = limiter.time_until_reset(key)
                logger = get_logger(func.__module__)
                logger.warning(f"Rate limit exceeded for {func.__name__}, key: {key}, reset in: {reset_time:.1f}s")
                return None
            
            return func(*args, **kwargs)
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def cache_result(ttl: int = 300, key_func: Optional[Callable] = None, max_size: int = 128):
    """
    Simple result caching decorator.
    
    Args:
        ttl: Time to live in seconds
        key_func: Function to generate cache key from args
        max_size: Maximum cache size
    """
    def decorator(func):
        cache = {}
        access_order = deque()
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = f"{args}:{sorted(kwargs.items())}"
            
            now = time.time()
            
            # Check cache
            if key in cache:
                value, timestamp = cache[key]
                if now - timestamp < ttl:
                    # Move to end of access order
                    if key in access_order:
                        access_order.remove(key)
                    access_order.append(key)
                    return value
                else:
                    # Expired
                    del cache[key]
            
            # Call function
            result = await func(*args, **kwargs)
            
            # Store in cache
            cache[key] = (result, now)
            access_order.append(key)
            
            # Evict if over size limit
            while len(cache) > max_size and access_order:
                oldest_key = access_order.popleft()
                if oldest_key in cache:
                    del cache[oldest_key]
            
            return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = f"{args}:{sorted(kwargs.items())}"
            
            now = time.time()
            
            # Check cache
            if key in cache:
                value, timestamp = cache[key]
                if now - timestamp < ttl:
                    # Move to end of access order
                    if key in access_order:
                        access_order.remove(key)
                    access_order.append(key)
                    return value
                else:
                    # Expired
                    del cache[key]
            
            # Call function
            result = func(*args, **kwargs)
            
            # Store in cache
            cache[key] = (result, now)
            access_order.append(key)
            
            # Evict if over size limit
            while len(cache) > max_size and access_order:
                oldest_key = access_order.popleft()
                if oldest_key in cache:
                    del cache[oldest_key]
            
            return result
        
        # Add cache management methods
        def clear_cache():
            cache.clear()
            access_order.clear()
        
        def cache_info():
            return {
                'size': len(cache),
                'max_size': max_size,
                'ttl': ttl
            }
        
        wrapper = async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        wrapper.clear_cache = clear_cache
        wrapper.cache_info = cache_info
        
        return wrapper
    
    return decorator


def performance_monitor(threshold: float = 1.0, log_level: str = "WARNING"):
    """
    Performance monitoring decorator.
    
    Args:
        threshold: Time threshold in seconds to trigger logging
        log_level: Log level for slow operations
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            logger = get_logger(func.__module__)
            
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                execution_time = time.time() - start_time
                
                if execution_time > threshold:
                    logger.log(
                        getattr(logger, log_level.upper(), logger.WARNING),
                        f"Slow operation detected: {func.__name__} took {execution_time:.3f}s",
                        extra={
                            'function': func.__name__,
                            'execution_time': execution_time,
                            'threshold': threshold
                        }
                    )
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            logger = get_logger(func.__module__)
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                execution_time = time.time() - start_time
                
                if execution_time > threshold:
                    logger.log(
                        getattr(logger, log_level.upper(), logger.WARNING),
                        f"Slow operation detected: {func.__name__} took {execution_time:.3f}s",
                        extra={
                            'function': func.__name__,
                            'execution_time': execution_time,
                            'threshold': threshold
                        }
                    )
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0, exceptions: tuple = (Exception,)):
    """
    Retry decorator with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries
        backoff: Backoff multiplier
        exceptions: Tuple of exceptions to catch
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts - 1:
                        logger.error(f"Function {func.__name__} failed after {max_attempts} attempts: {e}")
                        raise
                    
                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt + 1}/{max_attempts}): {e}. "
                        f"Retrying in {current_delay:.1f}s"
                    )
                    
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts - 1:
                        logger.error(f"Function {func.__name__} failed after {max_attempts} attempts: {e}")
                        raise
                    
                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt + 1}/{max_attempts}): {e}. "
                        f"Retrying in {current_delay:.1f}s"
                    )
                    
                    time.sleep(current_delay)
                    current_delay *= backoff
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def validate_args(**validators):
    """
    Argument validation decorator.
    
    Args:
        **validators: Keyword arguments where key is parameter name and value is validation function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get function signature
            import inspect
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Validate arguments
            for param_name, validator in validators.items():
                if param_name in bound_args.arguments:
                    value = bound_args.arguments[param_name]
                    if not validator(value):
                        raise ValueError(f"Validation failed for parameter '{param_name}' with value: {value}")
            
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# Validation functions for common use cases
def is_positive_int(value):
    """Validate positive integer."""
    return isinstance(value, int) and value > 0


def is_non_negative_int(value):
    """Validate non-negative integer."""
    return isinstance(value, int) and value >= 0


def is_valid_discord_id(value):
    """Validate Discord ID format."""
    return isinstance(value, int) and len(str(value)) >= 17


def is_non_empty_string(value):
    """Validate non-empty string."""
    return isinstance(value, str) and len(value.strip()) > 0
