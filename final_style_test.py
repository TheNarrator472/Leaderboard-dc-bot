#!/usr/bin/env python3
"""Final styling test - purple arrows for all top 10, bold titles, proper usernames."""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(__file__))

import discord
from discord.ext import commands
from config import Config
from database.manager import DatabaseManager

async def final_style_test():
    """Test final styling with purple arrows for all members and bold titles."""
    config = Config()
    
    # Initialize bot
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    async def get_proper_username(user_id: int) -> str:
        """Get proper username with comprehensive fallback."""
        try:
            # Try bot cache first
            user = bot.get_user(user_id)
            if user:
                return user.global_name or user.display_name or user.name
            
            # Try fetching user
            try:
                user = await bot.fetch_user(user_id)
                if user:
                    return user.global_name or user.display_name or user.name
            except:
                pass
            
            # Try guild members
            for guild in bot.guilds:
                try:
                    member = guild.get_member(user_id)
                    if member:
                        return member.global_name or member.display_name or member.name
                except:
                    continue
            
            # Fallback
            return f"Unknown User"
            
        except Exception as e:
            print(f"Error getting username for {user_id}: {e}")
            return f"Unknown User"
    
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
        
        print(f"Final test in: {message_channel.name}, {voice_channel.name}")
        
        # MESSAGE LEADERBOARD with final styling
        message_data = await db_manager.get_message_leaderboard(guild_id=target_guild_id, limit=10)
        
        embed = discord.Embed(
            title=f"**{message_channel.guild.name} - Message Leaderboard**",  # Bold title
            color=0x571173
        )
        
        if not message_data:
            embed.description = "No activity data available yet"
        else:
            leaderboard_lines = []
            for i, (user_id, count) in enumerate(message_data, 1):
                # Get proper username
                username = await get_proper_username(user_id)
                
                # Purple arrow for ALL top 10 members
                rank_text = f"<a:purp_arrow:1403295268505522187> "
                
                leaderboard_lines.append(f"{rank_text}{username} - **{count} messages**")
            
            embed.description = "\n".join(leaderboard_lines)
        
        if message_channel.guild.icon:
            embed.set_thumbnail(url=message_channel.guild.icon.url)
        
        from datetime import datetime
        embed.set_footer(text=f"Final Style • {datetime.utcnow().strftime('%H:%M UTC')}")
        
        # Delete old and send new
        setting_key = f"message_leaderboard_id_{target_guild_id}"
        old_id = await db_manager.get_setting(setting_key)
        
        if old_id:
            try:
                old_msg = await message_channel.fetch_message(int(old_id))
                await old_msg.delete()
                print(f"✓ Deleted old message: {old_id}")
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Could not delete old message: {e}")
        
        new_msg = await message_channel.send(embed=embed)
        await db_manager.set_setting(setting_key, str(new_msg.id))
        print(f"✓ Sent final message leaderboard: {new_msg.id}")
        
        # VOICE LEADERBOARD with final styling
        voice_data = await db_manager.get_voice_leaderboard(guild_id=target_guild_id, limit=10)
        
        embed = discord.Embed(
            title=f"**{voice_channel.guild.name} - Voice Activity Leaderboard**",  # Bold title
            color=0x571173
        )
        
        if not voice_data:
            embed.description = "No voice activity data available yet"
        else:
            leaderboard_lines = []
            for i, (user_id, total_time) in enumerate(voice_data, 1):
                # Get proper username
                username = await get_proper_username(user_id)
                
                hours = total_time // 3600
                minutes = (total_time % 3600) // 60
                time_str = f"{hours}h {minutes}m"
                
                # Purple arrow for ALL top 10 members
                rank_text = f"<a:purp_arrow:1403295268505522187> "
                
                leaderboard_lines.append(f"{rank_text}{username} - **{time_str}**")
            
            embed.description = "\n".join(leaderboard_lines)
        
        if voice_channel.guild.icon:
            embed.set_thumbnail(url=voice_channel.guild.icon.url)
        
        embed.set_footer(text=f"Final Style • {datetime.utcnow().strftime('%H:%M UTC')}")
        
        # Delete old and send new
        setting_key = f"voice_leaderboard_id_{target_guild_id}"
        old_id = await db_manager.get_setting(setting_key)
        
        if old_id:
            try:
                old_msg = await voice_channel.fetch_message(int(old_id))
                await old_msg.delete()
                print(f"✓ Deleted old voice message: {old_id}")
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Could not delete old voice message: {e}")
        
        new_msg = await voice_channel.send(embed=embed)
        await db_manager.set_setting(setting_key, str(new_msg.id))
        print(f"✓ Sent final voice leaderboard: {new_msg.id}")
        
        print("\n✓ Final styling applied:")
        print("  - Purple arrows for ALL top 10 members")
        print("  - Bold titles with ** formatting")
        print("  - Improved username resolution")
        print("  - Clean delete-then-send")
        print("  - Color: #571173")
        
        await db_manager.close()
        await bot.close()
    
    # Start the bot
    await bot.start(config.TOKEN)

if __name__ == "__main__":
    asyncio.run(final_style_test())