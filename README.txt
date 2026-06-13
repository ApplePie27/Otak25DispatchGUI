Dispatch Call Management System (V5)
====================================

Overview
--------
The Dispatch Call Management System is a Python-based application for tracking and managing convention dispatch calls. It features a user-friendly Tkinter GUI for headquarters, an automated Discord bot for field notifications, and relies on a synchronized SQLite database to support multiple dispatchers seamlessly over a local network.

Key Features
------------
- Complete call management (add/modify/resolve/void)
- Local SQLite Database for multi-user concurrency
- Discord Bot Integration (Smart routing and Read-Only notifications)
- Automated Thread Logging (Mirrors Discord field chat to the HQ database)
- Automated SLA Timers (Visual color-coding for response times)
- High-Priority Audio Alarms (Submarine klaxons for severe incidents)
- Comprehensive search and filtering
- Immutable liability audit logs and CSV reporting
- Shift Passdown notes for dispatcher handovers

System Requirements
-------------------
- OS: Windows 10+, macOS 10.15+, or Linux
- Python: 3.8 or later
- RAM: 4GB minimum (8GB recommended)
- Storage: 100MB available space
- Network: Local LAN router (for multi-computer sync)

Installation
------------
1. Ensure Python 3.8+ is installed.
2. Download or clone the repository.
3. Install required dependencies via command line:
   pip install discord.py sv_ttk
4. Ensure config.ini is located in the same directory as the scripts.
5. Run the applications from command line:
   python main.py (For the HQ GUI)
   python discord_bot.py (For the Field Bot)

First Run
---------
- System will read the config.ini file for settings and channels.
- System will automatically generate dispatch.db (the SQLite database).
- Prompt for dispatcher username login.

User Guide
----------
Getting Started
1. Logging In: Upon launching the application, enter your username to log in.
2. Main Interface: The main window consists of input fields, action buttons, a color-coded SLA table for displaying calls, and a bottom log area.

Adding a New Call
1. Fill in the input fields (Input Medium, Caller, Location, Code, Description).
2. Click "ADD CALL" to save the incident. It will appear in the table and automatically route to Discord if it is a high-priority code.

Resolving or Voiding a Call
1. Select a call from the table.
2. Check the "Resolved" or "Cancelled / Void" checkbox.
3. If resolved, enter the name of the resolver.
4. Click "SAVE MODIFICATION". The table row will turn Green (Resolved) or Grey (Void).

Modifying a Call
1. Select a call from the table.
2. Update the input fields with new details.
3. Click "SAVE MODIFICATION" to update the call. All changes are tracked in the history log.

Viewing Incident History & Discord Logs
1. Select a call from the table.
2. Click "View History".
3. A window will display every modification, state change, and intercepted Discord thread message related to that specific ticket.

SLA Timers & Priorities
- Black: Open for < 5 minutes.
- Yellow: SLA Warning (Open for > 5 minutes without being resolved).
- Slate Blue: High-priority emergency (Medical, Active Threat, Missing Child).
- Dark Red: SLA Critical (Ticket has been open for > 30 minutes. Requires radio check-in).

Exporting Data
- Export Report: Click "File -> Export Report to CSV" to export the current table for statistics.
- Export Audit Log: Admins can click "File -> Export Complete Audit Log" to download the uneditable, second-by-second history of the entire convention.

Troubleshooting
-------------
- Configuration Errors: Ensure config.ini exists and has valid Discord Channel IDs.
- Dark Mode / UI Crashing: Ensure the 'sv_ttk' library is installed via pip.
- Discord Bot Not Posting: Verify the bot token is correct in config.ini and the bot has "Create Public Threads" permissions in the server.
- Database Locking: The system handles this automatically, but ensure all laptops are connected to the same local network and Windows Sleep Mode is disabled.

Backup System
-------------
- The system automatically creates isolated localized backups.
- Stored in backups/ directory.
- Files named: backup_YYYYMMDD_HHMMSS.db.
- Maintains last 10 backup database sets.

Pros and Cons
-------------
Pros
- Offline-Capable: Continues to function entirely offline via local network even if venue Wi-Fi/Discord goes down.
- Liability Tracking: Immutable audit logs protect the convention post-event.
- Automated Triage: SLA timers and smart routing reduce dispatcher cognitive load.
- Modern UI: Supports Light and Dark modes with vivid readability.

Cons
- Local Database Limitations: Relies on Windows SMB File Sharing rather than a cloud-based client-server model.
- Strict Setup: Requires matching Python environments and config files across all machines.

License
This project is licensed under the MIT License. See the LICENSE file for details.