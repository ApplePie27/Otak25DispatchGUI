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
print("🟢 INITIALIZING HQ DISCORD BOT...")
print("========================================")

# ==========================================
# LOAD CONFIGURATION
# ==========================================
try:
    config = configparser.ConfigParser()
    config.read('config.ini')

    DISCORD_TOKEN = config.get('DISCORD', 'bot_token', fallback="").strip()
    DB_PATH = config.get('DATABASE', 'filename', fallback='dispatch.db')
    PORT = 8080

    CHANNEL_MAP = {
        "Safety": int(config.get('DISCORD', 'safety_channel', fallback="0")),
        "General": int(config.get('DISCORD', 'general_channel', fallback="0")),
        "First Aid": int(config.get('DISCORD', 'first_aid_channel', fallback="0"))
    }
except Exception as e:
    print(f"❌ ERROR LOADING CONFIG.INI: {e}")
    sys.exit(1)

intents = discord.Intents.default()
intents.message_content = True
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

# ==========================================
# MASTER TEMPLATE BUILDER
# ==========================================
def generate_embed(row):
    """Builds the exact visual layout from the database row."""
    report_id = row['ReportID']
    is_answered = str(row['AnsweredStatus']).lower() in ('1', 'true')
    is_resolved = str(row['ResolutionStatus']).lower() in ('1', 'true')
    
    if is_resolved:
        color = discord.Color.green()
        title = f"✅ Resolved: {report_id}"
    elif is_answered:
        color = discord.Color.orange()
        title = f"🚨 Claimed: {report_id}"
    else:
        color = discord.Color.red()
        if "Discord" in str(row['Source']):
            title = f"🚨 Field Report: {report_id}"
        else:
            title = f"🚨 HQ Alert: {report_id}"

    # PREVENT API CRASH: Discord max description length is 4096
    safe_description = str(row['Description'])
    if len(safe_description) > 4000:
        safe_description = safe_description[:3997] + "..."

    embed = discord.Embed(title=title, description=safe_description, color=color)
    
    embed.add_field(name="Location", value=str(row['Location'])[:1024], inline=True)
    embed.add_field(name="Source Dept", value=str(row['Source']).replace("Discord: ", "")[:1024], inline=True)
    embed.add_field(name="Incident Code", value=str(row['Code'])[:1024] if row['Code'] else "No_Code", inline=True)
    
    if is_answered:
        embed.add_field(name="Assigned Responder", value=f"Claimed by {row['AnsweredBy']} at {row['AnsweredTimestamp']}", inline=False)
        
    if is_resolved:
        embed.add_field(name="Resolution State", value=f"Resolved by {row['ResolvedBy']} at {row['ResolutionTimestamp']}", inline=False)
        
    embed.set_footer(text="HQ Dispatch Center")
    return embed

class IncidentControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🙋 Claim Assignment", style=discord.ButtonStyle.green, custom_id="claim_incident_btn")
    async def claim_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Dynamically extract Report ID from the Embed Title
        report_id = interaction.message.embeds[0].title.split(': ')[-1].strip()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        user_display = interaction.user.display_name
        conn = get_db_connection()

        try:
            with conn:
                cursor = conn.execute("SELECT * FROM calls WHERE ReportID = ?", (report_id,))
                call = cursor.fetchone()
                
                if not call:
                    return await interaction.response.send_message("Incident record not found.", ephemeral=True)
                if str(call['AnsweredStatus']).lower() in ('1', 'true'):
                    return await interaction.response.send_message("Incident already claimed.", ephemeral=True)

                conn.execute("UPDATE calls SET AnsweredStatus = 1, AnsweredBy = ?, AnsweredTimestamp = ? WHERE ReportID = ?", 
                               (user_display, now, report_id))
                conn.execute("INSERT INTO call_history (CallID, Timestamp, User, Action, Details) VALUES (?, ?, ?, ?, ?)", 
                               (report_id, now, "Discord Bot", "Call Answered", f"Claimed by {user_display}"))
                
                cursor = conn.execute("SELECT * FROM calls WHERE ReportID = ?", (report_id,))
                fresh_row = cursor.fetchone()

            embed = generate_embed(fresh_row)
            self.children[0].disabled = True
            self.children[0].label = "Claimed"
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            await interaction.response.send_message(f"Database error: {e}", ephemeral=True)
        finally:
            conn.close()

    @discord.ui.button(label="✅ Resolve Incident", style=discord.ButtonStyle.blurple, custom_id="resolve_incident_btn")
    async def resolve_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        report_id = interaction.message.embeds[0].title.split(': ')[-1].strip()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        user_display = interaction.user.display_name
        conn = get_db_connection()

        try:
            with conn:
                cursor = conn.execute("SELECT * FROM calls WHERE ReportID = ?", (report_id,))
                call = cursor.fetchone()
                if str(call['ResolutionStatus']).lower() in ('1', 'true'):
                    return await interaction.response.send_message("Incident already resolved.", ephemeral=True)

                conn.execute("UPDATE calls SET ResolutionStatus = 1, ResolvedBy = ?, ResolutionTimestamp = ? WHERE ReportID = ?", 
                               (user_display, now, report_id))
                conn.execute("INSERT INTO call_history (CallID, Timestamp, User, Action, Details) VALUES (?, ?, ?, ?, ?)", 
                               (report_id, now, "Discord Bot", "Call Resolved", f"Resolved by {user_display}"))

                cursor = conn.execute("SELECT * FROM calls WHERE ReportID = ?", (report_id,))
                fresh_row = cursor.fetchone()

            embed = generate_embed(fresh_row)
            self.children[0].disabled = True
            self.children[1].disabled = True
                
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            await interaction.response.send_message(f"Database error: {e}", ephemeral=True)
        finally:
            conn.close()

class IncidentReportModal(discord.ui.Modal, title="🚨 Report Emergency to HQ"):
    location = discord.ui.TextInput(label="Exact Location", placeholder="E.g., Hall A, Main Stage", required=True, max_length=1000)
    situation = discord.ui.TextInput(label="Situation (Optional Code)", placeholder="E.g., Blue, Adam, Orange, etc.", required=False, max_length=100)
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, required=True, max_length=3990)

    async def on_submit(self, interaction: discord.Interaction):
        now = datetime.now()
        call_id_prefix = f"DC{now.strftime('%y')}"
        discord_user = interaction.user.display_name
        
        channel_source = f"Discord: #{interaction.channel.name}"
        incident_code = self.situation.value.strip() if self.situation.value.strip() else "No_Code"
        conn = get_db_connection()
        
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO calls (
                        CallDate, CallTime, AnsweredTimestamp, AnsweredStatus, AnsweredBy,
                        ResolutionTimestamp, ResolutionStatus, ResolvedBy, InputMedium, Source, 
                        Caller, Location, Code, Description, CreatedBy, ModifiedBy, RedFlag, ReportNumber, Deleted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    now.strftime("%Y-%m-%d"), now.strftime("%H:%M"), "", False, "", "", False, "",
                    "Social Media", channel_source, discord_user, self.location.value, 
                    incident_code, self.description.value, discord_user, "", False, "", False
                ))
                new_id = cursor.lastrowid
                report_id = f"{call_id_prefix}-{new_id:04d}"
                cursor.execute("UPDATE calls SET ReportID = ? WHERE ID = ?", (report_id, new_id))
                cursor.execute("INSERT INTO call_history (CallID, Timestamp, User, Action, Details) VALUES (?, ?, ?, ?, ?)", 
                               (report_id, now.strftime("%Y-%m-%d %H:%M:%S"), "Discord Bot", "Call Created", "Reported via Discord Modal"))
                
                cursor.execute("SELECT * FROM calls WHERE ReportID = ?", (report_id,))
                fresh_row = cursor.fetchone()
                
            await interaction.response.send_message(f"✅ Incident **{report_id}** successfully transmitted to HQ.", ephemeral=True)
            
            embed = generate_embed(fresh_row)
            view = IncidentControlView()
            msg = await interaction.channel.send(embed=embed, view=view)
            
            with conn:
                conn.execute("UPDATE calls SET DiscordMessageID=?, DiscordChannelID=? WHERE ReportID=?", 
                             (str(msg.id), str(interaction.channel.id), report_id))
        except Exception as e:
            await interaction.response.send_message(f"Failed to submit: {e}", ephemeral=True)
        finally:
            conn.close()

@bot.tree.command(name="report", description="Report a new incident directly to the HQ Dispatch Desk")
async def report_incident(interaction: discord.Interaction):
    await interaction.response.send_modal(IncidentReportModal())

# ==========================================
# HQ TO DISCORD BACKGROUND SIGNALING
# ==========================================
class LocalCommunicationServer(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        data = json.loads(self.rfile.read(content_length).decode('utf-8'))
        
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
        cursor = conn.execute("SELECT * FROM calls WHERE ReportID = ?", (report_id,))
        row = cursor.fetchone()
        if not row: return

        channel_id = CHANNEL_MAP.get(source, CHANNEL_MAP["General"])
        channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)

        embed = generate_embed(row)
        view = IncidentControlView()
        
        is_answered = str(row['AnsweredStatus']).lower() in ('1', 'true')
        is_resolved = str(row['ResolutionStatus']).lower() in ('1', 'true')
        if is_answered or is_resolved:
            view.children[0].disabled = True
            view.children[0].label = "Claimed"
        if is_resolved:
            view.children[1].disabled = True
            
        msg = await channel.send(embed=embed, view=view)
        
        conn.execute("UPDATE calls SET DiscordMessageID=?, DiscordChannelID=? WHERE ReportID=?", (str(msg.id), str(channel.id), report_id))
        conn.commit()
    except Exception as e:
        print(f"[BOT ERROR] Post failed: {e}")
    finally:
        conn.close()

async def edit_dispatch_message(report_id):
    await asyncio.sleep(0.5)
    conn = get_db_connection()
    try:
        conn.commit()
        cursor = conn.execute("SELECT * FROM calls WHERE ReportID = ?", (report_id,))
        row = cursor.fetchone()
        
        if not row or not row['DiscordMessageID'] or not row['DiscordChannelID']: return
            
        channel = bot.get_channel(int(row['DiscordChannelID'])) or await bot.fetch_channel(int(row['DiscordChannelID']))
        message = await channel.fetch_message(int(row['DiscordMessageID']))
        
        embed = generate_embed(row)
        view = IncidentControlView()
        
        is_answered = str(row['AnsweredStatus']).lower() in ('1', 'true')
        is_resolved = str(row['ResolutionStatus']).lower() in ('1', 'true')
        if is_answered or is_resolved:
            view.children[0].disabled = True
            view.children[0].label = "Claimed"
        if is_resolved:
            view.children[1].disabled = True
                
        await message.edit(embed=embed, view=view)
    except Exception as e:
        print(f"[BOT ERROR] Discord update failed for {report_id}: {e}")
    finally:
        conn.close()

# FIX: Correctly registering the persistent view hook (No @bot.event decorator here)
async def setup_bot_hook():
    print("✅ Registering persistent UI buttons...")
    bot.add_view(IncidentControlView())

bot.setup_hook = setup_bot_hook

@bot.event
async def on_ready():
    print(f"✅ Bot successfully logged into Discord as {bot.user}")
    print("✅ Syncing slash commands...")
    await bot.tree.sync()
    print("🚨 BOT IS FULLY ONLINE AND READY.")

if __name__ == "__main__":
    try:
        if not DISCORD_TOKEN:
            print("❌ FATAL: The DISCORD_TOKEN in config.ini is empty or missing.")
            sys.exit(1)

        print(f"✅ Starting Local IPC GUI Communicator on Port {PORT}...")
        server_thread = threading.Thread(
            target=lambda: HTTPServer(('localhost', PORT), LocalCommunicationServer).serve_forever(), 
            daemon=True
        )
        server_thread.start()
        
        print("✅ Attempting to connect to Discord API...")
        bot.run(DISCORD_TOKEN)

    except discord.errors.LoginFailure:
        print("❌ FATAL: Invalid Discord Token. Please check your config.ini")
    except OSError as e:
        if e.errno == 10048:
            print(f"❌ FATAL: Port {PORT} is already in use. Is another copy of the bot running in the background?")
        else:
            print(f"❌ OS ERROR: {e}")
    except Exception as e:
        print(f"❌ CRASH: An unexpected error occurred: {e}")
        traceback.print_exc()