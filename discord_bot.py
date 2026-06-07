import discord
from discord.ext import commands
import sqlite3
import configparser
import asyncio
import threading
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

# ==========================================
# LOAD CONFIGURATION
# ==========================================
config = configparser.ConfigParser()
config.read('config.ini')

DISCORD_TOKEN = config.get('DISCORD', 'bot_token')
DB_PATH = config.get('DATABASE', 'filename', fallback='dispatch.db')
PORT = 8080

CHANNEL_MAP = {
    "Safety": int(config.get('DISCORD', 'safety_channel')),
    "General": int(config.get('DISCORD', 'general_channel')),
    "First Aid": int(config.get('DISCORD', 'first_aid_channel'))
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def get_db_connection():
    """Create a network-safe SQLite connection for the Discord Bot."""
    # Convert to absolute path - helps Windows File Share resolve the file properly
    abs_path = os.path.abspath(DB_PATH)
    
    # timeout=20.0 forces the bot to wait patiently if the GUI is currently saving a file
    conn = sqlite3.connect(abs_path, timeout=20.0)
    conn.row_factory = sqlite3.Row
    
    # CRITICAL: These must exactly match the GUI's data_manager.py settings for Network Shares
    conn.execute("PRAGMA journal_mode=TRUNCATE;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=20000;")
    
    return conn

# ==========================================
# INTERACTIVE BUTTONS
# ==========================================
class IncidentControlView(discord.ui.View):
    def __init__(self, report_id: str):
        super().__init__(timeout=None)
        self.report_id = report_id

    @discord.ui.button(label="🙋 Claim Assignment", style=discord.ButtonStyle.green, custom_id="claim_btn")
    async def claim_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        user_display = interaction.user.display_name
        conn = get_db_connection()

        try:
            with conn:
                cursor = conn.execute("SELECT * FROM calls WHERE ReportID = ?", (self.report_id,))
                call = cursor.fetchone()
                
                if not call:
                    await interaction.response.send_message("Incident record not found.", ephemeral=True)
                    return
                if call['AnsweredStatus']:
                    await interaction.response.send_message("Incident already claimed.", ephemeral=True)
                    return

                conn.execute("""UPDATE calls SET AnsweredStatus = 1, AnsweredBy = ?, AnsweredTimestamp = ? WHERE ReportID = ?""", 
                               (user_display, now, self.report_id))
                conn.execute("""INSERT INTO call_history (CallID, Timestamp, User, Action, Details) VALUES (?, ?, ?, ?, ?)""", 
                               (self.report_id, now, "Discord Bot", "Call Answered", f"Claimed by {user_display}"))

            embed = interaction.message.embeds[0]
            embed.color = discord.Color.orange()
            embed.add_field(name="Assigned Responder", value=f"Claimed by {user_display} at {now}", inline=False)
            button.disabled = True
            button.label = "Claimed"
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            await interaction.response.send_message(f"Database error: {e}", ephemeral=True)
        finally:
            conn.close()

    @discord.ui.button(label="✅ Resolve Incident", style=discord.ButtonStyle.blurple, custom_id="resolve_btn")
    async def resolve_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        user_display = interaction.user.display_name
        conn = get_db_connection()

        try:
            with conn:
                cursor = conn.execute("SELECT * FROM calls WHERE ReportID = ?", (self.report_id,))
                call = cursor.fetchone()
                if call['ResolutionStatus']:
                    await interaction.response.send_message("Incident already resolved.", ephemeral=True)
                    return

                conn.execute("""UPDATE calls SET ResolutionStatus = 1, ResolvedBy = ?, ResolutionTimestamp = ? WHERE ReportID = ?""", 
                               (user_display, now, self.report_id))
                conn.execute("""INSERT INTO call_history (CallID, Timestamp, User, Action, Details) VALUES (?, ?, ?, ?, ?)""", 
                               (self.report_id, now, "Discord Bot", "Call Resolved", f"Resolved by {user_display}"))

            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            embed.title = f"✅ Resolved: {self.report_id}"
            for child in self.children: child.disabled = True
                
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            await interaction.response.send_message(f"Database error: {e}", ephemeral=True)
        finally:
            conn.close()

# ==========================================
# VOLUNTEER-TO-HQ REPORTING MODAL
# ==========================================
class IncidentReportModal(discord.ui.Modal, title="🚨 Report Emergency to HQ"):
    location = discord.ui.TextInput(label="Exact Location", placeholder="E.g., Hall A, Main Stage", required=True)
    situation = discord.ui.TextInput(label="Situation (Optional Code)", placeholder="E.g., Medical, General", required=False)
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        now = datetime.now()
        call_id_prefix = f"DC{now.strftime('%y')}"
        discord_user = interaction.user.display_name
        
        # Capture the name of the Discord channel where the command was typed
        channel_source = f"Discord: #{interaction.channel.name}"
        
        conn = get_db_connection()
        
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO calls (
                        CallDate, CallTime, AnsweredTimestamp, AnsweredStatus, AnsweredBy,
                        ResolutionTimestamp, ResolutionStatus, ResolvedBy, InputMedium, Source, 
                        Caller, Location, Code, Description, CreatedBy, ModifiedBy, RedFlag,
                        ReportNumber, Deleted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    now.strftime("%Y-%m-%d"), now.strftime("%H:%M"), "", False, "", "", False, "",
                    "Social Media", channel_source, discord_user, self.location.value, 
                    self.situation.value or "No_Code", self.description.value, discord_user, "", False, "", False
                ))
                
                new_id = cursor.lastrowid
                report_id = f"{call_id_prefix}-{new_id:04d}"
                cursor.execute("UPDATE calls SET ReportID = ? WHERE ID = ?", (report_id, new_id))
                
            await interaction.response.send_message(f"✅ Incident **{report_id}** successfully transmitted to HQ Dispatch.", ephemeral=True)
            
            # Post the interactive card into the channel so others can claim it
            channel = interaction.channel
            embed = discord.Embed(title=f"🚨 Field Report: {report_id}", description=self.description.value, color=discord.Color.red())
            embed.add_field(name="Location", value=self.location.value, inline=True)
            embed.add_field(name="Reported By", value=discord_user, inline=True)
            await channel.send(embed=embed, view=IncidentControlView(report_id))
            
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
        if self.path == "/dispatch":
            content_length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(content_length).decode('utf-8'))
            
            asyncio.run_coroutine_threadsafe(
                post_dispatch_message(data.get("report_id"), data.get("location"), data.get("code"), data.get("description"), data.get("source")),
                bot.loop
            )
            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

async def post_dispatch_message(report_id, location, code, description, source):
    channel_id = CHANNEL_MAP.get(source, CHANNEL_MAP["General"])
    channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)

    embed = discord.Embed(title=f"🚨 New HQ Alert: {report_id}", description=description, color=discord.Color.red())
    embed.add_field(name="Location", value=location, inline=True)
    embed.add_field(name="Code", value=code if code else "No_Code", inline=True)
    await channel.send(embed=embed, view=IncidentControlView(report_id))

@bot.event
async def on_ready():
    print(f"SQLite Discord Dispatch Bot active as {bot.user}")
    await bot.tree.sync()

if __name__ == "__main__":
    threading.Thread(target=lambda: HTTPServer(('localhost', PORT), LocalCommunicationServer).serve_forever(), daemon=True).start()
    bot.run(DISCORD_TOKEN)