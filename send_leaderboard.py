#!/usr/bin/env python3
"""Send leaderboards to separate channels in guild 1315029949211738222."""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(__file__))

import discord
from discord.ext import commands
from config import Config
from database.manager import DatabaseManager

async def send_to_separate_channels():
    """Send message and voice leaderboards to separate channels."""
    config = Config()
    
    # Initialize bot
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    @bot.event
    async def on_ready():
        print(f"Bot connected as {bot.user}")
        
        # Target guild
        target_guild_id = 1315029949211738222
        
        # Initialize database
        db_manager = DatabaseManager(config.DATABASE_PATH)
        await db_manager.initialize()
        
        # Get the target guild
        guild = bot.get_guild(target_guild_id)
        if not guild:
            print(f"Guild {target_guild_id} not found")
            await bot.close()
            return
        
        print(f"Found guild: {guild.name}")
        print("Available channels:")
        for ch in guild.text_channels:
            print(f"  - {ch.name} (ID: {ch.id})")
        
        # Find message leaderboard channel (look for names containing "message", "msg", or "text")
        message_channel = None
        for ch in guild.text_channels:
            if any(keyword in ch.name.lower() for keyword in ['message', 'msg', 'text', 'chat']):
                message_channel = ch
                break
        
        # Find voice leaderboard channel (we know this one)
        voice_channel = bot.get_channel(1404855743596728374)  # vc-lb channel
        
        if not message_channel:
            print("Message leaderboard channel not found, using first available channel")
            message_channel = guild.text_channels[0] if guild.text_channels else None
        
        if not voice_channel:
            print("Voice leaderboard channel not found")
            await bot.close()
            return
        
        print(f"Message channel: {message_channel.name} (ID: {message_channel.id})")
        print(f"Voice channel: {voice_channel.name} (ID: {voice_channel.id})")
        
        # Send MESSAGE LEADERBOARD to message channel
        message_data = await db_manager.get_message_leaderboard(guild_id=guild.id, limit=10)
        
        embed = discord.Embed(
            title=f"{guild.name} - Message Leaderboard",
            color=0x571173
        )
        
        if not message_data:
            embed.description = "No activity data available yet"
        else:
            leaderboard_lines = []
            for i, (user_id, count) in enumerate(message_data, 1):
                user = bot.get_user(user_id)
                username = user.display_name if user else f"User {user_id}"
                
                if i == 1:
                    rank_text = f"👑 **{i}** - "
                else:
                    rank_text = f"**{i}.** "
                
                leaderboard_lines.append(f"{rank_text}{username} - **{count} messages**")
            
            embed.description = "\n".join(leaderboard_lines)
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        from datetime import datetime
        embed.set_footer(text=f"Last updated • {datetime.utcnow().strftime('%H:%M UTC')}")
        
        # Send to message channel
        try:
            msg = await message_channel.send(embed=embed)
            print(f"Sent message leaderboard to #{message_channel.name}: {msg.id}")
        except Exception as e:
            print(f"Error sending message leaderboard: {e}")
        
        # Send VOICE LEADERBOARD to voice channel
        voice_data = await db_manager.get_voice_leaderboard(guild_id=guild.id, limit=10)
        
        embed = discord.Embed(
            title=f"{guild.name} - Voice Activity Leaderboard",
            color=0x571173
        )
        
        if not voice_data:
            embed.description = "No voice activity data available yet"
        else:
            leaderboard_lines = []
            for i, (user_id, total_time) in enumerate(voice_data, 1):
                user = bot.get_user(user_id)
                username = user.display_name if user else f"User {user_id}"
                
                hours = total_time // 3600
                minutes = (total_time % 3600) // 60
                time_str = f"{hours}h {minutes}m"
                
                if i == 1:
                    rank_text = f"👑 **{i}** - "
                else:
                    rank_text = f"**{i}.** "
                
                leaderboard_lines.append(f"{rank_text}{username} - **{time_str}**")
            
            embed.description = "\n".join(leaderboard_lines)
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.set_footer(text=f"Last updated • {datetime.utcnow().strftime('%H:%M UTC')}")
        
        # Send to voice channel
        try:
            msg = await voice_channel.send(embed=embed)
            print(f"Sent voice leaderboard to #{voice_channel.name}: {msg.id}")
        except Exception as e:
            print(f"Error sending voice leaderboard: {e}")
        
        await db_manager.close()
        await bot.close()
    
    # Start the bot
    await bot.start(config.TOKEN)

if __name__ == "__main__":
    asyncio.run(send_to_separate_channels())