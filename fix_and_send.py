#!/usr/bin/env python3
"""Fixed script to create and send working leaderboards."""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(__file__))

import discord
from discord.ext import commands
from config import Config
from database.manager import DatabaseManager

async def send_fixed_leaderboard():
    """Send a properly formatted leaderboard."""
    config = Config()
    
    # Initialize bot
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    @bot.event
    async def on_ready():
        print(f"Bot connected as {bot.user}")
        
        # Initialize database
        db_manager = DatabaseManager(config.DATABASE_PATH)
        await db_manager.initialize()
        
        # Get the channel
        channel = bot.get_channel(config.MESSAGE_CHANNEL_ID)
        if not channel:
            print(f"Channel {config.MESSAGE_CHANNEL_ID} not found")
            await bot.close()
            return
        
        print(f"Found channel: {channel.name}")
        
        # Get message leaderboard data directly
        message_data = await db_manager.get_message_leaderboard(guild_id=channel.guild.id, limit=10)
        
        # Create message leaderboard embed
        embed = discord.Embed(
            title=f"{channel.guild.name} - Message Leaderboard",
            color=0x571173
        )
        
        if not message_data:
            embed.description = "No activity data available yet"
        else:
            leaderboard_lines = []
            for i, (user_id, count) in enumerate(message_data, 1):
                # Try to get username from bot
                user = bot.get_user(user_id)
                username = user.display_name if user else f"User {user_id}"
                
                if i == 1:
                    rank_text = f"👑 **{i}** - "
                else:
                    rank_text = f"**{i}.** "
                
                leaderboard_lines.append(f"{rank_text}{username} - **{count} messages**")
            
            embed.description = "\n".join(leaderboard_lines)
        
        # Add guild icon if available
        if channel.guild.icon:
            embed.set_thumbnail(url=channel.guild.icon.url)
        
        # Add footer
        from datetime import datetime
        embed.set_footer(text=f"Last updated • {datetime.utcnow().strftime('%H:%M UTC')}")
        
        # Send the embed
        message = await channel.send(embed=embed)
        print(f"Sent fixed message leaderboard: {message.id}")
        
        # Get voice leaderboard data
        voice_data = await db_manager.get_voice_leaderboard(guild_id=channel.guild.id, limit=10)
        
        # Create voice leaderboard embed
        embed = discord.Embed(
            title=f"{channel.guild.name} - Voice Activity Leaderboard",
            color=0x571173
        )
        
        if not voice_data:
            embed.description = "No voice activity data available yet"
        else:
            leaderboard_lines = []
            for i, (user_id, total_time) in enumerate(voice_data, 1):
                # Try to get username from bot
                user = bot.get_user(user_id)
                username = user.display_name if user else f"User {user_id}"
                
                # Format time
                hours = total_time // 3600
                minutes = (total_time % 3600) // 60
                time_str = f"{hours}h {minutes}m"
                
                if i == 1:
                    rank_text = f"👑 **{i}** - "
                else:
                    rank_text = f"**{i}.** "
                
                leaderboard_lines.append(f"{rank_text}{username} - **{time_str}**")
            
            embed.description = "\n".join(leaderboard_lines)
        
        # Add guild icon if available
        if channel.guild.icon:
            embed.set_thumbnail(url=channel.guild.icon.url)
        
        # Add footer
        embed.set_footer(text=f"Last updated • {datetime.utcnow().strftime('%H:%M UTC')}")
        
        # Send the embed
        message = await channel.send(embed=embed)
        print(f"Sent fixed voice leaderboard: {message.id}")
        
        await db_manager.close()
        await bot.close()
    
    # Start the bot
    await bot.start(config.TOKEN)

if __name__ == "__main__":
    asyncio.run(send_fixed_leaderboard())