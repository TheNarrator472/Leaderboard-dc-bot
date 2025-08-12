#!/usr/bin/env python3
"""Send leaderboards to specific guild ID 1315029949211738222."""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(__file__))

import discord
from discord.ext import commands
from config import Config
from database.manager import DatabaseManager

async def send_to_specific_guild():
    """Send leaderboards to guild ID 1315029949211738222."""
    config = Config()
    
    # Initialize bot
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    @bot.event
    async def on_ready():
        print(f"Bot connected as {bot.user}")
        
        # Target guild ID
        target_guild_id = 1315029949211738222
        
        # Initialize database
        db_manager = DatabaseManager(config.DATABASE_PATH)
        await db_manager.initialize()
        
        # Get the target guild
        guild = bot.get_guild(target_guild_id)
        if not guild:
            print(f"Guild {target_guild_id} not found or bot not in guild")
            await bot.close()
            return
        
        print(f"Found guild: {guild.name} (ID: {guild.id})")
        
        # Find a suitable channel (look for general, announcements, or first text channel)
        channel = None
        for ch in guild.text_channels:
            if ch.name.lower() in ['general', 'announcements', 'leaderboard', 'vc-leaderboard']:
                channel = ch
                break
        
        if not channel:
            # Use first available text channel
            channel = guild.text_channels[0] if guild.text_channels else None
        
        if not channel:
            print("No suitable text channel found in guild")
            await bot.close()
            return
        
        print(f"Using channel: {channel.name} (ID: {channel.id})")
        
        # Get message leaderboard data for this guild
        message_data = await db_manager.get_message_leaderboard(guild_id=guild.id, limit=10)
        
        # Create message leaderboard embed
        embed = discord.Embed(
            title=f"{guild.name} - Message Leaderboard",
            color=0x9966cc
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
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        # Add footer
        from datetime import datetime
        embed.set_footer(text=f"Last updated • {datetime.utcnow().strftime('%H:%M UTC')}")
        
        # Send the embed
        try:
            message = await channel.send(embed=embed)
            print(f"Sent message leaderboard to {guild.name}: {message.id}")
        except discord.Forbidden:
            print(f"No permission to send messages in {channel.name}")
        except Exception as e:
            print(f"Error sending message leaderboard: {e}")
        
        # Get voice leaderboard data
        voice_data = await db_manager.get_voice_leaderboard(guild_id=guild.id, limit=10)
        
        # Create voice leaderboard embed
        embed = discord.Embed(
            title=f"{guild.name} - Voice Activity Leaderboard",
            color=0x9966cc
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
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        # Add footer
        embed.set_footer(text=f"Last updated • {datetime.utcnow().strftime('%H:%M UTC')}")
        
        # Send the embed
        try:
            message = await channel.send(embed=embed)
            print(f"Sent voice leaderboard to {guild.name}: {message.id}")
        except discord.Forbidden:
            print(f"No permission to send messages in {channel.name}")
        except Exception as e:
            print(f"Error sending voice leaderboard: {e}")
        
        await db_manager.close()
        await bot.close()
    
    # Start the bot
    await bot.start(config.TOKEN)

if __name__ == "__main__":
    asyncio.run(send_to_specific_guild())