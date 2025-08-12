#!/usr/bin/env python3
"""Update specific leaderboard messages by their IDs."""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(__file__))

import discord
from discord.ext import commands
from config import Config
from database.manager import DatabaseManager

async def update_specific_messages():
    """Update the specific leaderboard messages."""
    config = Config()
    
    # Initialize bot
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    @bot.event
    async def on_ready():
        print(f"Bot connected as {bot.user}")
        
        # Target guild and message IDs
        target_guild_id = 1315029949211738222
        message_leaderboard_id = 1404855785183252572
        voice_channel_id = 1404855743596728374
        
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
        
        # Find the channel containing the messages
        channel = None
        for ch in guild.text_channels:
            try:
                # Try to fetch the message leaderboard message
                msg = await ch.fetch_message(message_leaderboard_id)
                if msg:
                    channel = ch
                    break
            except (discord.NotFound, discord.Forbidden):
                continue
        
        if not channel:
            print("Could not find channel with the message leaderboard")
            await bot.close()
            return
        
        print(f"Found channel: {channel.name}")
        
        # Update message leaderboard
        try:
            message_data = await db_manager.get_message_leaderboard(guild_id=guild.id, limit=10)
            
            embed = discord.Embed(
                title=f"{guild.name} - Message Leaderboard",
                color=0x9966cc
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
            
            # Update the message
            message = await channel.fetch_message(message_leaderboard_id)
            await message.edit(embed=embed)
            print(f"Updated message leaderboard: {message_leaderboard_id}")
            
        except Exception as e:
            print(f"Error updating message leaderboard: {e}")
        
        # Update voice leaderboard (check if it's a separate message or same channel)
        try:
            voice_data = await db_manager.get_voice_leaderboard(guild_id=guild.id, limit=10)
            
            embed = discord.Embed(
                title=f"{guild.name} - Voice Activity Leaderboard",
                color=0x9966cc
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
            
            # Try to find voice leaderboard message (it might be in same channel or different)
            voice_message = None
            try:
                voice_message = await channel.fetch_message(voice_channel_id)
            except discord.NotFound:
                # Try other channels
                for ch in guild.text_channels:
                    try:
                        voice_message = await ch.fetch_message(voice_channel_id)
                        break
                    except discord.NotFound:
                        continue
            
            if voice_message:
                await voice_message.edit(embed=embed)
                print(f"Updated voice leaderboard: {voice_channel_id}")
            else:
                # Send new voice leaderboard message
                new_voice_msg = await channel.send(embed=embed)
                print(f"Created new voice leaderboard: {new_voice_msg.id}")
            
        except Exception as e:
            print(f"Error updating voice leaderboard: {e}")
        
        await db_manager.close()
        await bot.close()
    
    # Start the bot
    await bot.start(config.TOKEN)

if __name__ == "__main__":
    asyncio.run(update_specific_messages())