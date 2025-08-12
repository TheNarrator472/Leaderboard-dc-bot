#!/usr/bin/env python3
"""Fix styling and test the delete-then-send functionality."""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(__file__))

import discord
from discord.ext import commands
from config import Config
from database.manager import DatabaseManager

async def fix_style_and_test():
    """Fix styling - remove numbers, keep only purple arrow for #1."""
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
        
        print(f"Testing delete-then-send in: {message_channel.name}, {voice_channel.name}")
        
        # Test MESSAGE LEADERBOARD with fixed styling
        message_data = await db_manager.get_message_leaderboard(guild_id=target_guild_id, limit=10)
        
        embed = discord.Embed(
            title=f"{message_channel.guild.name} - Message Leaderboard",
            color=0x571173
        )
        
        if not message_data:
            embed.description = "No activity data available yet"
        else:
            leaderboard_lines = []
            for i, (user_id, count) in enumerate(message_data, 1):
                user = bot.get_user(user_id)
                username = user.display_name if user else f"User {user_id}"
                
                # Only purple arrow for #1, no numbers for others
                if i == 1:
                    rank_text = f"<a:purp_arrow:1403295268505522187> "
                else:
                    rank_text = ""
                
                leaderboard_lines.append(f"{rank_text}{username} - **{count} messages**")
            
            embed.description = "\n".join(leaderboard_lines)
        
        if message_channel.guild.icon:
            embed.set_thumbnail(url=message_channel.guild.icon.url)
        
        from datetime import datetime
        embed.set_footer(text=f"Fixed Style • {datetime.utcnow().strftime('%H:%M UTC')}")
        
        # Delete old message first
        setting_key = f"message_leaderboard_id_{target_guild_id}"
        old_id = await db_manager.get_setting(setting_key)
        
        if old_id:
            try:
                old_msg = await message_channel.fetch_message(int(old_id))
                await old_msg.delete()
                print(f"✓ Deleted old message: {old_id}")
                await asyncio.sleep(0.5)  # Wait for deletion
            except Exception as e:
                print(f"Could not delete old message {old_id}: {e}")
        
        # Send new message
        new_msg = await message_channel.send(embed=embed)
        await db_manager.set_setting(setting_key, str(new_msg.id))
        print(f"✓ Sent new message leaderboard: {new_msg.id}")
        
        # Test VOICE LEADERBOARD with same fixed styling
        voice_data = await db_manager.get_voice_leaderboard(guild_id=target_guild_id, limit=10)
        
        embed = discord.Embed(
            title=f"{voice_channel.guild.name} - Voice Activity Leaderboard",
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
                
                # Only purple arrow for #1, no numbers for others
                if i == 1:
                    rank_text = f"<a:purp_arrow:1403295268505522187> "
                else:
                    rank_text = ""
                
                leaderboard_lines.append(f"{rank_text}{username} - **{time_str}**")
            
            embed.description = "\n".join(leaderboard_lines)
        
        if voice_channel.guild.icon:
            embed.set_thumbnail(url=voice_channel.guild.icon.url)
        
        embed.set_footer(text=f"Fixed Style • {datetime.utcnow().strftime('%H:%M UTC')}")
        
        # Delete old voice message first
        setting_key = f"voice_leaderboard_id_{target_guild_id}"
        old_id = await db_manager.get_setting(setting_key)
        
        if old_id:
            try:
                old_msg = await voice_channel.fetch_message(int(old_id))
                await old_msg.delete()
                print(f"✓ Deleted old voice message: {old_id}")
                await asyncio.sleep(0.5)  # Wait for deletion
            except Exception as e:
                print(f"Could not delete old voice message {old_id}: {e}")
        
        # Send new voice message
        new_msg = await voice_channel.send(embed=embed)
        await db_manager.set_setting(setting_key, str(new_msg.id))
        print(f"✓ Sent new voice leaderboard: {new_msg.id}")
        
        print("\n✓ Fixed styling:")
        print("  - Removed numbers before usernames")
        print("  - Only purple arrow emoji for #1 rank")
        print("  - Clean delete-then-send functionality")
        print("  - Color: #571173")
        
        await db_manager.close()
        await bot.close()
    
    # Start the bot
    await bot.start(config.TOKEN)

if __name__ == "__main__":
    asyncio.run(fix_style_and_test())