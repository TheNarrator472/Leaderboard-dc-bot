#!/usr/bin/env python3
"""Debug and send updated leaderboards with new color and emoji."""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(__file__))

import discord
from discord.ext import commands
from config import Config
from database.manager import DatabaseManager

async def send_debug_leaderboards():
    """Send leaderboards with new color (571173) and purple arrow emoji."""
    config = Config()
    
    # Initialize bot
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    @bot.event
    async def on_ready():
        print(f"Bot connected as {bot.user}")
        
        # Target guild and channels
        target_guild_id = 1315029949211738222
        message_channel_id = 1404855785183252572  # chat-lb
        voice_channel_id = 1404855743596728374    # vc-lb
        
        # Initialize database
        db_manager = DatabaseManager(config.DATABASE_PATH)
        await db_manager.initialize()
        
        # Get channels
        message_channel = bot.get_channel(message_channel_id)
        voice_channel = bot.get_channel(voice_channel_id)
        
        if not message_channel or not voice_channel:
            print("Channels not found")
            await bot.close()
            return
        
        print(f"Sending to channels: {message_channel.name}, {voice_channel.name}")
        
        # Send MESSAGE LEADERBOARD with new style
        message_data = await db_manager.get_message_leaderboard(guild_id=target_guild_id, limit=10)
        
        embed = discord.Embed(
            title=f"{message_channel.guild.name} - Message Leaderboard",
            color=0x571173  # New purple color
        )
        
        if not message_data:
            embed.description = "No activity data available yet"
        else:
            leaderboard_lines = []
            for i, (user_id, count) in enumerate(message_data, 1):
                user = bot.get_user(user_id)
                username = user.display_name if user else f"User {user_id}"
                
                if i == 1:
                    rank_text = f"<a:purp_arrow:1403295268505522187> **{i}** - "  # Purple arrow emoji
                else:
                    rank_text = f"**{i}.** "
                
                leaderboard_lines.append(f"{rank_text}{username} - **{count} messages**")
            
            embed.description = "\n".join(leaderboard_lines)
        
        if message_channel.guild.icon:
            embed.set_thumbnail(url=message_channel.guild.icon.url)
        
        from datetime import datetime
        embed.set_footer(text=f"Updated Style • {datetime.utcnow().strftime('%H:%M UTC')}")
        
        # Send message leaderboard
        msg = await message_channel.send(embed=embed)
        print(f"Sent updated message leaderboard: {msg.id}")
        
        # Send VOICE LEADERBOARD with new style
        voice_data = await db_manager.get_voice_leaderboard(guild_id=target_guild_id, limit=10)
        
        embed = discord.Embed(
            title=f"{voice_channel.guild.name} - Voice Activity Leaderboard",
            color=0x571173  # New purple color
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
                    rank_text = f"<a:purp_arrow:1403295268505522187> **{i}** - "  # Purple arrow emoji
                else:
                    rank_text = f"**{i}.** "
                
                leaderboard_lines.append(f"{rank_text}{username} - **{time_str}**")
            
            embed.description = "\n".join(leaderboard_lines)
        
        if voice_channel.guild.icon:
            embed.set_thumbnail(url=voice_channel.guild.icon.url)
        
        embed.set_footer(text=f"Updated Style • {datetime.utcnow().strftime('%H:%M UTC')}")
        
        # Send voice leaderboard
        msg = await voice_channel.send(embed=embed)
        print(f"Sent updated voice leaderboard: {msg.id}")
        
        print("✓ Updated leaderboards with new color (0x571173) and purple arrow emoji")
        print("✓ Color: #571173 (dark purple)")
        print("✓ Emoji: <a:purp_arrow:1403295268505522187> for #1 rank")
        
        await db_manager.close()
        await bot.close()
    
    # Start the bot
    await bot.start(config.TOKEN)

if __name__ == "__main__":
    asyncio.run(send_debug_leaderboards())