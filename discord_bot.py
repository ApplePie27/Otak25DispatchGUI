"""
DISCORD_BOT.PY
Companion bot for the HQ Dispatch System.
Acts as a read-only notification pipeline, routing Medical/First Aid 
alerts to Discord and silently logging field replies back to the local database.
"""
import discord
from discord.ext import commands
from aiohttp import web
import sqlite3
import json
import asyncio
import configparser
import os
from datetime import datetime
import time

# ==========================================
# CONFIGURATION & SETUP
# ==========================================
config = configparser.ConfigParser()
config.read('config.ini')

BOT_TOKEN = config.get('DISCORD', 'bot_token', fallback='')
FIRST_AID_CHANNEL_ID = config.getint('DISCORD', 'first_aid_channel', fallback=0)
DB_PATH = config.get('DATABASE', 'filename', fallback='dispatch.db')

# Strict routing: Bot will only broadcast these codes
ALLOWED_DISCORD_CODES = ["Blue", "Yellow"]

# Enable necessary intents (requires Message Content intent in Discord Dev Portal)
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================================
# DATABASE HELPER
# ==========================================
def get_db_connection():
    """Returns a dictionary-like cursor for SQLite with retry logic for SMB networks."""
    retries = 5
    while retries > 0:
        try:
            # timeout=20.0 allows it to wait in line if the GUI is currently writing
            conn = sqlite3.connect(DB_PATH, timeout=20.0)
            
            # MATCH THE GUI'S PRAGMAS EXACTLY TO PREVENT DISK I/O ERRORS
            conn.execute("PRAGMA journal_mode=TRUNCATE;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=20000;")
            
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.OperationalError:
            retries -= 1
            time.sleep(0.5)
    raise Exception("Database Locked: Could not connect after multiple retries.")

# ==========================================
# OFFLINE MESSAGE SYNCHRONIZATION
# ==========================================
async def sync_offline_messages():
    """Scans active threads to recover any messages sent while the bot was offline."""
    print("🔄 [SYNC] Checking active threads for missed messages...")
    conn = get_db_connection()
    try:
        # Fetch all unresolved and uncancelled calls that have a Discord Thread attached
        cursor = conn.execute("SELECT ReportID, DiscordMessageID, DiscordChannelID FROM calls WHERE (ResolutionStatus = 0 OR ResolutionStatus IS NULL) AND (Cancelled = 0 OR Cancelled IS NULL) AND DiscordMessageID IS NOT NULL")
        active_calls = cursor.fetchall()

        for row in active_calls:
            report_id = row['ReportID']
            thread_id = int(row['DiscordMessageID'])
            channel_id = int(row['DiscordChannelID'])

            try:
                # Fetch the channel and thread from the Discord API
                channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
                thread = channel.get_thread(thread_id)
                if not thread:
                    try: thread = await channel.fetch_thread(thread_id)
                    except: continue # Thread might be deleted or inaccessible

                # Read the last 50 messages in the thread (oldest to newest)
                async for message in thread.history(limit=50, oldest_first=True):
                    if message.author.bot: continue

                    content = message.content.strip()
                    if message.attachments: content += f" [Attached {len(message.attachments)} file(s)]"
                    if not content: content = "[Empty Message / Sticker]"

                    user_tag = f"Discord: {message.author.display_name}"

                    # Deduplication check: Verify if this exact message is already in the database
                    check_cursor = conn.execute("SELECT 1 FROM call_history WHERE CallID = ? AND User = ? AND Details = ?", (report_id, user_tag, content))
                    
                    if not check_cursor.fetchone():
                        # Use Discord's official timestamp so the timeline remains chronologically accurate
                        original_time = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        
                        conn.execute("INSERT INTO call_history (CallID, Timestamp, User, Action, Details) VALUES (?, ?, ?, ?, ?)",
                                     (report_id, original_time, user_tag, "Thread Message", content))
                        conn.commit()
                        print(f"🔄 [SYNCED] Recovered missed message from {message.author.display_name} for {report_id}.")

            except Exception as e:
                print(f"⚠️ [SYNC ERROR] Failed to sync {report_id}: {e}")
                
    except sqlite3.OperationalError as e:
        print(f"🚨 [CRITICAL DB ERROR] Could not sync offline messages: {e}")
    except Exception as e:
        print(f"🚨 [UNEXPECTED ERROR] {e}")
    finally:
        conn.close()
    print("✅ [SYNC] Offline message recovery complete.")


# ==========================================
# DISCORD EVENTS
# ==========================================
@bot.event
async def on_ready():
    # Purge old slash commands from Discord's memory, as the bot is now strictly Read-Only
    bot.tree.clear_commands(guild=None)
    await bot.tree.sync()
    print(f"✅ Read-Only Logger successfully logged into Discord as {bot.user}")
    
    # Trigger the offline message recovery
    await sync_offline_messages()
    
    print("🚨 BOT IS FULLY ONLINE AND ROUTING EXCLUSIVELY TO FIRST AID.")

@bot.event
async def on_message(message):
    """Listens for field responder replies inside generated threads and logs them to SQLite."""
    if message.author.bot: return
    
    # Only process messages sent inside a Thread
    if not isinstance(message.channel, discord.Thread): return

    conn = get_db_connection()
    try:
        # Check if this thread belongs to an active dispatch ticket
        cursor = conn.execute("SELECT ReportID FROM calls WHERE DiscordMessageID = ?", (str(message.channel.id),))
        row = cursor.fetchone()
        
        if row:
            report_id = row['ReportID']
            content = message.content.strip()
            if message.attachments: content += f" [Attached {len(message.attachments)} file(s)]"
            if not content: content = "[Empty Message / Sticker]"
            
            user_tag = f"Discord: {message.author.display_name}"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            conn.execute("INSERT INTO call_history (CallID, Timestamp, User, Action, Details) VALUES (?, ?, ?, ?, ?)",
                         (report_id, timestamp, user_tag, "Thread Message", content))
            conn.commit()
            print(f"📥 [LOGGED] Message from {message.author.display_name} saved to ticket {report_id}")
    except Exception as e:
        print(f"⚠️ [DB ERROR] Failed to log Discord message: {e}")
    finally:
        conn.close()

# ==========================================
# IPC WEB SERVER (RECEIVES PINGS FROM GUI)
# ==========================================
def create_dispatch_embed(call_data):
    """Formats a standardized Dispatch Card embed."""
    color = discord.Color.blue() if call_data['Code'] == 'Blue' else discord.Color.gold()
    embed = discord.Embed(title=f"🚨 DISPATCH: {call_data['Code']} (ID: {call_data['ReportID']})", color=color)
    embed.add_field(name="Location", value=call_data['Location'], inline=False)
    embed.add_field(name="Description", value=call_data['Description'], inline=False)
    embed.add_field(name="Caller ID", value=call_data['Caller'], inline=True)
    embed.add_field(name="Time", value=call_data['CallTime'], inline=True)
    embed.set_footer(text="Reply directly in this thread with vitals and status updates.")
    return embed

async def handle_dispatch(request):
    """Triggered by the GUI when a new call is added."""
    data = await request.json()
    report_id = data.get('report_id')
    
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT * FROM calls WHERE ReportID = ?", (report_id,))
        call_data = cursor.fetchone()
        
        # Verify it's a valid Medical code before routing
        if not call_data or call_data['Code'] not in ALLOWED_DISCORD_CODES:
            return web.Response(text="Ignored: Code not in Allowed Discord Codes.")
            
        channel = bot.get_channel(FIRST_AID_CHANNEL_ID)
        if not channel: return web.Response(status=500, text="First Aid channel not found.")
        
        embed = create_dispatch_embed(dict(call_data))
        message = await channel.send(embed=embed)
        
        # Create dedicated thread
        thread_name = f"Ticket {report_id} - {call_data['Location'][:50]}"
        thread = await message.create_thread(name=thread_name, auto_archive_duration=1440)
        
        # Save Thread ID back to local database
        conn.execute("UPDATE calls SET DiscordMessageID = ?, DiscordChannelID = ? WHERE ReportID = ?",
                     (str(thread.id), str(channel.id), report_id))
        conn.commit()
        
        return web.Response(text="Dispatch successfully routed to Discord.")
    except Exception as e:
        print(f"⚠️ IPC Error (Dispatch): {e}")
        return web.Response(status=500, text=str(e))
    finally:
        conn.close()

async def handle_update(request):
    """Triggered by the GUI when an existing call is modified."""
    data = await request.json()
    report_id = data.get('report_id')
    
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT * FROM calls WHERE ReportID = ?", (report_id,))
        call_data = cursor.fetchone()
        
        if not call_data or not call_data['DiscordMessageID']:
            return web.Response(text="Ignored: No active Discord thread for this call.")
            
        thread_id = int(call_data['DiscordMessageID'])
        channel_id = int(call_data['DiscordChannelID'])
        
        channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
        thread = channel.get_thread(thread_id) or await channel.fetch_thread(thread_id)
        
        if not thread: return web.Response(status=404, text="Thread not found.")
        
        # If resolved or cancelled, close the thread
        if str(call_data['ResolutionStatus']).lower() in ('1', 'true', 1) or str(call_data['Cancelled']).lower() in ('1', 'true', 1):
            embed = discord.Embed(title=f"✅ TICKET {report_id} CLOSED", color=discord.Color.green())
            await thread.send(embed=embed)
            await thread.edit(archived=True, locked=True)
        else:
            embed = discord.Embed(title=f"🔄 UPDATE: TICKET {report_id}", description=call_data['Description'], color=discord.Color.orange())
            await thread.send(embed=embed)
            
        return web.Response(text="Update successfully pushed to Discord thread.")
    except Exception as e:
        print(f"⚠️ IPC Error (Update): {e}")
        return web.Response(status=500, text=str(e))
    finally:
        conn.close()

async def start_ipc_server():
    """Starts the local web server to listen for GUI pings."""
    app = web.Application()
    app.router.add_post('/dispatch', handle_dispatch)
    app.router.add_post('/update', handle_update)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()
    print("🌐 IPC Web Server listening on localhost:8080")

# ==========================================
# MAIN EXECUTION
# ==========================================
async def main():
    async with bot:
        bot.loop.create_task(start_ipc_server())
        await bot.start(BOT_TOKEN)

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("CRITICAL: BOT_TOKEN is missing from config.ini")
    else:
        asyncio.run(main())