"""
Optimized leaderboard service with caching, batch processing, and performance monitoring.
"""

import asyncio
import time
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta

import discord
from discord.ext import tasks

from database.manager import DatabaseManager
from database.models import LeaderboardEntry
from services.cache import CacheService
from utils.logger import get_logger
from utils.decorators import rate_limit, performance_monitor


class LeaderboardService:
    """
    Enhanced leaderboard service with optimized operations and caching.
    """
    
    def __init__(self, db_manager: DatabaseManager, cache_service: CacheService, config):
        self.db_manager = db_manager
        self.cache_service = cache_service
        self.config = config
        self.logger = get_logger("leaderboard.service")
        
        # Rate limiting tracking
        self._rate_limit_tracker = {}
        
        # Performance metrics
        self._metrics = {
            'messages_tracked': 0,
            'voice_updates': 0,
            'leaderboard_updates': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        # Background tasks
        self._update_tasks = []
        self._cleanup_task = None
        
        # Bot reference (set during initialization)
        self.bot = None
    
    def set_bot(self, bot):
        """Set bot reference for Discord operations."""
        self.bot = bot
    
    async def track_message(self, user_id: int, guild_id: int, channel_id: int):
        """Track a message with rate limiting and batch processing."""
        try:
            if not self.config.ENABLE_MESSAGE_TRACKING:
                return
            
            # Check rate limiting (per user)
            if not self._check_rate_limit(user_id, 'message'):
                return
            
            await self.db_manager.increment_message_count(user_id, guild_id, channel_id)
            
            # Cache user info if not cached
            if self.bot:
                await self._cache_user_if_needed(user_id)
            
            # Invalidate related caches
            cache_keys = [
                f"message_leaderboard_{guild_id}",
                f"message_leaderboard_global",
                f"user_message_stats_{user_id}_{guild_id}"
            ]
            for key in cache_keys:
                self.cache_service.delete(key)
            
            self._metrics['messages_tracked'] += 1
            
        except Exception as e:
            self.logger.error(f"Error tracking message for user {user_id}: {e}")
    
    async def handle_voice_state_update(self, member, before, after):
        """Handle voice state updates with optimized processing."""
        try:
            if not self.config.ENABLE_VOICE_TRACKING:
                return
            
            user_id = member.id
            guild_id = member.guild.id
            
            # Check rate limiting
            if not self._check_rate_limit(user_id, 'voice'):
                return
            
            # Handle different voice state transitions
            if before.channel is None and after.channel is not None:
                # User joined voice
                await self.db_manager.update_voice_join(user_id, guild_id)
                self.logger.debug(f"User {user_id} joined voice in guild {guild_id}")
                
            elif before.channel is not None and after.channel is None:
                # User left voice
                await self.db_manager.update_voice_leave(user_id, guild_id)
                self.logger.debug(f"User {user_id} left voice in guild {guild_id}")
                
            elif before.channel != after.channel:
                # User switched channels (treat as leave + join)
                await self.db_manager.update_voice_leave(user_id, guild_id)
                await self.db_manager.update_voice_join(user_id, guild_id)
                self.logger.debug(f"User {user_id} switched voice channels in guild {guild_id}")
            
            # Cache user info if not cached
            await self._cache_user_if_needed(user_id)
            
            # Invalidate related caches
            cache_keys = [
                f"voice_leaderboard_{guild_id}",
                f"voice_leaderboard_global",
                f"user_voice_stats_{user_id}_{guild_id}"
            ]
            for key in cache_keys:
                self.cache_service.delete(key)
            
            self._metrics['voice_updates'] += 1
            
        except Exception as e:
            self.logger.error(f"Error handling voice state update for user {member.id}: {e}")
    
    async def get_message_leaderboard(self, guild_id: int = None, limit: int = None) -> List[LeaderboardEntry]:
        """Get message leaderboard with caching and 30-day refresh."""
        if limit is None:
            limit = self.config.LEADERBOARD_SIZE
        
        # Ensure we only show top 10
        limit = min(limit, 10)
        
        # Check if leaderboard needs reset (30-day cycle)
        if await self.db_manager.should_reset_leaderboard(self.config.LEADERBOARD_REFRESH_DAYS):
            await self.db_manager.reset_leaderboard_data()
            self.cache_service.clear()  # Clear cache after reset
        
        cache_key = f"message_leaderboard_{guild_id or 'global'}_{limit}"
        
        # Try cache first
        cached = self.cache_service.get(cache_key)
        if cached:
            self._metrics['cache_hits'] += 1
            return cached
        
        self._metrics['cache_misses'] += 1
        
        try:
            # Get data from database
            raw_data = await self.db_manager.get_message_leaderboard(guild_id, limit)
            
            # Convert to leaderboard entries
            entries = []
            for position, (user_id, count) in enumerate(raw_data, 1):
                username = await self._get_username(user_id)
                entry = LeaderboardEntry.create_message_entry(position, user_id, username, count)
                entries.append(entry)
            
            # Cache the result
            self.cache_service.set(cache_key, entries)
            
            return entries
            
        except Exception as e:
            self.logger.error(f"Error getting message leaderboard: {e}")
            return []
    
    async def get_voice_leaderboard(self, guild_id: int = None, limit: int = None) -> List[LeaderboardEntry]:
        """Get voice leaderboard with caching and 30-day refresh."""
        if limit is None:
            limit = self.config.LEADERBOARD_SIZE
        
        # Ensure we only show top 10
        limit = min(limit, 10)
        
        # Check if leaderboard needs reset (30-day cycle)
        if await self.db_manager.should_reset_leaderboard(self.config.LEADERBOARD_REFRESH_DAYS):
            await self.db_manager.reset_leaderboard_data()
            self.cache_service.clear()  # Clear cache after reset
        
        cache_key = f"voice_leaderboard_{guild_id or 'global'}_{limit}"
        
        # Try cache first (shorter TTL for voice as it changes more frequently)
        cached = self.cache_service.get(cache_key)
        if cached:
            self._metrics['cache_hits'] += 1
            return cached
        
        self._metrics['cache_misses'] += 1
        
        try:
            # Get data from database
            raw_data = await self.db_manager.get_voice_leaderboard(guild_id, limit)
            
            # Convert to leaderboard entries
            entries = []
            for position, (user_id, total_time) in enumerate(raw_data, 1):
                username = await self._get_username(user_id)
                entry = LeaderboardEntry.create_voice_entry(position, user_id, username, total_time)
                entries.append(entry)
            
            # Cache the result with shorter TTL
            self.cache_service.set(cache_key, entries, ttl=60)  # 1 minute for voice
            
            return entries
            
        except Exception as e:
            self.logger.error(f"Error getting voice leaderboard: {e}")
            return []
    
    async def _get_username(self, user_id: int) -> str:
        """Get username with comprehensive caching and fallback."""
        try:
            # Try to fetch from Discord first (more reliable)
            if self.bot:
                user = self.bot.get_user(user_id)
                if user:
                    # Cache the user for future use
                    await self._cache_user_if_needed(user_id)
                    # Prefer global_name, then display_name, then username
                    return user.global_name or user.display_name or user.name
                
                # Try fetching user if not in cache
                try:
                    user = await self.bot.fetch_user(user_id)
                    if user:
                        await self._cache_user_if_needed(user_id)
                        return user.global_name or user.display_name or user.name
                except discord.NotFound:
                    pass
                
                # Try guild members for better accuracy
                for guild in self.bot.guilds:
                    try:
                        member = guild.get_member(user_id)
                        if member:
                            await self._cache_user_if_needed(user_id)
                            return member.global_name or member.display_name or member.name
                    except:
                        continue
            
            # Try database cache as fallback
            cached_user = await self.db_manager.get_cached_user(user_id)
            if cached_user:
                username, discriminator = cached_user
                if username and username != f"User {user_id}":
                    if discriminator and discriminator != "0":
                        return f"{username}#{discriminator}"
                    return username
            
            # Last resort but more informative
            self.logger.warning(f"Could not resolve username for user {user_id}")
            return f"Unknown User"
            
        except Exception as e:
            self.logger.error(f"Error getting username for {user_id}: {e}")
            return f"Unknown User"
    
    async def _cache_user_if_needed(self, user_id: int):
        """Cache user information if not already cached."""
        try:
            cached = await self.db_manager.get_cached_user(user_id)
            if not cached and self.bot:
                user = self.bot.get_user(user_id)
                if user:
                    await self.db_manager.cache_user(
                        user_id,
                        user.display_name or user.name,
                        user.discriminator if user.discriminator != "0" else ""
                    )
        except Exception as e:
            self.logger.error(f"Error caching user {user_id}: {e}")
    
    def _check_rate_limit(self, user_id: int, operation_type: str) -> bool:
        """Check if user is rate limited for specific operation."""
        current_time = time.time()
        key = f"{user_id}_{operation_type}"
        
        if key not in self._rate_limit_tracker:
            self._rate_limit_tracker[key] = []
        
        # Clean old entries
        cutoff_time = current_time - self.config.RATE_LIMIT_WINDOW
        self._rate_limit_tracker[key] = [
            t for t in self._rate_limit_tracker[key] if t > cutoff_time
        ]
        
        # Check if rate limited
        if len(self._rate_limit_tracker[key]) >= self.config.RATE_LIMIT_MESSAGES:
            return False
        
        # Add current request
        self._rate_limit_tracker[key].append(current_time)
        return True
    
    async def create_leaderboard_embed(self, leaderboard_type: str, guild_id: int = None) -> discord.Embed:
        """Create a Discord embed for leaderboard display."""
        try:
            if leaderboard_type == "message":
                entries = await self.get_message_leaderboard(guild_id)
                title = ""
                description = ""
                color = 0x571173  # Custom purple color
            elif leaderboard_type == "voice":
                entries = await self.get_voice_leaderboard(guild_id)
                title = ""
                description = ""
                color = 0x571173  # Custom purple color
            else:
                raise ValueError(f"Invalid leaderboard type: {leaderboard_type}")
            
            embed = discord.Embed(color=color)
            
            if not entries:
                description = "No activity data available yet"
            else:
                # Create leaderboard in the style of the provided image
                leaderboard_lines = []
                for i, entry in enumerate(entries[:self.config.LEADERBOARD_SIZE], 1):
                    # Purple arrow for all top 10 members
                    rank_text = f"<a:purp_arrow:1403295268505522187> "
                    
                    # Format the entry similar to the image
                    leaderboard_lines.append(f"{rank_text}{entry.username} - **{entry.formatted_value}**")
                
                description = "\n".join(leaderboard_lines)
            
            # Set title with server name based on leaderboard type
            guild_name = "Global"
            if self.bot and guild_id:
                guild = self.bot.get_guild(guild_id)
                if guild:
                    guild_name = guild.name
            
            if leaderboard_type == "message":
                embed.title = f"**{guild_name} - Message Leaderboard**"
            else:
                embed.title = f"**{guild_name} - Voice Activity Leaderboard**"
            
            embed.description = description
            
            # Add guild icon as thumbnail if available
            if self.bot and guild_id:
                guild = self.bot.get_guild(guild_id)
                if guild and guild.icon:
                    embed.set_thumbnail(url=guild.icon.url)
            
            # Add footer like in the image
            embed.set_footer(
                text=f"Last updated • {datetime.utcnow().strftime('%H:%M UTC')}"
            )
            
            return embed
            
        except Exception as e:
            self.logger.error(f"Error creating leaderboard embed: {e}")
            # Return error embed
            embed = discord.Embed(
                title="SYSTEM ERROR",
                description="```Failed to load leaderboard data```",
                color=0x571173
            )
            return embed
    
    async def update_leaderboard_message(self, channel_id: int, leaderboard_type: str, guild_id: int = None):
        """Update leaderboard message in specified channel."""
        try:
            if not self.bot:
                return
            
            channel = self.bot.get_channel(channel_id)
            if not channel:
                self.logger.warning(f"Channel {channel_id} not found")
                return
            
            embed = await self.create_leaderboard_embed(leaderboard_type, guild_id)
            
            # Get stored message ID
            setting_key = f"{leaderboard_type}_leaderboard_id_{guild_id or 'global'}"
            message_id = await self.db_manager.get_setting(setting_key)
            
            if message_id:
                try:
                    # Delete the old message first
                    old_message = await channel.fetch_message(int(message_id))
                    await old_message.delete()
                    self.logger.info(f"Deleted old {leaderboard_type} leaderboard message: {message_id}")
                    # Small delay to ensure deletion is processed
                    await asyncio.sleep(0.5)
                except (discord.NotFound, discord.Forbidden) as e:
                    self.logger.warning(f"Could not delete old message {message_id}: {e}")
                except Exception as e:
                    self.logger.error(f"Error deleting old message {message_id}: {e}")
            
            # Always create a new message
            message = await channel.send(embed=embed)
            await self.db_manager.set_setting(setting_key, str(message.id))
            self.logger.info(f"Created new {leaderboard_type} leaderboard message: {message.id}")
            
            self._metrics['leaderboard_updates'] += 1
            
        except Exception as e:
            self.logger.error(f"Error updating leaderboard message: {e}")
    
    # Background Tasks
    async def start_background_tasks(self):
        """Start all background tasks."""
        try:
            # Message leaderboard update task (chat-lb channel)
            @tasks.loop(seconds=self.config.UPDATE_INTERVAL)
            async def update_message_leaderboard():
                try:
                    await self.update_leaderboard_message(
                        self.config.MESSAGE_CHANNEL_ID,  # chat-lb channel
                        "message",
                        self.config.TARGET_GUILD_ID
                    )
                except Exception as e:
                    self.logger.error(f"Error in message leaderboard update task: {e}")
            
            # Voice leaderboard update task (vc-lb channel)
            @tasks.loop(seconds=self.config.UPDATE_INTERVAL)
            async def update_voice_leaderboard():
                try:
                    await self.update_leaderboard_message(
                        self.config.VOICE_CHANNEL_ID,  # vc-lb channel
                        "voice",
                        self.config.TARGET_GUILD_ID
                    )
                except Exception as e:
                    self.logger.error(f"Error in voice leaderboard update task: {e}")
            
            # Cleanup task
            @tasks.loop(seconds=self.config.CLEANUP_INTERVAL)
            async def cleanup_task():
                try:
                    if self.config.ENABLE_AUTO_CLEANUP:
                        await self.db_manager.cleanup_old_data()
                        
                        # Clear old rate limit entries
                        current_time = time.time()
                        cutoff_time = current_time - (self.config.RATE_LIMIT_WINDOW * 2)
                        
                        for key in list(self._rate_limit_tracker.keys()):
                            self._rate_limit_tracker[key] = [
                                t for t in self._rate_limit_tracker[key] if t > cutoff_time
                            ]
                            if not self._rate_limit_tracker[key]:
                                del self._rate_limit_tracker[key]
                        
                        self.logger.info("Completed periodic cleanup")
                except Exception as e:
                    self.logger.error(f"Error in cleanup task: {e}")
            
            # Start tasks
            update_message_leaderboard.start()
            update_voice_leaderboard.start()
            cleanup_task.start()
            
            self._update_tasks = [
                update_message_leaderboard,
                update_voice_leaderboard,
                cleanup_task
            ]
            
            self.logger.info("Background tasks started successfully")
            
        except Exception as e:
            self.logger.error(f"Error starting background tasks: {e}")
            raise
    
    async def stop_background_tasks(self):
        """Stop all background tasks."""
        try:
            for task in self._update_tasks:
                if task.is_running():
                    task.cancel()
            
            self._update_tasks.clear()
            self.logger.info("Background tasks stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping background tasks: {e}")
    
    def get_metrics(self) -> Dict[str, int]:
        """Get service metrics."""
        metrics = self._metrics.copy()
        metrics['cache_hit_rate'] = (
            metrics['cache_hits'] / max(metrics['cache_hits'] + metrics['cache_misses'], 1) * 100
        )
        return metrics
