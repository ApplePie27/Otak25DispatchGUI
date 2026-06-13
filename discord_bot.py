import discord
from discord.ext import commands
import sqlite3
import configparser
import asyncio
import threading
import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

print("========================================")
print("🟢 INITIALIZING HQ DISCORD BOT V5.0 (READ ONLY)...")
print("========================================")

try:
    config = configparser.ConfigParser()
    config.optionxform = str
    config.read('config.ini')

    DISCORD_TOKEN = config.get('DISCORD', 'bot_token', fallback="").strip()
    DB_PATH = config.get('DATABASE', 'filename', fallback='dispatch.db')
    PORT = 8080

    CHANNEL_MAP = {
        "General": int(config.get('DISCORD', 'general_channel', fallback="0")),
        "Safety": int(config.get('DISCORD', 'safety_channel', fallback="0")),
        "First Aid": int(config.get('DISCORD', 'first_aid_channel', fallback="0")),
        "Code Adam": int(config.get('DISCORD', 'code_adam_channel', fallback="0"))
    }
    
except Exception as e:
    print(f"❌ ERROR LOADING CONFIG.INI: {e}")
    sys.exit(1)

# UPDATED LISTS BASED ON NEW PROTOCOL
ALLOWED_DISCORD_CODES = ["Adam", "Blue", "Yellow"]
HIGH_PRIORITY_CODES = ["White / Mayday", "Silver", "Black", "Red", "Blue", "Adam"]

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

def get_db_connection():
    abs_path = os.path.abspath(DB_PATH)
    conn = sqlite3.connect(abs_path, timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=TRUNCATE;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA cache_size=-64000;")
    conn.execute("PRAGMA busy_timeout=20000;")
    return conn

def generate_embed(row):
    row = dict(row)
    report_id = row['ReportID']
    is_resolved = str(row.get('ResolutionStatus', 'False')).lower() in ('1', 'true')
    is_cancelled = str(row.get('Cancelled', 'False')).lower() in ('1', 'true')
    code = str(row.get('Code', ''))
    
    if is_cancelled: 
        color, title = discord.Color.light_grey(), f"🚫 Cancelled/Void: {report_id}"
    elif is_resolved: 
        color, title = discord.Color.green(), f"✅ Resolved: {report_id}"
    else:
        # DYNAMIC EMOJIS BASED ON NEW CODES
        if code == "Blue":
            color, title = discord.Color.blue(), f"🔵 Blue Alert: {report_id}"
        elif code == "Yellow":
            color, title = discord.Color.gold(), f"🟡 Yellow Alert: {report_id}"
        elif code == "Adam":
            color, title = discord.Color.magenta(), f"🧸 Code Adam: {report_id}"
        elif code == "White / Mayday":
            color, title = discord.Color.light_grey(), f"⚪ MAYDAY: {report_id}"
        elif code == "Silver":
            color, title = discord.Color.light_grey(), f"⚔️ Silver Alert: {report_id}"
        elif code == "Black":
            color, title = discord.Color.dark_theme(), f"⚫ Black Alert: {report_id}"
        elif code == "Red":
            color, title = discord.Color.red(), f"🔴 Red Alert: {report_id}"
        else:
            color, title = discord.Color.orange(), f"🚨 HQ Alert: {report_id}"

    safe_desc = str(row.get('Description', ''))
    if len(safe_desc) > 4000: safe_desc = safe_desc[:3997] + "..."

    embed = discord.Embed(title=title, description=safe_desc, color=color)
    embed.add_field(name="Location", value=str(row.get('Location', ''))[:1024], inline=True)
    embed.add_field(name="Source Dept", value=str(row.get('Source', '')).replace("Discord: ", "")[:1024], inline=True)
    embed.add_field(name="Incident Code", value=code[:1024] if code else "No_Code", inline=True)
        
    if is_resolved:
        embed.add_field(name="Resolution State", value=f"Resolved by {row.get('ResolvedBy', '')} at {row.get('ResolutionTimestamp', '')}", inline=False)
        
    embed.set_footer(text="HQ Dispatch Center - Read Only Log")
    return embed


# ==========================================
# HQ TO DISCORD BACKGROUND SIGNALING
# ==========================================
class LocalCommunicationServer(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        data = json.loads(self.rfile.read(content_length).decode('utf-8'))
        
        print(f"📥 [IPC SIGNAL RECEIVED] Endpoint: {self.path} | Data: {data}")
        
        if self.path == "/dispatch":
            asyncio.run_coroutine_threadsafe(post_dispatch_message(data.get("report_id"), data.get("source")), bot.loop)
            self.send_response(200)
            self.end_headers()
        elif self.path == "/update":
            asyncio.run_coroutine_threadsafe(edit_dispatch_message(data.get("report_id")), bot.loop)
            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

async def post_dispatch_message(report_id, source):
    await asyncio.sleep(0.5)
    conn = get_db_connection()
    try:
        conn.commit()
        row = conn.execute("SELECT * FROM calls WHERE ReportID = ?", (report_id,)).fetchone()
        if not row: return
        
        incident_code = str(row['Code'])
        
        # FILTER: Only post if the code is Adam or First Aid (Blue/Yellow)
        if incident_code not in ALLOWED_DISCORD_CODES: 
            print(f"⏩ [SKIPPED] {report_id} has code {incident_code} (Not configured for Discord broadcast).")
            return

        # SMART ROUTING
        if incident_code == "Adam":
            target_channel_id = CHANNEL_MAP.get("Code Adam")
        elif incident_code in ["Blue", "Yellow"]:
            target_channel_id = CHANNEL_MAP.get("First Aid")
        else:
            target_channel_id = CHANNEL_MAP.get(source, CHANNEL_MAP["General"])

        if target_channel_id == 0:
            target_channel_id = CHANNEL_MAP.get("General")

        channel = bot.get_channel(target_channel_id) or await bot.fetch_channel(target_channel_id)

        embed = generate_embed(row)
            
        msg = await channel.send(embed=embed)
        conn.execute("UPDATE calls SET DiscordMessageID=?, DiscordChannelID=? WHERE ReportID=?", (str(msg.id), str(channel.id), report_id))
        conn.commit()
        
        print(f"✅ [SUCCESS] {report_id} posted to Discord channel {channel.name}!")
        
        if incident_code.upper() in [c.upper() for c in HIGH_PRIORITY_CODES]:
            try: await msg.create_thread(name=f"🚨 HQ Alert: {report_id}", auto_archive_duration=1440)
            except Exception as thread_err: print(f"⚠️ THREAD ERROR: {thread_err}")
            
    except Exception as e: print(f"❌ [BOT ERROR] Post failed: {e}")
    finally: conn.close()

async def edit_dispatch_message(report_id):
    await asyncio.sleep(0.5)
    conn = get_db_connection()
    try:
        conn.commit()
        row = conn.execute("SELECT * FROM calls WHERE ReportID = ?", (report_id,)).fetchone()
        
        if not row or not row['DiscordMessageID'] or not row['DiscordChannelID']: return
            
        channel = bot.get_channel(int(row['DiscordChannelID'])) or await bot.fetch_channel(int(row['DiscordChannelID']))
        message = await channel.fetch_message(int(row['DiscordMessageID']))
        
        embed = generate_embed(row)
        await message.edit(embed=embed)
        print(f"🔄 [UPDATED] {report_id} modified on Discord.")
        
    except Exception as e: print(f"❌ [BOT ERROR] Discord update failed: {e}")
    finally: conn.close()

@bot.event
async def on_ready():
    bot.tree.clear_commands(guild=None)
    await bot.tree.sync()
    print(f"✅ Read-Only Logger successfully logged into Discord as {bot.user}")
    print("🚨 BOT IS FULLY ONLINE AND READY.")

if __name__ == "__main__":
    try:
        if not DISCORD_TOKEN: sys.exit("❌ FATAL: DISCORD_TOKEN is empty.")
        threading.Thread(target=lambda: HTTPServer(('localhost', PORT), LocalCommunicationServer).serve_forever(), daemon=True).start()
        bot.run(DISCORD_TOKEN)
    except Exception as e: traceback.print_exc()