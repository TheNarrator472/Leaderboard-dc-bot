"""
Configuration management for the Discord Leaderboard Bot.
Handles environment variables, validation, and default values.
"""

import os
import logging
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class Config:
    """
    Configuration class with environment variable support and validation.
    """
    
    def __init__(self):
        # Discord Configuration
        self.TOKEN = self._get_required_env("DISCORD_TOKEN", "YOUR_BOT_TOKEN")
        self.PREFIX = os.getenv("BOT_PREFIX", "!")
        
        # Channel Configuration  
        self.MESSAGE_CHANNEL_ID = self._get_int_env("MESSAGE_CHANNEL_ID", 1404855785183252572)  # chat-lb channel
        self.VOICE_CHANNEL_ID = self._get_int_env("VOICE_CHANNEL_ID", 1404855743596728374)  # vc-lb channel
        self.TARGET_GUILD_ID = self._get_int_env("TARGET_GUILD_ID", 1315029949211738222)
        
        # Leaderboard Message IDs (updated with latest ones)
        self.MESSAGE_LEADERBOARD_ID = self._get_int_env("MESSAGE_LEADERBOARD_ID", 1404857467279511573)
        self.VOICE_LEADERBOARD_ID = self._get_int_env("VOICE_LEADERBOARD_ID", 1404857469259223132)
        
        # Database Configuration
        self.DATABASE_PATH = os.getenv("DATABASE_PATH", "leaderboard.db")
        self.DB_POOL_SIZE = self._get_int_env("DB_POOL_SIZE", 10)
        self.BATCH_SIZE = self._get_int_env("BATCH_SIZE", 100)
        self.DB_TIMEOUT = self._get_int_env("DB_TIMEOUT", 30)
        
        # Update Intervals (seconds)
        self.UPDATE_INTERVAL = self._get_int_env("UPDATE_INTERVAL", 300)  # 5 minutes
        self.BATCH_UPDATE_INTERVAL = self._get_int_env("BATCH_UPDATE_INTERVAL", 60)  # 1 minute
        self.CLEANUP_INTERVAL = self._get_int_env("CLEANUP_INTERVAL", 3600)  # 1 hour
        
        # Cache Configuration
        self.CACHE_SIZE = self._get_int_env("CACHE_SIZE", 1000)
        self.CACHE_TTL = self._get_int_env("CACHE_TTL", 300)  # 5 minutes
        
        # Leaderboard Configuration
        self.LEADERBOARD_SIZE = self._get_int_env("LEADERBOARD_SIZE", 10)  # Fixed to top 10
        self.MAX_LEADERBOARD_SIZE = self._get_int_env("MAX_LEADERBOARD_SIZE", 10)  # Limit to 10
        self.LEADERBOARD_REFRESH_DAYS = self._get_int_env("LEADERBOARD_REFRESH_DAYS", 30)  # 30 day refresh
        
        # Rate Limiting
        self.RATE_LIMIT_MESSAGES = self._get_int_env("RATE_LIMIT_MESSAGES", 50)  # Increased limit
        self.RATE_LIMIT_WINDOW = self._get_int_env("RATE_LIMIT_WINDOW", 60)
        
        # Performance Monitoring
        self.PERFORMANCE_ALERT_THRESHOLD = self._get_float_env("PERFORMANCE_ALERT_THRESHOLD", 5.0)
        self.MEMORY_ALERT_THRESHOLD = self._get_int_env("MEMORY_ALERT_THRESHOLD", 500)  # MB
        
        # Logging Configuration
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
        self.LOG_FILE = os.getenv("LOG_FILE", "leaderboard_bot.log")
        self.LOG_MAX_SIZE = self._get_int_env("LOG_MAX_SIZE", 10)  # MB
        self.LOG_BACKUP_COUNT = self._get_int_env("LOG_BACKUP_COUNT", 5)
        
        # Health Check Configuration
        self.HEALTH_CHECK_INTERVAL = self._get_int_env("HEALTH_CHECK_INTERVAL", 60)
        self.HEALTH_CHECK_TIMEOUT = self._get_int_env("HEALTH_CHECK_TIMEOUT", 10)
        
        # Security Configuration
        self.ALLOWED_GUILDS = self._get_list_env("ALLOWED_GUILDS")
        self.ADMIN_USER_IDS = self._get_list_env("ADMIN_USER_IDS")
        
        # Feature Flags
        self.ENABLE_VOICE_TRACKING = self._get_bool_env("ENABLE_VOICE_TRACKING", True)
        self.ENABLE_MESSAGE_TRACKING = self._get_bool_env("ENABLE_MESSAGE_TRACKING", True)
        self.ENABLE_PERFORMANCE_MONITORING = self._get_bool_env("ENABLE_PERFORMANCE_MONITORING", True)
        self.ENABLE_AUTO_CLEANUP = self._get_bool_env("ENABLE_AUTO_CLEANUP", True)
        
        # Validate configuration
        self._validate_config()
    
    def _get_required_env(self, key: str, default: str = None) -> str:
        """Get required environment variable with optional default."""
        value = os.getenv(key, default)
        if not value or value == "YOUR_BOT_TOKEN":
            if key == "DISCORD_TOKEN":
                # Allow fallback for development
                value = default
        return value
    
    def _get_int_env(self, key: str, default: int) -> int:
        """Get integer environment variable with default."""
        try:
            return int(os.getenv(key, default))
        except (ValueError, TypeError):
            return default
    
    def _get_float_env(self, key: str, default: float) -> float:
        """Get float environment variable with default."""
        try:
            return float(os.getenv(key, default))
        except (ValueError, TypeError):
            return default
    
    def _get_bool_env(self, key: str, default: bool) -> bool:
        """Get boolean environment variable with default."""
        value = os.getenv(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on', 'enabled')
    
    def _get_list_env(self, key: str, default: List[str] = None) -> List[str]:
        """Get list environment variable with default."""
        if default is None:
            default = []
        
        value = os.getenv(key, "")
        if not value:
            return default
        
        return [item.strip() for item in value.split(",") if item.strip()]
    
    def _validate_config(self):
        """Validate configuration values."""
        errors = []
        
        # Validate required fields
        if not self.TOKEN or self.TOKEN == "YOUR_BOT_TOKEN":
            errors.append("DISCORD_TOKEN is required")
        
        # Validate numeric ranges
        if self.UPDATE_INTERVAL < 60:
            errors.append("UPDATE_INTERVAL must be at least 60 seconds")
        
        if self.LEADERBOARD_SIZE < 1 or self.LEADERBOARD_SIZE > self.MAX_LEADERBOARD_SIZE:
            errors.append(f"LEADERBOARD_SIZE must be between 1 and {self.MAX_LEADERBOARD_SIZE}")
        
        if self.DB_POOL_SIZE < 1:
            errors.append("DB_POOL_SIZE must be at least 1")
        
        # Validate log level
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.LOG_LEVEL not in valid_log_levels:
            errors.append(f"LOG_LEVEL must be one of: {', '.join(valid_log_levels)}")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")
    
    def get_log_level(self) -> int:
        """Get logging level as integer."""
        return getattr(logging, self.LOG_LEVEL, logging.INFO)
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is an admin."""
        return str(user_id) in self.ADMIN_USER_IDS
    
    def is_guild_allowed(self, guild_id: int) -> bool:
        """Check if guild is allowed."""
        if not self.ALLOWED_GUILDS:
            return True  # Allow all guilds if none specified
        return str(guild_id) in self.ALLOWED_GUILDS
    
    def __repr__(self):
        """String representation with sensitive data masked."""
        safe_attrs = {
            key: "***MASKED***" if "token" in key.lower() or "secret" in key.lower() else value
            for key, value in self.__dict__.items()
            if not key.startswith('_')
        }
        return f"Config({safe_attrs})"
