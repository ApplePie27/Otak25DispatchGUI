import discord
from discord.ext import commands
import sqlite3
import json
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

# ==========================================
# CONFIGURATION
# ==========================================
DB_PATH = "dispatch.db"
DISCORD_TOKEN = "MTUxMDczMjQ4NTQzMTEzNjMwNg.G9WCLY.tKprdSYxsGPEBehb8JTX-ALk74JXX593FGlLOM"      # Replace with your Bot Token
PORT = 8080                                        # Communication port between GUI and Bot

# Map your GUI 'Source' selections directly to distinct Discord Channel IDs
# Replace these placeholder IDs with your actual Discord Text Channel IDs
CHANNEL_MAP = {
    "Safety": 1510743241690058916,      # Replace with your Safety Channel ID
    "General": 1510731653251596532,    # Replace with your General Channel ID
    "First Aid": 1510743272291696721     # Replace with your First Aid Channel ID
}

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================================
# BOT VIEW (INTERACTIVE BUTTONS)
# ==========================================
class IncidentControlView(discord.ui.View):
    def __init__(self, report_id: str):
        super().__init__(timeout=None)
        self.report_id = report_id

    @discord.ui.button(label="🙋 Claim Assignment", style=discord.ButtonStyle.green, custom_id="claim_btn")
    async def claim_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        user_display = interaction.user.display_name

        try:
            with conn:
                cursor = conn.execute("SELECT * FROM calls WHERE ReportID = ?", (self.report_id,))
                call = cursor.fetchone()
                
                if not call:
                    await interaction.response.send_message("Incident record not found.", ephemeral=True)
                    return
                
                if call['AnsweredStatus']:
                    await interaction.response.send_message(f"This incident was already claimed by {call['AnsweredBy']}.", ephemeral=True)
                    return

                conn.execute("""
                    UPDATE calls 
                    SET AnsweredStatus = 1, AnsweredBy = ?, AnsweredTimestamp = ? 
                    WHERE ReportID = ?
                """, (user_display, now, self.report_id))
                
                conn.execute("""
                    INSERT INTO call_history (CallID, Timestamp, User, Action, Details)
                    VALUES (?, ?, ?, ?, ?)
                """, (self.report_id, now, "Discord Bot", "Call Answered", f"Claimed by {user_display}"))

            embed = interaction.message.embeds[0]
            embed.color = discord.Color.orange()
            embed.add_field(name="Assigned Responder", value=f"Claimed by {user_display} at {now}", inline=False)
            
            button.disabled = True
            button.label = "Claimed"
            
            await interaction.response.edit_message(embed=embed, view=self)
            await interaction.followup.send(f"You have claimed incident **{self.report_id}**.", ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"Database error: {e}", ephemeral=True)
        finally:
            conn.close()

    @discord.ui.button(label="✅ Resolve Incident", style=discord.ButtonStyle.blurple, custom_id="resolve_btn")
    async def resolve_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Enables named column queries on database tuples
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        user_display = interaction.user.display_name

        try:
            with conn:
                cursor = conn.execute("SELECT * FROM calls WHERE ReportID = ?", (self.report_id,))
                call = cursor.fetchone()
                
                if not call:
                    await interaction.response.send_message("Incident record not found.", ephemeral=True)
                    return
                
                if call['ResolutionStatus']:
                    await interaction.response.send_message("Incident has already been resolved.", ephemeral=True)
                    return

                conn.execute("""
                    UPDATE calls 
                    SET ResolutionStatus = 1, ResolvedBy = ?, ResolutionTimestamp = ? 
                    WHERE ReportID = ?
                """, (user_display, now, self.report_id))
                
                conn.execute("""
                    INSERT INTO call_history (CallID, Timestamp, User, Action, Details)
                    VALUES (?, ?, ?, ?, ?)
                """, (self.report_id, now, "Discord Bot", "Call Resolved", f"Resolved by {user_display}"))

            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            embed.title = f"✅ Resolved: {self.report_id}"
            embed.add_field(name="Resolution State", value=f"Resolved by {user_display} at {now}", inline=False)
            
            for child in self.children:
                child.disabled = True
                
            await interaction.response.edit_message(embed=embed, view=self)
            await interaction.followup.send(f"Incident **{self.report_id}** has been resolved.", ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"Database error: {e}", ephemeral=True)
        finally:
            conn.close()


# ==========================================
# LOCAL COMMUNICATION LISTENER (HTTP)
# ==========================================
class LocalCommunicationServer(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        """Processes incoming post requests from the Tkinter desktop GUI."""
        if self.path == "/dispatch":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            report_id = data.get("report_id")
            location = data.get("location")
            code = data.get("code")
            description = data.get("description")
            source = data.get("source")
            
            asyncio.run_coroutine_threadsafe(
                post_dispatch_message(report_id, location, code, description, source),
                bot.loop
            )
            
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status": "success"}')
        else:
            self.send_response(404)
            self.end_headers()

def start_http_server():
    server = HTTPServer(('localhost', PORT), LocalCommunicationServer)
    print(f"Internal signaling server running on port {PORT}")
    server.serve_forever()


# ==========================================
# ASYNC BOT EVENTS & TASKS
# ==========================================
async def post_dispatch_message(report_id, location, code, description, source):
    """Sends the formatted rich embed card containing claim buttons to the assigned channel."""
    # Lookup target channel from map using source parameter. Fallback to General.
    channel_id = CHANNEL_MAP.get(source, CHANNEL_MAP["General"])
    
    channel = bot.get_channel(channel_id)
    if not channel:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception as e:
            print(f"Error: Could not retrieve Channel ID {channel_id} (Source: {source}) via API. Details: {e}")
            return

    embed = discord.Embed(
        title=f"🚨 New Incident Alert: {report_id}",
        description=description,
        color=discord.Color.red(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Location", value=location, inline=True)
    embed.add_field(name="Source Dept", value=source, inline=True)
    embed.add_field(name="Incident Code", value=code if code else "No_Code", inline=True)
    embed.set_footer(text="HQ Dispatch Center")

    view = IncidentControlView(report_id=report_id)
    await channel.send(embed=embed, view=view)


@bot.event
async def on_ready():
    print(f"Two-Way Discord Dispatch Bot active as {bot.user}")
    try:
        await bot.tree.sync()
        print("Slash commands synced successfully.")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")


# ==========================================
# VOLUNTEER SLASH COMMANDS
# ==========================================
@bot.tree.command(name="status", description="Query details of a specific dispatch call")
async def status(interaction: discord.Interaction, report_id: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute("SELECT * FROM calls WHERE ReportID = ?", (report_id,))
        call = cursor.fetchone()
        
        if not call:
            await interaction.response.send_message(f"Could not locate call '{report_id}'.", ephemeral=True)
            return

        status_text = "🔴 Open"
        if call['ResolutionStatus']:
            status_text = "🟢 Resolved"
        elif call['AnsweredStatus']:
            status_text = f"🟡 Claimed by {call['AnsweredBy']}"

        embed = discord.Embed(title=f"Call Details: {report_id}", color=discord.Color.blue())
        embed.add_field(name="Status", value=status_text, inline=True)
        embed.add_field(name="Location", value=call['Location'], inline=True)
        embed.add_field(name="Code Type", value=call['Code'] if call['Code'] else "No_Code", inline=True)
        embed.add_field(name="Description", value=call['Description'], inline=False)
        
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
    finally:
        conn.close()


if __name__ == "__main__":
    # Launch internal communications server on background thread
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    # Launch Discord client
    bot.run(DISCORD_TOKEN)