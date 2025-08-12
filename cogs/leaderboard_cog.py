"""
Discord commands cog for leaderboard management and user interaction.
"""

import asyncio
from typing import Optional, Union

import discord
from discord.ext import commands

from utils.logger import get_logger
from utils.decorators import rate_limit, performance_monitor


class LeaderboardCog(commands.Cog):
    """
    Commands and interactions for leaderboard functionality.
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger("leaderboard.cog")
    
    @commands.group(name="leaderboard", aliases=["lb"], invoke_without_command=True)
    @rate_limit(max_calls=5, window=60)
    async def leaderboard(self, ctx):
        """Show available leaderboard commands."""
        embed = discord.Embed(
            title="LEADERBOARD SYSTEM",
            description="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0x2f3136
        )
        
        commands_text = "```\n"
        commands_text += f"▓ {ctx.prefix}leaderboard messages  │ Message activity rankings\n"
        commands_text += f"▒ {ctx.prefix}leaderboard voice     │ Voice channel activity\n"
        commands_text += f"░ {ctx.prefix}leaderboard stats     │ Personal statistics\n"
        commands_text += f"· {ctx.prefix}leaderboard settings  │ System configuration\n"
        commands_text += "```"
        
        embed.add_field(
            name="▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
            value=commands_text,
            inline=False
        )
        
        embed.set_footer(text="Enterprise Discord Analytics System")
        
        await ctx.send(embed=embed)
    
    @leaderboard.command(name="messages", aliases=["msg", "chat"])
    @rate_limit(max_calls=3, window=60)
    async def messages_leaderboard(self, ctx, limit: Optional[int] = None):
        """Show message leaderboard."""
        try:
            if limit and (limit < 1 or limit > 10):
                await ctx.send(
                    f"```Invalid range: 1-10 entries allowed (top 10 only)```",
                    delete_after=10
                )
                return
            
            if limit is None:
                limit = self.bot.config.LEADERBOARD_SIZE
            
            # Create and send leaderboard embed
            embed = await self.bot.leaderboard_service.create_leaderboard_embed(
                "message", 
                guild_id=ctx.guild.id if ctx.guild else None
            )
            
            # Add command info to footer
            current_footer = embed.footer.text if embed.footer else ""
            embed.set_footer(text=f"Requested by {ctx.author.display_name} • {current_footer}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error in messages leaderboard command: {e}")
            await ctx.send(
                "```System Error: Unable to retrieve message leaderboard```",
                delete_after=10
            )
    
    @leaderboard.command(name="voice", aliases=["vc"])
    @rate_limit(max_calls=3, window=60)
    async def voice_leaderboard(self, ctx, limit: Optional[int] = None):
        """Show voice time leaderboard."""
        try:
            if not self.bot.config.ENABLE_VOICE_TRACKING:
                await ctx.send(
                    "```Voice tracking is currently disabled```",
                    delete_after=10
                )
                return
            
            if limit and (limit < 1 or limit > 10):
                await ctx.send(
                    f"```Invalid range: 1-10 entries allowed (top 10 only)```",
                    delete_after=10
                )
                return
            
            if limit is None:
                limit = self.bot.config.LEADERBOARD_SIZE
            
            # Create and send leaderboard embed
            embed = await self.bot.leaderboard_service.create_leaderboard_embed(
                "voice", 
                guild_id=ctx.guild.id if ctx.guild else None
            )
            
            # Add command info to footer
            current_footer = embed.footer.text if embed.footer else ""
            embed.set_footer(text=f"Requested by {ctx.author.display_name} • {current_footer}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error in voice leaderboard command: {e}")
            await ctx.send(
                "```System Error: Unable to retrieve voice leaderboard```",
                delete_after=10
            )
    
    @leaderboard.command(name="stats", aliases=["statistics", "user"])
    @rate_limit(max_calls=5, window=60)
    async def user_stats(self, ctx, user: Optional[Union[discord.Member, discord.User]] = None):
        """Show statistics for a user."""
        try:
            # Default to command author if no user specified
            if user is None:
                user = ctx.author
            
            # Get user statistics
            guild_id = ctx.guild.id if ctx.guild else None
            
            # Get message stats
            message_data = await self.bot.db_manager.execute_query(
                "SELECT count FROM messages WHERE user_id = ? AND guild_id = ?",
                (user.id, guild_id),
                fetch_one=True
            )
            message_count = message_data[0] if message_data else 0
            
            # Get voice stats
            voice_data = await self.bot.db_manager.execute_query(
                "SELECT total_time, join_time FROM voice WHERE user_id = ? AND guild_id = ?",
                (user.id, guild_id),
                fetch_one=True
            )
            
            if voice_data:
                total_time, join_time = voice_data
                if join_time:  # Currently in voice
                    import time
                    current_session = int(time.time()) - join_time
                    total_time += current_session
            else:
                total_time = 0
            
            # Format voice time
            hours = total_time // 3600
            minutes = (total_time % 3600) // 60
            
            # Create embed
            embed = discord.Embed(
                title=f"📊 Statistics for {user.display_name}",
                color=discord.Color.green()
            )
            
            embed.set_thumbnail(url=user.display_avatar.url)
            
            embed.add_field(
                name="📨 Messages Sent",
                value=f"{message_count:,}",
                inline=True
            )
            
            embed.add_field(
                name="🎙️ Voice Time",
                value=f"{hours}h {minutes}m",
                inline=True
            )
            
            # Get user's rank in message leaderboard
            message_rank_data = await self.bot.db_manager.execute_query(
                """SELECT COUNT(*) + 1 FROM messages 
                   WHERE guild_id = ? AND count > (
                       SELECT COALESCE(count, 0) FROM messages 
                       WHERE user_id = ? AND guild_id = ?
                   )""",
                (guild_id, user.id, guild_id),
                fetch_one=True
            )
            message_rank = message_rank_data[0] if message_rank_data else "N/A"
            
            # Get user's rank in voice leaderboard
            voice_rank_data = await self.bot.db_manager.execute_query(
                """SELECT COUNT(*) + 1 FROM voice 
                   WHERE guild_id = ? AND total_time > ?""",
                (guild_id, total_time),
                fetch_one=True
            )
            voice_rank = voice_rank_data[0] if voice_rank_data else "N/A"
            
            embed.add_field(
                name="🏆 Message Rank",
                value=f"#{message_rank}",
                inline=True
            )
            
            embed.add_field(
                name="🎖️ Voice Rank",
                value=f"#{voice_rank}",
                inline=True
            )
            
            # Check if user is currently in voice
            if voice_data and voice_data[1]:  # join_time exists
                embed.add_field(
                    name="🔊 Currently",
                    value="In Voice Channel",
                    inline=True
                )
            
            embed.set_footer(text=f"Requested by {ctx.author}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error in user stats command: {e}")
            await ctx.send(
                "❌ An error occurred while fetching user statistics.",
                delete_after=10
            )
    
    @leaderboard.command(name="settings", aliases=["config"])
    @commands.has_permissions(administrator=True)
    async def settings(self, ctx):
        """Show bot settings (Admin only)."""
        try:
            embed = discord.Embed(
                title="⚙️ Bot Settings",
                color=discord.Color.orange()
            )
            
            # Bot configuration
            embed.add_field(
                name="📊 Tracking",
                value=f"Messages: {'✅' if self.bot.config.ENABLE_MESSAGE_TRACKING else '❌'}\n"
                      f"Voice: {'✅' if self.bot.config.ENABLE_VOICE_TRACKING else '❌'}",
                inline=True
            )
            
            embed.add_field(
                name="🔄 Update Interval",
                value=f"{self.bot.config.UPDATE_INTERVAL // 60} minutes",
                inline=True
            )
            
            embed.add_field(
                name="📋 Leaderboard Size",
                value=f"{self.bot.config.LEADERBOARD_SIZE} entries",
                inline=True
            )
            
            embed.add_field(
                name="📨 Message Channel",
                value=f"<#{self.bot.config.MESSAGE_CHANNEL_ID}>",
                inline=True
            )
            
            embed.add_field(
                name="🎙️ Voice Channel",
                value=f"<#{self.bot.config.VOICE_CHANNEL_ID}>",
                inline=True
            )
            
            embed.add_field(
                name="💾 Cache",
                value=f"Size: {self.bot.config.CACHE_SIZE}\n"
                      f"TTL: {self.bot.config.CACHE_TTL}s",
                inline=True
            )
            
            # Performance metrics
            if hasattr(self.bot, 'performance_monitor'):
                metrics = self.bot.leaderboard_service.get_metrics()
                embed.add_field(
                    name="📈 Performance",
                    value=f"Messages: {metrics.get('messages_tracked', 0):,}\n"
                          f"Voice Updates: {metrics.get('voice_updates', 0):,}\n"
                          f"Cache Hit Rate: {metrics.get('cache_hit_rate', 0):.1f}%",
                    inline=True
                )
            
            embed.set_footer(text="Configuration can be modified via environment variables")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error in settings command: {e}")
            await ctx.send(
                "❌ An error occurred while fetching settings.",
                delete_after=10
            )
    
    @leaderboard.command(name="health", aliases=["status"])
    @commands.has_permissions(administrator=True)
    async def health_check(self, ctx):
        """Show bot health status (Admin only)."""
        try:
            if not hasattr(self.bot, 'performance_monitor'):
                await ctx.send("❌ Performance monitoring is not enabled.", delete_after=10)
                return
            
            # Run health checks
            health_results = await self.bot.performance_monitor.run_health_checks()
            
            embed = discord.Embed(
                title="🏥 Bot Health Status",
                color=discord.Color.green()
            )
            
            overall_status = self.bot.performance_monitor.health_checker.get_overall_status()
            status_emoji = {
                'healthy': '✅',
                'warning': '⚠️',
                'critical': '❌',
                'unknown': '❓'
            }
            
            embed.add_field(
                name="Overall Status",
                value=f"{status_emoji.get(overall_status, '❓')} {overall_status.title()}",
                inline=False
            )
            
            # Individual health checks
            for name, result in health_results.items():
                status_icon = status_emoji.get(result.status, '❓')
                embed.add_field(
                    name=f"{status_icon} {name.title()}",
                    value=f"{result.message}\n*Response time: {result.response_time:.3f}s*",
                    inline=True
                )
            
            # System metrics
            performance_summary = self.bot.performance_monitor.get_performance_summary()
            system_metrics = performance_summary.get('system_metrics', {})
            
            if 'memory_percent' in system_metrics:
                memory_info = system_metrics['memory_percent']
                embed.add_field(
                    name="💾 Memory Usage",
                    value=f"{memory_info['latest']:.1f}%",
                    inline=True
                )
            
            if 'cpu_percent' in system_metrics:
                cpu_info = system_metrics['cpu_percent']
                embed.add_field(
                    name="🖥️ CPU Usage",
                    value=f"{cpu_info['latest']:.1f}%",
                    inline=True
                )
            
            embed.set_footer(text=f"Uptime: {performance_summary.get('uptime', 0) // 3600:.0f} hours")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error in health check command: {e}")
            await ctx.send(
                "❌ An error occurred while checking bot health.",
                delete_after=10
            )
    
    @leaderboard.command(name="refresh", aliases=["update"])
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 60, commands.BucketType.guild)
    async def refresh_leaderboards(self, ctx):
        """Manually refresh leaderboards (Admin only)."""
        try:
            # Send initial message
            msg = await ctx.send("🔄 Refreshing leaderboards...")
            
            # Update message leaderboard
            await self.bot.leaderboard_service.update_leaderboard_message(
                self.bot.config.MESSAGE_CHANNEL_ID,
                "message",
                guild_id=ctx.guild.id if ctx.guild else None
            )
            
            # Update voice leaderboard
            await self.bot.leaderboard_service.update_leaderboard_message(
                self.bot.config.VOICE_CHANNEL_ID,
                "voice",
                guild_id=ctx.guild.id if ctx.guild else None
            )
            
            # Clear cache for fresh data
            self.bot.cache_service.clear()
            
            # Update message
            await msg.edit(content="✅ Leaderboards refreshed successfully!")
            
        except Exception as e:
            self.logger.error(f"Error in refresh command: {e}")
            await ctx.send(
                "❌ An error occurred while refreshing leaderboards.",
                delete_after=10
            )
    
    @commands.command(name="ping")
    async def ping(self, ctx):
        """Check bot latency."""
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Bot latency: {latency}ms",
            color=discord.Color.green() if latency < 100 else discord.Color.orange()
        )
        await ctx.send(embed=embed)
    
    # Error handlers for this cog
    @leaderboard.error
    async def leaderboard_error(self, ctx, error):
        """Handle leaderboard command errors."""
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏰ Command is on cooldown. Try again in {error.retry_after:.1f} seconds.",
                delete_after=10
            )
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send(
                "❌ You don't have permission to use this command.",
                delete_after=10
            )
        else:
            self.logger.error(f"Leaderboard command error: {error}")
            await ctx.send(
                "❌ An unexpected error occurred.",
                delete_after=10
            )


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(LeaderboardCog(bot))
