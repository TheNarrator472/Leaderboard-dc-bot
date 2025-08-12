#!/usr/bin/env python3
"""
Optimized Discord Leaderboard Bot
Main entry point with improved error handling, performance, and maintainability.
"""

import asyncio
import signal
import sys
import os
from datetime import datetime

import discord
from discord.ext import commands

from config import Config
from database.manager import DatabaseManager
from services.leaderboard import LeaderboardService
from services.cache import CacheService
from utils.logger import setup_logger
from utils.monitoring import PerformanceMonitor
from cogs.leaderboard_cog import LeaderboardCog

from keep_alive import keep_alive

keep_alive()  # Start the web server

client = discord.Client(intents=discord.Intents.all())

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')


class OptimizedLeaderboardBot(commands.Bot):
    """
    Enhanced Discord bot with improved performance, error handling, and monitoring.
    """
    
    def __init__(self):
        # Initialize configuration
        self.config = Config()
        
        # Setup logging
        self.logger = setup_logger(
            name="leaderboard_bot",
            level=self.config.LOG_LEVEL,
            log_file=self.config.LOG_FILE
        )
        
        # Initialize Discord intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        intents.members = True
        
        super().__init__(
            command_prefix=self.config.PREFIX,
            intents=intents,
            help_command=None,
            case_insensitive=True
        )
        
        # Initialize services
        self.db_manager = None
        self.leaderboard_service = None
        self.cache_service = None
        self.performance_monitor = None
        
        # Bot state
        self.startup_time = None
        self._is_ready = False
        
    async def setup_hook(self):
        """
        Setup hook called before the bot connects to Discord.
        Initialize all services and database connections.
        """
        try:
            self.logger.info("Initializing bot services...")
            
            # Initialize database manager
            self.db_manager = DatabaseManager(
                db_path=self.config.DATABASE_PATH,
                pool_size=self.config.DB_POOL_SIZE
            )
            await self.db_manager.initialize()
            
            # Initialize cache service
            self.cache_service = CacheService(
                max_size=self.config.CACHE_SIZE,
                default_ttl=self.config.CACHE_TTL
            )
            
            # Initialize leaderboard service
            self.leaderboard_service = LeaderboardService(
                db_manager=self.db_manager,
                cache_service=self.cache_service,
                config=self.config
            )
            
            # Set bot reference in leaderboard service
            self.leaderboard_service.set_bot(self)
            
            # Initialize performance monitor
            self.performance_monitor = PerformanceMonitor(
                logger=self.logger,
                alert_threshold=self.config.PERFORMANCE_ALERT_THRESHOLD
            )
            
            # Add cogs
            await self.add_cog(LeaderboardCog(self))
            
            self.logger.info("Bot services initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize bot services: {e}", exc_info=True)
            raise
    
    async def on_ready(self):
        """
        Called when the bot is ready and connected to Discord.
        """
        try:
            self.startup_time = datetime.utcnow()
            self._is_ready = True
            
            self.logger.info(f"Bot is ready! Logged in as {self.user}")
            self.logger.info(f"Connected to {len(self.guilds)} guilds")
            self.logger.info(f"Serving {len(self.users)} users")
            
            # Start background tasks
            await self.leaderboard_service.start_background_tasks()
            
            # Update bot status
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name=f"{len(self.guilds)} servers | {self.config.PREFIX}help"
                )
            )
            
        except Exception as e:
            self.logger.error(f"Error in on_ready: {e}", exc_info=True)
    
    async def on_message(self, message):
        """
        Handle incoming messages for leaderboard tracking.
        """
        try:
            # Skip bot messages
            if message.author.bot:
                return
            
            # Track message with performance monitoring
            with self.performance_monitor.track_operation("message_processing"):
                await self.leaderboard_service.track_message(
                    user_id=message.author.id,
                    guild_id=message.guild.id if message.guild else 0,
                    channel_id=message.channel.id
                )
            
            # Process commands
            await self.process_commands(message)
            
        except Exception as e:
            self.logger.error(f"Error processing message: {e}", exc_info=True)
    
    async def on_voice_state_update(self, member, before, after):
        """
        Handle voice state changes for voice time tracking.
        """
        try:
            with self.performance_monitor.track_operation("voice_state_update"):
                await self.leaderboard_service.handle_voice_state_update(
                    member=member,
                    before=before,
                    after=after
                )
        except Exception as e:
            self.logger.error(f"Error handling voice state update: {e}", exc_info=True)
    
    async def on_error(self, event, *args, **kwargs):
        """
        Global error handler for unhandled exceptions.
        """
        self.logger.error(f"Unhandled error in event {event}", exc_info=True)
    
    async def on_command_error(self, ctx, error):
        """
        Handle command errors with user-friendly messages.
        """
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore command not found errors
        
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏰ Command is on cooldown. Try again in {error.retry_after:.1f} seconds.",
                delete_after=10
            )
        
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send(
                "❌ You don't have permission to use this command.",
                delete_after=10
            )
        
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send(
                "❌ I don't have the required permissions to execute this command.",
                delete_after=10
            )
        
        else:
            self.logger.error(f"Command error in {ctx.command}: {error}", exc_info=True)
            await ctx.send(
                "❌ An unexpected error occurred. Please try again later.",
                delete_after=10
            )
    
    async def close(self):
        """
        Graceful shutdown procedure.
        """
        self.logger.info("Initiating graceful shutdown...")
        
        try:
            # Stop background tasks
            if self.leaderboard_service:
                await self.leaderboard_service.stop_background_tasks()
            
            # Close database connections
            if self.db_manager:
                await self.db_manager.close()
            
            # Clear cache
            if self.cache_service:
                self.cache_service.clear()
            
            # Log performance metrics
            if self.performance_monitor:
                self.performance_monitor.log_final_metrics()
            
            self.logger.info("Graceful shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}", exc_info=True)
        
        finally:
            await super().close()


async def main():
    """
    Main entry point with proper signal handling and error recovery.
    """
    bot = OptimizedLeaderboardBot()
    
    # Signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        bot.logger.info(f"Received signal {signum}, initiating shutdown...")
        asyncio.create_task(bot.close())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await bot.start(bot.config.TOKEN)
    except discord.LoginFailure:
        bot.logger.error("Invalid bot token provided")
        sys.exit(1)
    except Exception as e:
        bot.logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if not bot.is_closed():
            await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot shutdown requested by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
