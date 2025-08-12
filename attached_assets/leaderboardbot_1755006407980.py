import discord
from discord.ext import commands, tasks
import sqlite3
import time

# ======================
# CONFIG
TOKEN = "YOUR_BOT_TOKEN"
PREFIX = "!"
MESSAGE_CHANNEL_ID = 123456789012345678  # Channel for message leaderboard
VOICE_CHANNEL_ID = 987654321098765432    # Channel for voice leaderboard
UPDATE_INTERVAL = 300  # seconds (5 minutes)
# ======================

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Database setup
conn = sqlite3.connect("leaderboard.db")
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS messages (
                user_id INTEGER PRIMARY KEY,
                count INTEGER DEFAULT 0
            )""")
c.execute("""CREATE TABLE IF NOT EXISTS voice (
                user_id INTEGER PRIMARY KEY,
                total_time INTEGER DEFAULT 0,
                join_time INTEGER
            )""")
c.execute("""CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )""")
conn.commit()

# -----------------
# HELPER FUNCTIONS
# -----------------
def add_message(user_id):
    with conn:
        c.execute("INSERT OR IGNORE INTO messages (user_id, count) VALUES (?, ?)", (user_id, 0))
        c.execute("UPDATE messages SET count = count + 1 WHERE user_id = ?", (user_id,))

def user_join_vc(user_id):
    with conn:
        c.execute("INSERT OR IGNORE INTO voice (user_id, total_time, join_time) VALUES (?, ?, ?)",
                  (user_id, 0, int(time.time())))
        c.execute("UPDATE voice SET join_time = ? WHERE user_id = ?", (int(time.time()), user_id))

def user_leave_vc(user_id):
    with conn:
        c.execute("SELECT join_time FROM voice WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if row and row[0]:
            join_time = row[0]
            total_time = int(time.time()) - join_time
            c.execute("UPDATE voice SET total_time = total_time + ?, join_time = NULL WHERE user_id = ?",
                      (total_time, user_id))

def get_message_leaderboard(limit=10):
    c.execute("SELECT user_id, count FROM messages ORDER BY count DESC LIMIT ?", (limit,))
    return c.fetchall()

def get_voice_leaderboard(limit=10):
    c.execute("SELECT user_id, total_time, join_time FROM voice")
    data = []
    now = int(time.time())
    for user_id, total_time, join_time in c.fetchall():
        if join_time:  # still in VC
            total_time += now - join_time
        data.append((user_id, total_time))
    data.sort(key=lambda x: x[1], reverse=True)
    return data[:limit]

def get_setting(key):
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    return int(row[0]) if row else None

def set_setting(key, value):
    with conn:
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))

# -----------------
# BOT EVENTS
# -----------------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    update_message_leaderboard.start()
    update_voice_leaderboard.start()

@bot.event
async def on_message(message):
    if not message.author.bot:
        add_message(message.author.id)
    await bot.process_commands(message)

@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel is None and after.channel is not None:  # joined VC
        user_join_vc(member.id)
    elif before.channel is not None and after.channel is None:  # left VC
        user_leave_vc(member.id)
    elif before.channel != after.channel:  # switched VC
        user_leave_vc(member.id)
        user_join_vc(member.id)

# -----------------
# BACKGROUND LOOPS
# -----------------
@tasks.loop(seconds=UPDATE_INTERVAL)
async def update_message_leaderboard():
    channel = bot.get_channel(MESSAGE_CHANNEL_ID)
    if channel:
        leaderboard = get_message_leaderboard()
        embed = discord.Embed(
            title="📨 Message Leaderboard",
            description="Top chatters in the server",
            color=discord.Color.blue()
        )
        for i, (user_id, count) in enumerate(leaderboard, start=1):
            user = bot.get_user(user_id)
            name = user.name if user else f"User {user_id}"
            embed.add_field(name=f"{i}. {name}", value=f"💬 {count} messages", inline=False)
        embed.set_footer(text="Auto-updates every 5 minutes")

        msg_id = get_setting("msg_leaderboard_id")
        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=embed)
            except discord.NotFound:
                msg = await channel.send(embed=embed)
                set_setting("msg_leaderboard_id", msg.id)
        else:
            msg = await channel.send(embed=embed)
            set_setting("msg_leaderboard_id", msg.id)

@tasks.loop(seconds=UPDATE_INTERVAL)
async def update_voice_leaderboard():
    channel = bot.get_channel(VOICE_CHANNEL_ID)
    if channel:
        leaderboard = get_voice_leaderboard()
        embed = discord.Embed(
            title="🎙 Voice Chat Leaderboard",
            description="Most active VC users",
            color=discord.Color.green()
        )
        for i, (user_id, total_time) in enumerate(leaderboard, start=1):
            hours = total_time // 3600
            minutes = (total_time % 3600) // 60
            user = bot.get_user(user_id)
            name = user.name if user else f"User {user_id}"
            embed.add_field(name=f"{i}. {name}", value=f"🕒 {hours}h {minutes}m", inline=False)
        embed.set_footer(text="Auto-updates every 5 minutes")

        msg_id = get_setting("vc_leaderboard_id")
        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=embed)
            except discord.NotFound:
                msg = await channel.send(embed=embed)
                set_setting("vc_leaderboard_id", msg.id)
        else:
            msg = await channel.send(embed=embed)
            set_setting("vc_leaderboard_id", msg.id)

bot.run(TOKEN)
