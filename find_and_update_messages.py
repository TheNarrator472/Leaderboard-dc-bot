#!/usr/bin/env python3
"""Find and update specific leaderboard messages in guild 1315029949211738222."""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(__file__))

import discord
from discord.ext import commands
from config import Config
from database.manager import DatabaseManager

async def find_and_update_messages():
    """Find the specific messages and update them."""
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
        voice_leaderboard_channel_id = 1404855743596728374  # This is actually a channel ID
        
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
        print(f"Guild has {len(guild.text_channels)} text channels")
        
        # Get the voice leaderboard channel
        voice_channel = bot.get_channel(voice_leaderboard_channel_id)
        if not voice_channel:
            print(f"Voice channel {voice_leaderboard_channel_id} not found")
            await bot.close()
            return
        
        print(f"Found voice channel: {voice_channel.name}")
        
        # Find the message leaderboard in any channel
        message_found = False
        for channel in guild.text_channels:
            try:
                message = await channel.fetch_message(message_leaderboard_id)
                if message:
                    print(f"Found message leaderboard in #{channel.name}")
                    
                    # Update message leaderboard
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
                    
                    await message.edit(embed=embed)
                    print(f"Updated message leaderboard: {message_leaderboard_id}")
                    message_found = True
                    break
                    
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                continue
        
        if not message_found:
            print("Message leaderboard not found, creating new one in voice channel")
            # Create new message leaderboard in voice channel
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
            
            new_msg = await voice_channel.send(embed=embed)
            print(f"Created new message leaderboard: {new_msg.id}")
        
        # Create/update voice leaderboard in the voice channel
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
        
        # Send voice leaderboard
        voice_msg = await voice_channel.send(embed=embed)
        print(f"Created voice leaderboard: {voice_msg.id}")
        
        print(f"\nChannel info:")
        print(f"Voice channel ID: {voice_channel.id}")
        print(f"Channel name: {voice_channel.name}")
        print(f"Guild: {guild.name} ({guild.id})")
        
        await db_manager.close()
        await bot.close()
    
    # Start the bot
    await bot.start(config.TOKEN)

if __name__ == "__main__":
    asyncio.run(find_and_update_messages())