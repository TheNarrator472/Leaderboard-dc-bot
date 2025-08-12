"""
Enhanced logging configuration with structured logging and performance monitoring.
"""

import logging
import logging.handlers
import os
import sys
import json
from datetime import datetime
from typing import Optional, Dict, Any


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter for structured JSON logging.
    """
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 'msecs', 
                          'relativeCreated', 'thread', 'threadName', 'processName', 'process',
                          'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                log_entry[key] = value
        
        return json.dumps(log_entry)


class ColoredFormatter(logging.Formatter):
    """
    Colored console formatter for better readability.
    """
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        
        # Format message
        message = f"{color}[{timestamp}] {record.levelname:8} {record.name}: {record.getMessage()}{reset}"
        
        # Add exception info if present
        if record.exc_info:
            message += f"\n{self.formatException(record.exc_info)}"
        
        return message


def setup_logger(name: str, level: str = "INFO", log_file: Optional[str] = None, 
                max_size: int = 10, backup_count: int = 5, 
                structured: bool = False) -> logging.Logger:
    """
    Setup logger with console and optional file output.
    
    Args:
        name: Logger name
        level: Logging level
        log_file: Optional log file path
        max_size: Max log file size in MB
        backup_count: Number of backup files to keep
        structured: Use structured JSON logging
    
    Returns:
        Configured logger instance
    """
    
    logger = logging.getLogger(name)
    
    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Set level
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    if structured:
        console_formatter = StructuredFormatter()
    else:
        console_formatter = ColoredFormatter()
    
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        try:
            # Create log directory if it doesn't exist
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            # Use rotating file handler
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_size * 1024 * 1024,  # Convert MB to bytes
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(log_level)
            
            # Always use structured format for file logs
            file_formatter = StructuredFormatter()
            file_handler.setFormatter(file_formatter)
            
            logger.addHandler(file_handler)
            
        except Exception as e:
            logger.error(f"Failed to setup file logging: {e}")
    
    # Add performance tracking capability
    logger.performance_data = {}
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get existing logger instance.
    """
    return logging.getLogger(name)


class PerformanceLogger:
    """
    Context manager for performance logging.
    """
    
    def __init__(self, logger: logging.Logger, operation: str, log_level: int = logging.DEBUG):
        self.logger = logger
        self.operation = operation
        self.log_level = log_level
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.utcnow()
        self.logger.log(self.log_level, f"Starting operation: {self.operation}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = datetime.utcnow()
        duration = (end_time - self.start_time).total_seconds()
        
        if exc_type is None:
            self.logger.log(
                self.log_level, 
                f"Completed operation: {self.operation}",
                extra={'duration_seconds': duration, 'operation': self.operation}
            )
        else:
            self.logger.error(
                f"Failed operation: {self.operation}",
                extra={'duration_seconds': duration, 'operation': self.operation, 'error': str(exc_val)}
            )


def log_performance(operation: str, log_level: int = logging.DEBUG):
    """
    Decorator for performance logging.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            with PerformanceLogger(logger, f"{func.__name__}:{operation}", log_level):
                return func(*args, **kwargs)
        return wrapper
    return decorator


async def log_async_performance(operation: str, log_level: int = logging.DEBUG):
    """
    Decorator for async function performance logging.
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            with PerformanceLogger(logger, f"{func.__name__}:{operation}", log_level):
                return await func(*args, **kwargs)
        return wrapper
    return decorator


class LoggingMixin:
    """
    Mixin class to add logging capabilities to any class.
    """
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class."""
        return get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    def log_performance(self, operation: str, log_level: int = logging.DEBUG):
        """Get performance logger context manager."""
        return PerformanceLogger(self.logger, operation, log_level)


# Global logger configuration
def configure_root_logger(level: str = "INFO", structured: bool = False):
    """
    Configure root logger with basic settings.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Remove default handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    if structured:
        formatter = StructuredFormatter()
    else:
        formatter = ColoredFormatter()
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
